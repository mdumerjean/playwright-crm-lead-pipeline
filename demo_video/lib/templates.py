"""HTML templates rendered by Playwright into screenshots/videos.

Deliberately simple, dependency-free "syntax highlighting" (regex-based, not
a real parser) -- good enough for short, hand-picked, real code/log/JSON
excerpts shown briefly on screen. No external CDN/network dependency: fonts
and styling are all system fonts + inline CSS, so rendering works fully
offline.
"""
from __future__ import annotations

import html
import re

FONT_MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
FONT_SANS = "-apple-system, 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif"

BG = "#0b0f14"
PANEL_BG = "#11161d"
BORDER = "#232b36"
TEXT = "#e6edf3"
DIM = "#8b98a5"
ACCENT = "#4fd1c5"
GREEN = "#7ee787"
AMBER = "#e3b341"
RED = "#ff7b72"
BLUE = "#79c0ff"
PURPLE = "#d2a8ff"

BASE_CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 1920px; height: 1080px; background: {BG}; overflow: hidden; }}
body {{ font-family: {FONT_SANS}; color: {TEXT}; }}
.window {{
  position: absolute; inset: 0; display: flex; flex-direction: column;
}}
.chrome {{
  display: flex; align-items: center; gap: 10px;
  padding: 22px 28px; background: {PANEL_BG}; border-bottom: 1px solid {BORDER};
}}
.dot {{ width: 16px; height: 16px; border-radius: 50%; }}
.dot.red {{ background: #ff5f57; }}
.dot.yellow {{ background: #febc2e; }}
.dot.green {{ background: #28c840; }}
.chrome-title {{
  margin-left: 18px; font-family: {FONT_MONO}; font-size: 20px; color: {DIM};
}}
.body {{ flex: 1; padding: 48px 56px; font-family: {FONT_MONO}; font-size: 26px; line-height: 1.55; overflow: hidden; }}
"""


def _wrap(inner: str, extra_css: str = "") -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{BASE_CSS}{extra_css}</style></head>
<body>{inner}</body></html>"""


def title_card(kicker: str, title: str, subtitle: str, bullets: list, footer: str) -> str:
    bullet_html = "".join(f'<div class="bullet"><span class="dot-b"></span>{html.escape(b)}</div>' for b in bullets)
    css = f"""
    .center {{ position:absolute; inset:0; display:flex; flex-direction:column; justify-content:center; padding: 0 160px; }}
    .kicker {{ font-family:{FONT_MONO}; color:{ACCENT}; font-size:28px; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 22px; }}
    .title {{ font-size: 76px; font-weight: 700; line-height: 1.15; margin-bottom: 26px; }}
    .subtitle {{ font-size: 32px; color: {DIM}; margin-bottom: 44px; max-width: 1400px; }}
    .bullet {{ font-family:{FONT_MONO}; font-size: 27px; color:{TEXT}; margin-bottom: 14px; display:flex; align-items:center; }}
    .dot-b {{ width:10px; height:10px; border-radius:50%; background:{GREEN}; margin-right:16px; flex-shrink:0; }}
    .footer {{ position:absolute; bottom: 56px; left: 160px; right:160px; font-family:{FONT_MONO}; font-size:22px; color:{DIM}; border-top:1px solid {BORDER}; padding-top:22px; }}
    """
    inner = f"""
    <div class="center">
      <div class="kicker">{html.escape(kicker)}</div>
      <div class="title">{html.escape(title)}</div>
      <div class="subtitle">{html.escape(subtitle)}</div>
      <div class="bullets">{bullet_html}</div>
    </div>
    <div class="footer">{html.escape(footer)}</div>
    """
    return _wrap(inner, css)


_LOG_LEVEL_COLOR = {"INFO": GREEN, "WARNING": AMBER, "ERROR": RED}


def _colorize_log_line(line: str) -> str:
    escaped = html.escape(line)
    m = re.match(r"^(\S+) \| (INFO|WARNING|ERROR)\s+\| (\S+)\s+\| (.*)$", line)
    if not m:
        return f'<span class="line">{escaped}</span>'
    ts, level, stage, msg = m.groups()
    color = _LOG_LEVEL_COLOR.get(level, TEXT)
    return (
        f'<span class="line">'
        f'<span style="color:{DIM}">{html.escape(ts)}</span> | '
        f'<span style="color:{color}; font-weight:600">{level:<8}</span> | '
        f'<span style="color:{BLUE}">{stage:<24}</span> | '
        f'<span>{html.escape(msg)}</span>'
        f'</span>'
    )


def terminal_typing(lines: list, target_seconds: float, window_title: str = "zsh — playwright-automation-demo") -> str:
    """A terminal window that reveals `lines` one at a time via JS, paced to
    finish (with a short trailing hold) within `target_seconds`.

    The caller is still responsible for keeping the recording context open
    for approximately `target_seconds` before closing it -- this only paces
    the *visual* reveal to match.
    """
    colorized = [
        f'<span class="prompt-line">{html.escape(l)}</span>' if l.startswith("$") else _colorize_log_line(l)
        for l in lines
    ]
    lines_json = "[" + ",".join('"' + c.replace("\\", "\\\\").replace('"', "&quot;") + '"' for c in colorized) + "]"
    num_lines = max(len(lines), 1)
    hold_ms = 900
    reveal_budget_ms = max(300, target_seconds * 1000 - hold_ms)
    line_ms = int(reveal_budget_ms / num_lines)

    css = f"""
    .term-body {{ font-size: 24px; line-height: 1.65; white-space: pre-wrap; word-break: break-word; }}
    .cursor {{ display:inline-block; width:13px; height:26px; background:{TEXT}; vertical-align:-4px; animation: blink 1s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    .prompt-line {{ color: {PURPLE}; }}
    """
    inner = f"""
    <div class="window">
      <div class="chrome">
        <div class="dot red"></div><div class="dot yellow"></div><div class="dot green"></div>
        <div class="chrome-title">{html.escape(window_title)}</div>
      </div>
      <div class="body term-body" id="out"></div>
    </div>
    <script>
      const lines = {lines_json};
      const lineMs = {line_ms};
      const out = document.getElementById('out');
      let li = 0;
      function typeNext() {{
        if (li >= lines.length) {{
          const c = document.createElement('span'); c.className = 'cursor'; out.appendChild(c);
          return;
        }}
        const div = document.createElement('div');
        div.innerHTML = lines[li];
        div.style.opacity = 0;
        out.appendChild(div);
        requestAnimationFrame(() => {{ div.style.transition = 'opacity 120ms'; div.style.opacity = 1; }});
        li += 1;
        setTimeout(typeNext, lineMs);
      }}
      typeNext();
    </script>
    """
    return _wrap(inner, css)


def caption_overlay(caption: str, speed_label: str = "") -> str:
    """A fully transparent 1920x1080 page with just a bottom caption bar (and
    optional top-right badge) -- meant to be screenshotted with a transparent
    background and composited over real video footage via ffmpeg's `overlay`
    filter (this avoids needing ffmpeg's `drawtext`, which this Homebrew build
    doesn't include)."""
    badge_html = (
        f'<div class="badge">{html.escape(speed_label)}</div>' if speed_label else ""
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 1920px; height: 1080px; background: transparent; }}
body {{ font-family: {FONT_MONO}; }}
.bar {{ position:absolute; left:0; right:0; bottom:0; height:76px; background: rgba(0,0,0,0.55);
        display:flex; align-items:center; padding: 0 32px; color:#fff; font-size:28px; }}
.badge {{ position:absolute; top:24px; right:24px; background: rgba(0,0,0,0.5); color:#fff;
          font-size:22px; padding:8px 14px; border-radius:6px; }}
</style></head>
<body>
  <div class="bar">{html.escape(caption)}</div>
  {badge_html}
</body></html>"""


def _highlight_python(code: str) -> str:
    escaped = html.escape(code, quote=False)
    lines_out = []
    keyword_re = re.compile(
        r"\b(async|await|def|class|return|if|elif|else|for|while|try|except|finally|"
        r"import|from|as|with|in|not|and|or|is|None|True|False|self|raise|pass|break|continue|lambda)\b"
    )
    string_re = re.compile(r"(&quot;.*?&quot;|'[^']*'|f'[^']*'|f&quot;.*?&quot;)")
    comment_re = re.compile(r"(#.*)$")
    for line in escaped.split("\n"):
        comment_match = comment_re.search(line)
        comment = ""
        if comment_match:
            comment = f'<span style="color:{DIM}">{comment_match.group(1)}</span>'
            line = line[: comment_match.start()]
        line = string_re.sub(lambda m: f'<span style="color:{GREEN}">{m.group(0)}</span>', line)
        line = keyword_re.sub(lambda m: f'<span style="color:{PURPLE}">{m.group(0)}</span>', line)
        lines_out.append(line + comment)
    return "\n".join(lines_out)


def code_viewer(code: str, filename: str, note: str = "") -> str:
    highlighted = _highlight_python(code)
    numbered = "\n".join(
        f'<span class="ln">{i + 1:>3}</span>  {l}' for i, l in enumerate(highlighted.split("\n"))
    )
    css = f"""
    .code-body {{ font-size: 24px; line-height: 1.7; white-space: pre; padding-bottom: 130px; }}
    .ln {{ color: {DIM}; user-select: none; }}
    .note {{ position:absolute; bottom:40px; left:56px; right:56px; font-family:{FONT_SANS}; font-size:24px; color:{DIM};
             border-top:1px solid {BORDER}; padding-top:18px; background:{BG}; }}
    """
    inner = f"""
    <div class="window">
      <div class="chrome">
        <div class="dot red"></div><div class="dot yellow"></div><div class="dot green"></div>
        <div class="chrome-title">{html.escape(filename)}</div>
      </div>
      <div class="body code-body">{numbered}</div>
      {f'<div class="note">{html.escape(note)}</div>' if note else ""}
    </div>
    """
    return _wrap(inner, css)


def _highlight_json(text: str) -> str:
    escaped = html.escape(text, quote=False)

    def repl(m):
        s = m.group(0)
        if s.endswith(":"):
            return f'<span style="color:{BLUE}">{s[:-1]}</span>:'
        if s in ("true", "false", "null"):
            return f'<span style="color:{PURPLE}">{s}</span>'
        try:
            float(s)
            return f'<span style="color:{AMBER}">{s}</span>'
        except ValueError:
            return f'<span style="color:{GREEN}">{s}</span>'

    pattern = re.compile(r'"(?:[^"\\]|\\.)*"\s*:|"(?:[^"\\]|\\.)*"|\btrue\b|\bfalse\b|\bnull\b|-?\d+\.?\d*')
    return pattern.sub(repl, escaped)


def json_viewer(json_text: str, filename: str, note: str = "") -> str:
    highlighted = _highlight_json(json_text)
    css = f"""
    .code-body {{ font-size: 20px; line-height: 1.4; white-space: pre; padding-bottom: 130px; }}
    .note {{ position:absolute; bottom:40px; left:56px; right:56px; font-family:{FONT_SANS}; font-size:22px; color:{DIM};
             border-top:1px solid {BORDER}; padding-top:18px; background:{BG}; }}
    """
    inner = f"""
    <div class="window">
      <div class="chrome">
        <div class="dot red"></div><div class="dot yellow"></div><div class="dot green"></div>
        <div class="chrome-title">{html.escape(filename)}</div>
      </div>
      <div class="body code-body">{highlighted}</div>
      {f'<div class="note">{html.escape(note)}</div>' if note else ""}
    </div>
    """
    return _wrap(inner, css)
