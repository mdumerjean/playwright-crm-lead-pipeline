# Demo Video Generator

A local, repeatable pipeline that produces a ~60-90s MP4 demo of this
project from **real execution** -- not slides, not a screen recording of a
manual take, not fabricated logs. Run one command; get a video.

## What it actually captures

| Scene | Content | Source |
|---|---|---|
| 1 | Title card | Static, no execution claims |
| 2 | Browser automation running | **Real Playwright video recording** of the real `python main.py` run's Chromium session (native Playwright `record_video_dir`, not a desktop screen capture) |
| 3 | Execution results | Real `BOT_STARTED`/`BOT_COMPLETED` log lines + the real `RUN SUMMARY` block, exactly as printed by `main.py` |
| 4 | Structured JSON output | Real values from the run's actual `output/run_*.json` (a curated projection of real fields, not the full nested dump -- see below) |
| 5 | Test suite | Real `python -m pytest -v` output tail, including the real `35 passed` line |
| 6 | Engineering/debugging | The real, unaltered source excerpt from `src/browser/scraper.py` around the pagination-state fix (dedented for legibility, elided in the middle with `...`, nothing rewritten) |
| 7 | Closing title card | Static, no execution claims |

Scenes 1 and 7 are the only ones with no execution evidence behind them --
they're plain title cards. Every other scene is built directly from the
output of an actual subprocess run captured moments earlier in the same
script invocation. If either `python main.py` or `python -m pytest -v`
fails or exits non-zero, **the script stops and reports the failure
instead of generating a video** (see `main()` in `generate_demo.py`).

The public demo runs in **mock CRM mode** (`CRM_MODE=mock`, the project
default) -- Scene 4's on-screen note says this explicitly, and the
narration never claims a real GoHighLevel account was used.

## How it works

```
generate_demo.py                 orchestrator / CLI entry point
lib/
  capture.py                     runs `python main.py` and `pytest -v` for real, locates the real
                                  artifacts they produce (JSON, screenshot, Playwright .webm)
  tts.py                         narration via macOS `say` (local, offline, free -- no API key)
  templates.py                   HTML templates: title cards, terminal "typing" reveal,
                                  code/JSON viewers (regex-based syntax coloring, no CDN)
  html_render.py                 renders those templates via Playwright itself:
                                  - screenshot_html() -> static PNG (title/code/JSON scenes)
                                  - record_html_video() -> real recorded .webm of a JS-animated
                                    page (terminal-typing scenes)
                                  - screenshot_html_transparent() -> transparent PNG (caption
                                    overlay for the real browser-recording scene)
  ffmpeg_utils.py                 thin ffmpeg/ffprobe subprocess wrappers: scale/pad to
                                  1920x1080, mild capped speed adjustment, image->video,
                                  audio+video muxing (freeze-frame padding if video is
                                  shorter than its narration), concatenation, frame extraction
narration.txt                    the narration script, split by `## SCENE N` markers
scenes/, audio/, captured/        intermediate artifacts (gitignored, regenerated every run)
output/playwright-automation-demo.mp4   final video (gitignored -- see note below)
```

**Why no desktop screen recording.** The brief for this generator asked to
avoid capturing the whole desktop (risk of stray windows, notifications,
unrelated apps, or personal files ending up on screen). Playwright's own
`record_video_dir` records exactly the browser's rendered viewport --
nothing else on the machine is ever in frame -- and works the same way in
headless mode. Every other scene is a rendered HTML page (title card,
terminal, code/JSON viewer), also screenshotted/recorded by Playwright, so
the *entire* video is built from controlled, isolated surfaces.

**Why a small opt-in change to the app.** `src/config/settings.py` and
`src/browser/scraper.py` gained one new optional field:
`record_video_dir` (env var `RECORD_VIDEO_DIR`). It's unset by default,
which means `python main.py`'s normal behavior, and all 35 existing tests,
are completely unaffected -- confirmed by rerunning the full suite after
the change. This generator sets that env var when it invokes `main.py` so
Playwright records the real session; nothing else about the app changed.

**Privacy/leak filtering.** Real captured terminal output sometimes
contains this machine's absolute filesystem path (e.g. `main.py`'s summary
prints `output_file` as an absolute path, and pytest's own deprecation
warning on stderr includes the venv's absolute path). `generate_demo.py`
explicitly filters out any captured line containing `/Users/` before it
reaches a scene, and separately sanitizes the JSON excerpt's `output_file`
field to a relative path. This was caught and fixed by visually inspecting
extracted frames during development -- see the "inspect frames" step below.

## Narration method

**macOS's built-in `say` command** -- fully local, fully offline, free, no
API key, no network call. Voice: `Samantha` (built into macOS, no extra
download). `lib/tts.py` synthesizes each scene's narration to `.aiff`,
converts to `.wav` via ffmpeg, and measures its real duration with
`ffprobe` -- that measured duration (not a guess) is what drives each
scene's video length, which is why the final video's total length tracks
the narration length almost exactly.

If `say` isn't available (e.g. running this on non-macOS), the script
stops immediately with an explanation rather than fabricating narration or
silently calling an external paid TTS API. Wiring in a paid/cloud TTS
service is a reasonable future option for higher voice quality, but would
need explicit approval and a credential, so it's out of scope here.

## Dependencies

- **Playwright** (already a project dependency -- used here via its
  synchronous API, independent of the app's async usage)
- **ffmpeg / ffprobe** (installed once via `brew install ffmpeg`)
- **macOS `say`** (built into macOS, nothing to install)

No new Python packages were added to `requirements.txt` -- Playwright is
already there for the app itself.

## Exact command to generate the video

```bash
source .venv/bin/activate
python demo_video/generate_demo.py
```

Takes roughly 1-2 minutes (dominated by the two terminal-typing scene
recordings, which hold in real time for their narration's duration, plus
the real `main.py`/`pytest` runs and several ffmpeg encode passes).

Output: `demo_video/output/playwright-automation-demo.mp4`

## How to regenerate it later

Just run the command above again. Every run:
1. Re-runs the real app (`python main.py`, bounded to `MAX_PAGES=2` /
   `MAX_RECORDS=24` against the live site so it also exercises real
   pagination -- see the comment in `generate_demo.py` for why 24) and the
   real test suite, from scratch.
2. Re-synthesizes narration from `narration.txt` (edit that file to change
   what's said -- scene *visuals* are defined in `generate_demo.py`).
3. Re-renders every scene and re-encodes the final MP4.

Nothing is cached between runs (`scenes/`, `audio/`, `captured/`, and
`output/` are cleared at the start of each run), so the output always
reflects a fresh, real execution.

## What's tracked in git vs. regenerated

Only the generator source (`generate_demo.py`, `lib/`, `narration.txt`,
this README) is tracked. `scenes/`, `audio/`, `captured/`, and
`output/*.mp4` are gitignored -- they're large, binary, and fully
reproducible by rerunning the command above, matching how `output/*.json`
and `screenshots/*.png` are already handled at the project root. If you
want the final MP4 available without regenerating it (e.g. to attach to a
proposal), keep a copy outside the repo or add it via Git LFS/a release
asset rather than committing it directly.

## Known limitations

- Real automation against `books.toscrape.com` is *fast* (a handful of
  seconds for two dozen records), which is shorter than a comfortable
  narration beat for Scene 2. Rather than distorting this into misleading
  fast-motion, playback is slowed by at most 1.8x (labeled on-screen when
  applied) and the remainder of the scene holds on the final real frame
  while narration continues -- a standard, non-deceptive editing technique.
- The regex-based "syntax highlighting" in `lib/templates.py` is
  cosmetic, not a real parser -- fine for the short, hand-picked, real
  code/JSON excerpts shown here, not intended as a general-purpose
  highlighter.
- Narration is a clear but plainly synthetic (non-human) macOS voice; a
  cloud neural TTS service would sound more natural but requires an
  external credential this project deliberately doesn't introduce without
  approval.
