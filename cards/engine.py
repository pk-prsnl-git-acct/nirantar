"""
Text fitting + SVG primitives for the Still Signal social cards.

Every text slot has a font-size ladder and a max line count. Words never break,
wrapping is balanced, and copy that cannot fit at the smallest rung raises
FitError naming the field, so the pipeline can shorten it instead of shipping
an unreadable card.
"""

from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import resvg_py
from PIL import Image, ImageFont

HERE = Path(__file__).parent
FONT_DIR = HERE / "fonts"
LOGO_PNG = HERE.parent / "assets" / "Nirantar_logo.png"

DISP, NUM, PLEX = "DM Serif Display", "Anton", "IBM Plex Mono"
FONT_FILES = {
    (DISP, 400, "normal"): "DMSerifDisplay-Regular.ttf",
    (DISP, 400, "italic"): "DMSerifDisplay-Italic.ttf",
    (NUM, 400, "normal"): "Anton-Regular.ttf",
    (PLEX, 500, "normal"): "IBMPlexMono-Medium.ttf",
    (PLEX, 600, "normal"): "IBMPlexMono-SemiBold.ttf",
    (PLEX, 700, "normal"): "IBMPlexMono-Bold.ttf",
}


class FitError(ValueError):
    """Copy for a named field does not fit its slot at the smallest allowed size."""


@dataclass
class Style:
    family: str
    weight: int = 400
    style: str = "normal"
    tracking: float = 0.0  # em
    fill: str = "#000000"


_font_cache: dict = {}


def _font(st: Style, size) -> ImageFont.FreeTypeFont:
    key = (st.family, st.weight, st.style, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(FONT_DIR / FONT_FILES[key[:3]]), size)
    return _font_cache[key]


def text_width(text: str, st: Style, size) -> float:
    return _font(st, size).getlength(text) + st.tracking * size * max(len(text) - 1, 0)


def cap_height(st: Style, size) -> float:
    return -_font(st, size).getbbox("H", anchor="ls")[1]


def tokenize(text: str) -> list[tuple[str, bool]]:
    """Split into (word, emphasised) tokens. Emphasis is marked *like this*."""
    out, emph = [], False
    for part in re.split(r"(\*)", text):
        if part == "*":
            emph = not emph
            continue
        out += [(w, emph) for w in part.split()]
    return out


def _greedy(tokens, st, est, size, width):
    space = text_width(" ", st, size)
    lines, cur, cur_w = [], [], 0.0
    for word, emph in tokens:
        w = text_width(word, est if emph else st, size)
        if w > width:
            return None  # never break a word
        add = w if not cur else cur_w + space + w
        if cur and add > width:
            lines.append(cur)
            cur, cur_w = [(word, emph)], w
        else:
            cur, cur_w = cur + [(word, emph)], add
    if cur:
        lines.append(cur)
    return lines


def wrap_balanced(tokens, st, est, size, width):
    """Greedy wrap, then narrow the measure while the line count holds (CSS text-wrap: balance)."""
    base = _greedy(tokens, st, est, size, width)
    if base is None or len(base) == 1:
        return base
    lo, hi, best = width * 0.5, width, base
    for _ in range(14):
        mid = (lo + hi) / 2
        trial = _greedy(tokens, st, est, size, mid)
        if trial is not None and len(trial) == len(base):
            best, hi = trial, mid
        else:
            lo = mid
    return best


def fit(field, text, st, ladder, width, max_lines, est=None):
    """Largest rung of the ladder at which the text fits. Returns (size, lines)."""
    tokens = tokenize(text)
    for size in ladder:
        lines = wrap_balanced(tokens, st, est or st, size, width)
        if lines is not None and len(lines) <= max_lines:
            return size, lines
    raise FitError(f"'{field}' does not fit in {max_lines} line(s) at {ladder[-1]}px: {text!r}")


def svg_text_lines(lines, x, y_first_baseline, size, lh, st, est=None, anchor="start"):
    est = est or st
    out = []
    for i, line in enumerate(lines):
        spans = []
        for j, (word, emph) in enumerate(line):
            s = est if emph else st
            spans.append(
                f'<tspan font-family="{s.family}" font-weight="{s.weight}" font-style="{s.style}" '
                f'fill="{s.fill}">{escape((" " if j else "") + word)}</tspan>'
            )
        ls = f' letter-spacing="{st.tracking * size:.2f}"' if st.tracking else ""
        out.append(f'<text x="{x:.1f}" y="{y_first_baseline + i * lh:.1f}" font-size="{size}" '
                   f'text-anchor="{anchor}"{ls}>{"".join(spans)}</text>')
    return "\n".join(out)


def one_line(text, x, y, size, st, anchor="start"):
    return svg_text_lines([[(text, False)]], x, y, size, 0, st, anchor=anchor)


def rect(x, y, w, h, fill, op=1):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" opacity="{op}"/>'


def hline(x1, x2, y, color, sw=2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="{sw}"{d}/>'


_logo_uri = None


def logo(x, y, s):
    """The Nirantar mark, clipped to a circle so its dark square never shows."""
    global _logo_uri
    if _logo_uri is None:
        im = Image.open(LOGO_PNG).convert("RGB").crop((190, 170, 1064, 1044)).resize((320, 320), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        _logo_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    cid, r = f"lc{int(x)}_{int(y)}_{int(s)}", s / 2
    return (f'<clipPath id="{cid}"><circle cx="{x + r}" cy="{y + r}" r="{r * 0.99}"/></clipPath>'
            f'<image x="{x}" y="{y}" width="{s}" height="{s}" href="{_logo_uri}" clip-path="url(#{cid})"/>')


def svg_doc(w, h, bg, body, grain=0.06):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs><filter id="grain" x="0" y="0" width="100%" height="100%">
<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/>
<feColorMatrix type="saturate" values="0"/></filter></defs>
<rect width="{w}" height="{h}" fill="{bg}"/>
{body}
<rect width="{w}" height="{h}" filter="url(#grain)" opacity="{grain}"/>
</svg>"""


def render_png(svg: str) -> bytes:
    return bytes(resvg_py.svg_to_bytes(svg_string=svg, font_dirs=[str(FONT_DIR)], skip_system_fonts=True))
