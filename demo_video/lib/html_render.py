"""Renders the HTML templates in lib/templates.py using Playwright itself.

Two modes:
- `screenshot_html`: one static PNG (for title cards -> looped into video by ffmpeg).
- `record_html_video`: opens the page in a video-recording context and holds
  it for `hold_seconds`, producing a real .webm of the (JS-animated) page --
  used for the terminal-typing scenes so the "typing" is an actual recorded
  render, not an after-the-fact overlay.

This reuses the same Playwright installation as the main application but is
otherwise fully independent of it (no imports from src/), per the
requirement to keep video-generation tooling separate from the app.
"""
from __future__ import annotations

import glob
import os
import shutil
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

WIDTH = 1920
HEIGHT = 1080


def screenshot_html(html_str: str, out_png: Path) -> Path:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.set_content(html_str, wait_until="load")
        page.screenshot(path=str(out_png))
        browser.close()
    return out_png


def screenshot_html_transparent(html_str: str, out_png: Path) -> Path:
    """Like screenshot_html, but preserves alpha transparency (page background
    must be `transparent`/rgba-alpha-0) -- used for the caption-overlay PNGs
    composited onto real video via ffmpeg's `overlay` filter."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.set_content(html_str, wait_until="load")
        page.screenshot(path=str(out_png), omit_background=True)
        browser.close()
    return out_png


def record_html_video(html_str: str, out_dir: Path, hold_seconds: float) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Playwright names the video file itself (a generated hash); record into
    # an isolated temp subdir so we can unambiguously find the one file produced.
    tmp_video_dir = Path(tempfile.mkdtemp(prefix="rec_", dir=str(out_dir)))
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                viewport={"width": WIDTH, "height": HEIGHT},
                record_video_dir=str(tmp_video_dir),
                record_video_size={"width": WIDTH, "height": HEIGHT},
            )
            page = context.new_page()
            page.set_content(html_str, wait_until="load")
            page.wait_for_timeout(int(hold_seconds * 1000))
            context.close()
            browser.close()

        webm_files = glob.glob(str(tmp_video_dir / "*.webm"))
        if not webm_files:
            raise RuntimeError(f"Playwright did not produce a video in {tmp_video_dir}")
        final_path = out_dir / f"{out_dir.name}_{os.path.basename(webm_files[0])}"
        shutil.move(webm_files[0], final_path)
        return final_path
    finally:
        shutil.rmtree(tmp_video_dir, ignore_errors=True)
