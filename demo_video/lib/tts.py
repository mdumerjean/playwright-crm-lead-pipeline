"""Local, offline, free narration via macOS's built-in `say` command.

No API key, no network call, no cost -- `say` ships with macOS. This is
deliberately the only narration method implemented: if it weren't available
(e.g. non-macOS host), generate_demo.py is expected to stop and report that
narration requires either macOS or an external TTS service, rather than
fabricating narration.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import ffmpeg_utils

DEFAULT_VOICE = "Samantha"  # clear, professional, built into macOS -- no download needed


def is_available() -> bool:
    return shutil.which("say") is not None


def synthesize(text: str, dst_wav: Path, voice: str = DEFAULT_VOICE, rate_wpm: int = 180) -> float:
    """Synthesize `text` to `dst_wav`. Returns the resulting duration in seconds."""
    if not is_available():
        raise RuntimeError(
            "macOS `say` is not available on this system. Narration requires either "
            "running this on macOS, or wiring in an external TTS API/credential -- "
            "which this project deliberately does not do without explicit approval."
        )
    aiff_path = dst_wav.with_suffix(".aiff")
    subprocess.run(
        ["say", "-v", voice, "-r", str(rate_wpm), "-o", str(aiff_path), text],
        check=True,
        capture_output=True,
        text=True,
    )
    ffmpeg_utils.audio_to_wav(aiff_path, dst_wav)
    aiff_path.unlink(missing_ok=True)
    return ffmpeg_utils.duration_seconds(dst_wav)
