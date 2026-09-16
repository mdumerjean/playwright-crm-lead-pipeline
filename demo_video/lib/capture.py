"""Runs the REAL application and REAL test suite, and locates the real
artifacts they produce. Nothing in this module fabricates output -- every
string returned here is exactly what the subprocess actually printed, and
every file path returned is a file that subprocess actually wrote.
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _newest(pattern: str) -> Optional[Path]:
    matches = glob.glob(pattern)
    if not matches:
        return None
    return Path(max(matches, key=os.path.getmtime))


def run_real_main(project_root: Path, video_dir: Path, log_path: Path, env_overrides: dict) -> dict:
    """Actually runs `python main.py` against the live site with the given env
    overrides (e.g. a smaller MAX_RECORDS for a tighter video clip -- still
    the real app, real network calls, real Playwright browser).
    """
    env = os.environ.copy()
    env.update({k: str(v) for k, v in env_overrides.items()})
    env["RECORD_VIDEO_DIR"] = str(video_dir)

    result = subprocess.run(
        [sys.executable, "main.py"],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
    )
    combined = result.stdout + result.stderr
    log_path.write_text(combined, encoding="utf-8")

    json_path = _newest(str(project_root / "output" / "run_*.json"))
    webm_path = _newest(str(video_dir / "*.webm"))
    screenshot_path = _newest(str(project_root / "screenshots" / "*.png"))

    return {
        "returncode": result.returncode,
        "log_text": combined,
        "json_path": json_path,
        "webm_path": webm_path,
        "screenshot_path": screenshot_path,
    }


def run_real_pytest(project_root: Path, log_path: Path) -> dict:
    """Actually runs `python -m pytest -v`."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    combined = result.stdout + result.stderr
    log_path.write_text(combined, encoding="utf-8")
    return {"returncode": result.returncode, "log_text": combined}
