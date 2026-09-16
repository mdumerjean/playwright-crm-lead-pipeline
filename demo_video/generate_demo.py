#!/usr/bin/env python3
"""Generates a ~60-90s demo MP4 from REAL execution of this project.

Every visual is either:
  (a) a direct recording of the real Playwright browser session (Scene 2),
  (b) a styled render of real captured terminal/JSON/code text (Scenes 3-6),
  (c) a static title card with no execution claims of its own (Scenes 1, 7).

Nothing here fabricates logs, test results, JSON, or code. If the real
`python main.py` run or the real `pytest` run fails, this script stops and
reports that, rather than producing a video with faked "success" output.

Usage:
    source .venv/bin/activate
    python demo_video/generate_demo.py

See demo_video/README.md for details.
"""
from __future__ import annotations

import json
import re
import sys
import textwrap
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DEMO_DIR.parent
sys.path.insert(0, str(DEMO_DIR))

from lib import capture, ffmpeg_utils, html_render, templates, tts  # noqa: E402

SCENES_DIR = DEMO_DIR / "scenes"
AUDIO_DIR = DEMO_DIR / "audio"
CAPTURED_DIR = DEMO_DIR / "captured"
OUTPUT_DIR = DEMO_DIR / "output"
FINAL_MP4 = OUTPUT_DIR / "playwright-automation-demo.mp4"

REPO_LABEL = "github.com/mdumerjean/playwright-crm-lead-pipeline"


def log(msg: str) -> None:
    print(f"[generate_demo] {msg}", flush=True)


def parse_narration(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^## SCENE (\d+)\s*$", text, flags=re.MULTILINE)
    scenes = {}
    # parts = [preamble, "1", text1, "2", text2, ...]
    for i in range(1, len(parts), 2):
        scene_num = int(parts[i])
        scene_text = " ".join(parts[i + 1].split())  # collapse whitespace/newlines
        scenes[scene_num] = scene_text
    return scenes


def truncate(s: str, max_len: int) -> str:
    s = s.strip()
    return s if len(s) <= max_len else s[: max_len - 1].rstrip() + "…"


def drop_sensitive_lines(lines: list) -> list:
    """Blanket safety net for real captured terminal output: drop any line
    carrying an absolute local filesystem path (which embeds the machine's
    username) rather than trying to redact just the path substring."""
    return [l for l in lines if "/Users/" not in l]


def clean_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*"):
        if f.name != ".gitkeep" and f.is_file():
            f.unlink()
        elif f.is_dir():
            import shutil

            shutil.rmtree(f)


# --------------------------------------------------------------------------
# Scene builders. Each returns a path to a final muxed (video+audio) mp4.
# --------------------------------------------------------------------------


def build_title_scene(name: str, kicker: str, title: str, subtitle: str, bullets: list, footer: str, audio_path: Path, audio_dur: float) -> Path:
    html_str = templates.title_card(kicker, title, subtitle, bullets, footer)
    png = SCENES_DIR / f"{name}.png"
    html_render.screenshot_html(html_str, png)
    silent_mp4 = SCENES_DIR / f"{name}_silent.mp4"
    ffmpeg_utils.image_to_video(png, silent_mp4, duration_s=audio_dur + 0.6)
    final = SCENES_DIR / f"{name}_final.mp4"
    ffmpeg_utils.mux_video_audio(silent_mp4, audio_path, final)
    return final


def build_terminal_scene(name: str, lines: list, audio_path: Path, audio_dur: float) -> Path:
    hold_s = audio_dur + 0.6
    html_str = templates.terminal_typing(lines, target_seconds=hold_s)
    webm = html_render.record_html_video(html_str, SCENES_DIR / f"{name}_raw", hold_seconds=hold_s)
    normalized = SCENES_DIR / f"{name}_norm.mp4"
    ffmpeg_utils.webm_to_normalized_mp4(webm, normalized)
    final = SCENES_DIR / f"{name}_final.mp4"
    ffmpeg_utils.mux_video_audio(normalized, audio_path, final)
    return final


def build_code_scene(name: str, code: str, filename: str, note: str, audio_path: Path, audio_dur: float, is_json: bool = False) -> Path:
    html_str = (
        templates.json_viewer(code, filename, note) if is_json else templates.code_viewer(code, filename, note)
    )
    png = SCENES_DIR / f"{name}.png"
    html_render.screenshot_html(html_str, png)
    silent_mp4 = SCENES_DIR / f"{name}_silent.mp4"
    ffmpeg_utils.image_to_video(png, silent_mp4, duration_s=audio_dur + 0.6)
    final = SCENES_DIR / f"{name}_final.mp4"
    ffmpeg_utils.mux_video_audio(silent_mp4, audio_path, final)
    return final


def build_browser_scene(name: str, webm_path: Path, audio_path: Path, audio_dur: float, caption: str) -> Path:
    target = audio_dur + 0.6
    normalized = SCENES_DIR / f"{name}_norm.mp4"
    _, speed_factor = ffmpeg_utils.webm_to_normalized_mp4(webm_path, normalized, target_duration_s=target)

    speed_label = ""
    if speed_factor > 1.15:
        speed_label = f"{speed_factor:.1f}x sped up for time"
    elif speed_factor < 0.85:
        speed_label = f"{1 / speed_factor:.1f}x slowed for visibility"

    overlay_html = templates.caption_overlay(caption, speed_label)
    overlay_png = SCENES_DIR / f"{name}_overlay.png"
    html_render.screenshot_html_transparent(overlay_html, overlay_png)

    captioned = SCENES_DIR / f"{name}_captioned.mp4"
    ffmpeg_utils.overlay_png(normalized, overlay_png, captioned)

    final = SCENES_DIR / f"{name}_final.mp4"
    ffmpeg_utils.mux_video_audio(captioned, audio_path, final, min_duration_s=target)
    return final


def main() -> int:
    if not tts.is_available():
        log("ERROR: macOS `say` is not available on this system.")
        log("Narration requires either running this on macOS, or wiring in an external")
        log("TTS API/credential -- which this script deliberately will not do without")
        log("your explicit approval. Stopping here rather than fabricating narration.")
        return 1

    for d in (SCENES_DIR, AUDIO_DIR, CAPTURED_DIR, OUTPUT_DIR):
        clean_dir(d)

    # ---- Narration -> per-scene audio (real synthesis, measured real durations) ----
    log("Synthesizing narration with macOS `say` (voice: Samantha, offline, no API)...")
    scene_texts = parse_narration(DEMO_DIR / "narration.txt")
    audio_paths, audio_durs = {}, {}
    for n, text in scene_texts.items():
        wav = AUDIO_DIR / f"scene{n}.wav"
        dur = tts.synthesize(text, wav)
        audio_paths[n], audio_durs[n] = wav, dur
        log(f"  scene {n}: {dur:.1f}s ({len(text.split())} words)")
    total_narration = sum(audio_durs.values())
    log(f"Total narration length: {total_narration:.1f}s")

    # ---- Real execution: python main.py, with real Playwright video recording ----
    log("Running the REAL application: python main.py (bounded to a short, presentable run)...")
    video_dir = CAPTURED_DIR / "browser_video"
    main_result = capture.run_real_main(
        PROJECT_ROOT,
        video_dir,
        CAPTURED_DIR / "main_run.log",
        env_overrides={
            # Mystery category has 20 books on page 1 -- MAX_RECORDS > 20 forces a
            # real page-2 navigation, so the recorded video genuinely shows the
            # pagination the narration describes (not just a single static page).
            "MAX_PAGES": 2,
            "MAX_RECORDS": 24,
            "HEADLESS": "true",
            "SCREENSHOTS_ENABLED": "true",
        },
    )
    if main_result["returncode"] != 0:
        log("ERROR: `python main.py` exited non-zero. Not generating a video around a failed run.")
        log(main_result["log_text"][-3000:])
        return 1
    if not main_result["webm_path"]:
        log("ERROR: no Playwright video was recorded (RECORD_VIDEO_DIR produced no .webm).")
        return 1
    log(f"  real run OK. JSON: {main_result['json_path'].name}, video: {main_result['webm_path'].name}")

    # ---- Real execution: python -m pytest -v ----
    log("Running the REAL test suite: python -m pytest -v ...")
    pytest_result = capture.run_real_pytest(PROJECT_ROOT, CAPTURED_DIR / "pytest_run.log")
    if pytest_result["returncode"] != 0:
        log("ERROR: pytest reported failures. Not generating a video claiming tests pass.")
        log(pytest_result["log_text"][-3000:])
        return 1
    log("  real test run OK (all tests passed).")

    # ---- Extract real content for Scenes 3-6 ----
    main_log_lines = drop_sensitive_lines([l for l in main_result["log_text"].splitlines() if l.strip()])
    bot_started = next((l for l in main_log_lines if "BOT_STARTED" in l), "")
    bot_completed = next((l for l in main_log_lines if "BOT_COMPLETED" in l), "")
    summary_lines = []
    in_summary = False
    for l in main_result["log_text"].splitlines():
        if "RUN SUMMARY" in l:
            in_summary = True
        if in_summary and l.strip():
            summary_lines.append(l)
        if in_summary and l.strip().startswith("====") and len(summary_lines) > 3:
            break
    summary_lines = drop_sensitive_lines(summary_lines)
    scene3_lines = [truncate(l, 118) for l in ([bot_started, bot_completed] if bot_completed else main_log_lines[-4:])]
    scene3_lines += [""] + [truncate(l, 118) for l in summary_lines[:11]]

    with open(main_result["json_path"], encoding="utf-8") as f:
        real_json = json.load(f)
    # A curated (not truncated-mid-structure) projection of real values -- picks a
    # handful of representative fields rather than dumping the full nested record,
    # so the panel stays legible. Every value below is copied verbatim from the
    # real run's JSON, nothing here is invented.
    safe_summary = dict(real_json["summary"])
    # The real summary's output_file is an absolute local filesystem path
    # (includes the machine's username) -- sanitize to a relative path before
    # this ever appears on screen, same policy as the public docs/ evidence.
    if safe_summary.get("output_file"):
        safe_summary["output_file"] = f"output/{Path(safe_summary['output_file']).name}"
    excerpt = {"run_id": real_json["run_id"], "summary": safe_summary}
    if real_json["records"]:
        rec = real_json["records"][0]["record"]
        sync = real_json["records"][0]["crm_sync"]
        excerpt["sample_record"] = {
            "title": rec["title"],
            "price_amount": rec["price_amount"],
            "price_currency": rec["price_currency"],
            "category": rec["category"],
            "upc": rec["upc"],
            "validation_status": rec["validation_status"],
            "crm_sync": {
                "success": sync["success"],
                "attempts": sync["attempts"],
                "status_code": sync["status_code"],
                "mode": sync["mode"],
            },
        }
    excerpt_text = json.dumps(excerpt, indent=2)

    pytest_clean_lines = drop_sensitive_lines([l for l in pytest_result["log_text"].splitlines() if l.strip()])
    pytest_tail_lines = [truncate(l, 118) for l in pytest_clean_lines][-14:]

    scraper_src = (PROJECT_ROOT / "src" / "browser" / "scraper.py").read_text(encoding="utf-8")
    src_lines = scraper_src.splitlines()
    comment_idx = next((i for i, l in enumerate(src_lines) if "Capture everything we need from the listing cards" in l), None)
    next_href_idx = next((i for i, l in enumerate(src_lines) if "next_href = await self._get_next_page_href(page)" in l), None)
    if comment_idx is not None and next_href_idx is not None:
        # A real, unaltered excerpt: the comment explaining *why*, the start of the
        # per-card snapshot loop, an elided middle (field extraction lines, omitted
        # only for screen space), then the actual next-page resolution it leads to.
        head = src_lines[comment_idx - 1 : comment_idx + 6]
        tail = src_lines[next_href_idx - 1 : next_href_idx + 1]
        # Dedent for display -- this is real, unaltered code deep inside a method;
        # re-indenting an excerpt for legibility (like a diff hunk) doesn't change
        # what it says, just how far right it starts on screen. Dedent head/tail
        # together (before inserting the elision marker) so the common leading
        # whitespace is computed correctly.
        dedented = textwrap.dedent("\n".join(head + tail)).split("\n")
        code_excerpt = "\n".join(dedented[: len(head)] + ["..."] + dedented[len(head) :])
    else:
        code_excerpt = "\n".join(src_lines[:17])

    # ---- Build the 7 scenes ----
    log("Rendering Scene 1: title card...")
    s1 = build_title_scene(
        "scene1",
        kicker="Portfolio work sample",
        title="Playwright → CRM Lead Pipeline",
        subtitle="An AI-assisted Python + Playwright browser automation pipeline",
        bullets=["Python + Playwright", "Claude Code (engineering copilot)", "pytest", "GoHighLevel-style CRM client"],
        footer=REPO_LABEL,
        audio_path=audio_paths[1],
        audio_dur=audio_durs[1],
    )

    log("Rendering Scene 2: real Playwright browser recording...")
    s2 = build_browser_scene(
        "scene2",
        webm_path=main_result["webm_path"],
        audio_path=audio_paths[2],
        audio_dur=audio_durs[2],
        caption="Real Chromium session — books.toscrape.com (public scraping sandbox)",
    )

    log("Rendering Scene 3: real execution results (terminal)...")
    s3 = build_terminal_scene("scene3", scene3_lines, audio_paths[3], audio_durs[3])

    log("Rendering Scene 4: real structured JSON output...")
    s4 = build_code_scene(
        "scene4",
        excerpt_text,
        filename=f"output/{main_result['json_path'].name}  (excerpt)",
        note="Validated records → mapped to CRM contact fields (mock CRM sync shown; live mode requires real GoHighLevel credentials)",
        audio_path=audio_paths[4],
        audio_dur=audio_durs[4],
        is_json=True,
    )

    log("Rendering Scene 5: real pytest run...")
    s5 = build_terminal_scene("scene5", pytest_tail_lines, audio_paths[5], audio_durs[5])

    log("Rendering Scene 6: real source code (pagination fix)...")
    s6 = build_code_scene(
        "scene6",
        code_excerpt,
        filename="src/browser/scraper.py",
        note="Bug found during real execution: “next page” was read after navigating off the listing page. Fixed, rerun, verified.",
        audio_path=audio_paths[6],
        audio_dur=audio_durs[6],
        is_json=False,
    )

    log("Rendering Scene 7: closing title card...")
    s7 = build_title_scene(
        "scene7",
        kicker="Same architecture, different target",
        title="Portable to any portal + GoHighLevel",
        subtitle="Browser automation, validation, and CRM sync stay independent modules",
        bullets=["Swap selectors for a new source site", "Swap the CRM payload mapping", "CRM_MODE=live with real credentials"],
        footer=REPO_LABEL,
        audio_path=audio_paths[7],
        audio_dur=audio_durs[7],
    )

    # ---- Concatenate ----
    log("Concatenating scenes into final MP4...")
    ffmpeg_utils.concat_videos([s1, s2, s3, s4, s5, s6, s7], FINAL_MP4)

    # ---- Inspect result ----
    info = ffmpeg_utils.probe(FINAL_MP4)
    duration = float(info["format"]["duration"])
    v_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    a_stream = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    log("=" * 60)
    log(f"Final video: {FINAL_MP4}")
    log(f"Duration:    {duration:.1f}s")
    log(f"Resolution:  {v_stream['width']}x{v_stream['height']} @ {v_stream.get('r_frame_rate')}")
    log(f"Video codec: {v_stream['codec_name']}")
    log(f"Audio:       {a_stream['codec_name'] if a_stream else 'MISSING'}")
    log("=" * 60)

    frames_dir = CAPTURED_DIR / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i, t in enumerate([1.0, duration * 0.3, duration * 0.55, duration * 0.8, duration - 1.0]):
        ffmpeg_utils.extract_frame(FINAL_MP4, t, frames_dir / f"frame_{i}.png")
    log(f"Sample frames written to {frames_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
