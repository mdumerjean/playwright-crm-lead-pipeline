"""Thin subprocess wrappers around ffmpeg/ffprobe.

Kept dependency-free (no ffmpeg-python binding) so the only new requirement
is the ffmpeg/ffprobe binaries themselves, installed once via Homebrew.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

VIDEO_W = 1920
VIDEO_H = 1080
FPS = 30


def run(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(str(c) for c in cmd)}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
    return result


def probe(path: Path) -> dict:
    """ffprobe -> parsed JSON with format + stream info."""
    result = run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ]
    )
    return json.loads(result.stdout)


def duration_seconds(path: Path) -> float:
    data = probe(path)
    return float(data["format"]["duration"])


def audio_to_wav(src: Path, dst: Path) -> Path:
    run(["ffmpeg", "-y", "-i", str(src), "-ar", "44100", "-ac", "2", str(dst)])
    return dst


def image_to_video(image: Path, dst: Path, duration_s: float, fade_s: float = 0.4) -> Path:
    """Static image -> silent video of exact duration, with a restrained fade in/out."""
    fade_out_start = max(0.0, duration_s - fade_s)
    vf = f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2,fade=t=in:st=0:d={fade_s},fade=t=out:st={fade_out_start}:d={fade_s}"
    run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(image),
            "-t", f"{duration_s:.3f}", "-r", str(FPS),
            "-vf", vf,
            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-an",
            str(dst),
        ]
    )
    return dst


def webm_to_normalized_mp4(
    src: Path, dst: Path, target_duration_s: Optional[float] = None, max_slowdown: float = 1.8
) -> tuple:
    """Normalize a Playwright-recorded .webm to 1920x1080/30fps h264.

    If `target_duration_s` is given and the real clip is shorter, playback is
    slowed down -- but only up to `max_slowdown`x (a real, visually honest
    pace, not a distorted crawl). Any remaining gap is left for the caller to
    fill by holding the final frame (see mux_video_audio's padding). If the
    real clip is longer than the target, it's sped up instead (uncapped --
    speeding up an over-long real clip for pacing is a standard, non-deceptive
    edit, same as a timelapse).

    Returns (dst, speed_factor) where speed_factor > 1 means sped up and
    < 1 means slowed down, so the caller can decide whether a label is
    warranted -- no numeric claim about elapsed time is embedded here.
    """
    src_duration = duration_seconds(src)
    filters = [f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2"]
    speed_factor = 1.0

    if target_duration_s and src_duration > 0:
        raw_speed_factor = src_duration / target_duration_s
        if raw_speed_factor < 1.0:
            # Would need to slow down by 1/raw_speed_factor; cap it.
            speed_factor = max(raw_speed_factor, 1 / max_slowdown)
        else:
            speed_factor = raw_speed_factor
        pts_multiplier = 1 / speed_factor
        filters.append(f"setpts={pts_multiplier:.6f}*PTS")

    vf = ",".join(filters)
    run(
        [
            "ffmpeg", "-y", "-i", str(src),
            "-vf", vf, "-r", str(FPS),
            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-an",
            str(dst),
        ]
    )
    return dst, speed_factor


def overlay_png(video: Path, png: Path, dst: Path) -> Path:
    """Composite a (possibly transparent) PNG over the full duration of `video`."""
    run(
        [
            "ffmpeg", "-y", "-i", str(video), "-loop", "1", "-i", str(png),
            "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
            str(dst),
        ]
    )
    return dst


def mux_video_audio(video_only: Path, audio: Path, dst: Path, min_duration_s: Optional[float] = None) -> Path:
    """Combine a silent video clip with a narration track.

    If the video is shorter than the audio, the last video frame is held
    (tpad) so narration is never cut off. If longer, output length follows
    the video (audio is padded with silence).
    """
    video_dur = duration_seconds(video_only)
    audio_dur = duration_seconds(audio)
    target = max(video_dur, audio_dur, min_duration_s or 0.0)
    pad_needed = max(0.0, target - video_dur)

    vf = f"tpad=stop_mode=clone:stop_duration={pad_needed:.3f}" if pad_needed > 0 else "null"

    run(
        [
            "ffmpeg", "-y",
            "-i", str(video_only),
            "-i", str(audio),
            "-filter_complex", f"[0:v]{vf}[v]",
            "-map", "[v]", "-map", "1:a",
            "-t", f"{target:.3f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(dst),
        ]
    )
    return dst


def concat_videos(clips: list, dst: Path) -> Path:
    list_file = dst.parent / "_concat_list.txt"
    list_file.write_text("\n".join(f"file '{Path(c).resolve()}'" for c in clips) + "\n")
    run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(dst),
        ]
    )
    list_file.unlink(missing_ok=True)
    return dst


def extract_frame(video: Path, at_seconds: float, dst: Path) -> Path:
    run(["ffmpeg", "-y", "-ss", f"{at_seconds:.2f}", "-i", str(video), "-vframes", "1", str(dst)])
    return dst
