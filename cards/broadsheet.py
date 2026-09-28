#!/usr/bin/env python3
"""
The Still Signal social cards, Broadsheet house style (cream paper, Peacock accent).

Reads a social.json and writes, next to it:
  li-01.jpg ... li-NN.jpg   1080x1350 carousel slides (cover, stories, Still Signal, CTA)
  li-carousel.pdf           the same slides as one PDF, for a LinkedIn document post
  x-card.jpg                1200x675 card for X and the Substack cover
  status.json               {"ok": true, ...} or {"ok": false, "error": "..."} for the pipeline to poll

Usage: python cards/broadsheet.py social/2026-09-28/social.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

from PIL import Image

from engine import (DISP, NUM, PLEX, FitError, Style, cap_height, fit, hline, logo, one_line, rect,
                    render_png, svg_doc, svg_text_lines, text_width, tokenize, wrap_balanced)

PAPER, INK, ACCENT, GREY = "#F1EBDF", "#151412", "#0B6E80", "#6E685D"  # accent: Peacock
W, H, M = 1080, 1350, 80
CW = W - 2 * M


def stack(parts, top, bottom, bias=0.42):
    """parts: [(height, draw(y_top) -> svg)]. Places the stack in the optical centre of [top, bottom]."""
    y = top + max(0, (bottom - top - sum(h for h, _ in parts)) * bias)
    out = []
    for h, draw in parts:
        out.append(draw(y))
        y += h
    return "\n".join(out)


def text_block(lines, size, lh, st, est=None, x=M, anchor="start"):
    h = cap_height(st, size) + (len(lines) - 1) * lh + size * 0.26
    return h, (lambda y: svg_text_lines(lines, x, y + cap_height(st, size), size, lh, st, est, anchor))


def gap(h):
    return h, (lambda y: "")


def ornament(x, y, anchor="start"):
    """Three accent squares: the house mark that stands in where a number would be."""
    s, g = 16, 10
    x0 = x - (3 * s + 2 * g) / 2 if anchor == "middle" else x
    return "\n".join(rect(x0 + i * (s + g), y, s, s, ACCENT) for i in range(3))


def masthead(d, right):
    dt = date.fromisoformat(d["date"])
    return "\n".join([
        logo(M, 52, 44),
        one_line("The Still Signal", M + 58, 88, 40, Style(DISP, fill=INK)),
        one_line(f"No. {d['issue']}", W - M, 86, 22, Style(PLEX, 600, fill=INK), anchor="end"),
        rect(M, 122, CW, 6, INK),
        hline(M, W - M, 136, INK, 1.5),
        one_line(dt.strftime("%A, %d %B %Y").upper(), M, 172, 19, Style(PLEX, 500, tracking=0.04, fill=GREY)),
        one_line(right, W - M, 172, 19, Style(PLEX, 600, tracking=0.04, fill=INK), anchor="end"),
    ])


def footer(idx, total, cue=None):
    out = [hline(M, W - M, 1206, INK, 1.5),
           one_line("nirantar.xyz", M, 1262, 32, Style(DISP, style="italic", fill=INK))]
    if cue:
        out.append(one_line(cue, W - M, 1260, 24, Style(PLEX, 700, tracking=0.04, fill=ACCENT), anchor="end"))
    else:
        s, g = 14, 8
        x0 = W - M - total * s - (total - 1) * g
        for i in range(total):
            fill, op = (ACCENT, 1) if i == idx else (INK, 0.85 if i < idx else 0.18)
            out.append(rect(x0 + i * (s + g), 1242, s, s, fill, op))
    return "\n".join(out)


def slide_cover(d, total):
    t_st, t_em = Style(DISP, fill=INK), Style(DISP, style="italic", fill=ACCENT)
    k_st = Style(DISP, style="italic", fill=GREY)
    k_size, k_lines = fit("dek", d["dek"], k_st, [40, 36, 33], CW, 3)
    item_st, num_st = Style(DISP, fill=INK), Style(PLEX, 600, fill=ACCENT)
    stories = d["stories"]
    for s in stories:
        if text_width(s["short"], item_st, 32) > CW - 110:
            raise FitError(f"'stories[].short' too long for one line: {s['short']!r}")

    # the title is the hook: biggest title that fits, then as many index rows as remain
    choice = None
    for t_size in [150, 134, 120, 106, 96, 86]:
        t_lines = wrap_balanced(tokenize(d["title"]), t_st, t_em, t_size, CW)
        if t_lines is None or len(t_lines) > 3:
            continue
        head_h = (cap_height(t_st, t_size) + (len(t_lines) - 1) * t_size + t_size * 0.3 + 30
                  + cap_height(k_st, k_size) + (len(k_lines) - 1) * k_size * 1.3 + 60)
        for n in sorted({min(len(stories), k) for k in (6, 5, 4, 3)}, reverse=True):
            rows = n + (1 if len(stories) > n else 0)
            if head_h + 50 + rows * 32 * 1.75 <= 1180 - 236:
                choice = (t_size, t_lines, n)
                break
        if choice:
            break
    if not choice:
        raise FitError("cover: title + dek + index do not fit together; shorten the title or dek")
    t_size, t_lines, n = choice

    body = [masthead(d, "TODAY'S EDITION")]
    y0 = 236 + cap_height(t_st, t_size)
    body.append(svg_text_lines(t_lines, M, y0, t_size, t_size, t_st, t_em))
    y = y0 + (len(t_lines) - 1) * t_size + t_size * 0.3 + 30
    body.append(svg_text_lines(k_lines, M, y + cap_height(k_st, k_size), k_size, k_size * 1.3, k_st))

    rows = n + (1 if len(stories) > n else 0)
    ly = 1180 - 50 - rows * 32 * 1.75
    body.append(rect(M, ly - 6, 150, 36, INK))
    body.append(one_line("INSIDE", M + 18, ly + 19, 20, Style(PLEX, 700, tracking=0.12, fill=PAPER)))
    ly += 50
    for i, s in enumerate(stories[:n]):
        by = ly + (i + 1) * 32 * 1.75 - 16
        tw = text_width(s["short"], item_st, 32)
        body.append(one_line(s["short"], M, by, 32, item_st))
        body.append(hline(M + tw + 14, W - M - 56, by - 4, INK, 2, "1 7"))
        body.append(one_line(f"{i + 2:02d}", W - M, by, 22, num_st, anchor="end"))
    if len(stories) > n:
        by = ly + (n + 1) * 32 * 1.75 - 16
        body.append(one_line(f"and {len(stories) - n} more inside", M, by, 32, Style(DISP, style="italic", fill=GREY)))
    body.append(footer(0, total, cue="TURN THE PAGE  →"))
    return svg_doc(W, H, PAPER, "\n".join(body))


def slide_story(d, s, idx, total, n):
    body = [masthead(d, f"STORY {idx:02d} OF {n:02d}")]
    sec = s["section"].upper()
    sec_st = Style(PLEX, 700, tracking=0.1, fill=PAPER)
    body.append(rect(M, 214, text_width(sec, sec_st, 20) + 36, 38, INK))
    body.append(one_line(sec, M + 18, 240, 20, sec_st))

    hed_st = Style(DISP, fill=INK)
    if s.get("number"):
        n_st = Style(NUM, fill=ACCENT)
        n_size, _ = fit("number", s["number"], n_st, [330, 290, 250, 214, 184, 156, 132], CW, 1)
        l_st = Style(PLEX, 500, fill=INK)
        l_size, l_lines = fit("label", s["label"], l_st, [30, 28, 26, 24], CW, 3)
        h_size, h_lines = fit("headline", s["headline"], hed_st, [80, 72, 64, 58, 52], CW, 5)
        n_cap = cap_height(n_st, n_size)
        parts = [
            (n_cap + n_size * 0.08, lambda y: one_line(s["number"], M - n_size * 0.02, y + n_cap, n_size, n_st)),
            gap(30), (4, lambda y: hline(M, W - M, y, INK, 1.5)), gap(30),
            text_block(l_lines, l_size, l_size * 1.4, l_st), gap(46),
            text_block(h_lines, h_size, h_size * 1.08, hed_st),
        ]
    else:
        h_size, h_lines = fit("headline", s["headline"], hed_st, [116, 104, 92, 82, 72, 64], CW, 6)
        parts = [(16, lambda y: ornament(M, y)), gap(44), text_block(h_lines, h_size, h_size * 1.04, hed_st)]
    body.append(stack(parts, 290, 1180))
    body.append(footer(idx, total))
    return svg_doc(W, H, PAPER, "\n".join(body))


def slide_signal(d, idx, total):
    q_st = Style(DISP, style="italic", fill=INK)
    q_size, q_lines = fit("still_signal", d["still_signal"], q_st, [74, 66, 60, 54, 48], CW, 9)
    parts = [
        (20, lambda y: one_line("THE STILL SIGNAL", M, y + 20, 22, Style(PLEX, 700, tracking=0.14, fill=ACCENT))),
        gap(56),
        text_block(q_lines, q_size, q_size * 1.14, q_st),
        gap(56),
        (16, lambda y: ornament(M, y)),
    ]
    body = [masthead(d, "THE CLOSE"), stack(parts, 236, 1180, 0.45), footer(idx, total)]
    return svg_doc(W, H, PAPER, "\n".join(body))


def slide_cta(d, idx, total):
    body = [masthead(d, "THE FULL EDITION")]
    body.append(ornament(W / 2, 380, anchor="middle"))
    body.append(one_line("Read the", W / 2, 520, 130, Style(DISP, fill=INK), anchor="middle"))
    body.append(one_line("full issue.", W / 2, 650, 130, Style(DISP, style="italic", fill=ACCENT), anchor="middle"))
    t = f"No. {d['issue']} · {d['title'].replace('*', '')}"
    t_size, t_lines = fit("cta title", t, Style(PLEX, 500, fill=GREY), [26, 24, 22], CW, 1)
    body.append(svg_text_lines(t_lines, W / 2, 740, t_size, 0, Style(PLEX, 500, fill=GREY), anchor="middle"))
    body.append(rect(W / 2 - 260, 820, 520, 110, INK))
    body.append(one_line("nirantar.xyz", W / 2, 894, 50, Style(DISP, fill=PAPER), anchor="middle"))
    body.append(one_line("Daily AI analysis. Beyond the noise.", W / 2, 1010, 30,
                         Style(DISP, style="italic", fill=INK), anchor="middle"))
    body.append(footer(idx, total))
    return svg_doc(W, H, PAPER, "\n".join(body))


def x_card(d):
    XW, XH, XM = 1200, 675, 60
    dt = date.fromisoformat(d["date"])
    t_st, t_em = Style(DISP, fill=INK), Style(DISP, style="italic", fill=ACCENT)
    t_size, t_lines = fit("x title", d["title"], t_st, [112, 100, 88, 78, 68], 600, 3, t_em)
    body = [
        logo(XM, 40, 40),
        one_line("The Still Signal", XM + 52, 72, 34, Style(DISP, fill=INK)),
        one_line(f"No. {d['issue']} · {dt.strftime('%d %b %Y').upper()}", XW - XM, 70, 19,
                 Style(PLEX, 600, fill=INK), anchor="end"),
        rect(XM, 98, XW - 2 * XM, 5, INK), hline(XM, XW - XM, 110, INK, 1.5),
    ]
    blk = cap_height(t_st, t_size) + (len(t_lines) - 1) * t_size
    y0 = 140 + max(0, (400 - blk) * 0.45) + cap_height(t_st, t_size)
    body.append(svg_text_lines(t_lines, XM, y0, t_size, t_size, t_st, t_em))
    body.append(one_line("nirantar.xyz", XM, XH - 50, 30, Style(DISP, style="italic", fill=INK)))

    cx = 730
    cw = XW - XM - cx
    body.append(f'<line x1="{cx - 40}" y1="140" x2="{cx - 40}" y2="{XH - 40}" stroke="{INK}" stroke-width="1.5"/>')
    body.append(one_line("BY THE NUMBERS", cx, 160, 18, Style(PLEX, 700, tracking=0.12, fill=GREY)))
    picks = [s for s in (d["stories"][i] for i in d.get("x_card_numbers", []) if i < len(d["stories"])) if s.get("number")]
    picks = (picks or [s for s in d["stories"] if s.get("number")])[:3]
    slot = (XH - 40 - 180) / max(len(picks), 1)
    for i, s in enumerate(picks):
        top = 180 + i * slot
        n_st, l_st = Style(NUM, fill=ACCENT), Style(PLEX, 500, fill=INK)
        n_size, _ = fit("x number", s["number"], n_st, [76, 66, 58, 50, 44], cw, 1)
        l_size, l_lines = fit("x label", s["label"], l_st, [17, 16, 15], cw, 2)
        nb = top + cap_height(n_st, n_size)
        body.append(one_line(s["number"], cx, nb, n_size, n_st))
        body.append(svg_text_lines(l_lines, cx, nb + 30, l_size, l_size * 1.35, l_st))
        if i:
            body.append(hline(cx, XW - XM, top - 14, INK, 1, "1 6"))
    return svg_doc(XW, XH, PAPER, "\n".join(body))


# ── Validation + orchestration ────────────────────────────────────────────────
REQUIRED = ["issue", "date", "title", "dek", "stories", "still_signal"]


def validate(d):
    problems = [f"missing '{k}'" for k in REQUIRED if not d.get(k)]

    def walk(v, path):
        if isinstance(v, str) and "—" in v:
            problems.append(f"em dash in {path}")
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}")
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{path}[{i}]")

    walk(d, "social")
    stories = d.get("stories") or []
    if not 1 <= len(stories) <= 10:
        problems.append("stories must have 1-10 items")
    for i, s in enumerate(stories):
        for k in ("section", "short", "headline"):
            if not s.get(k):
                problems.append(f"stories[{i}] missing '{k}'")
        if s.get("number") and not s.get("label"):
            problems.append(f"stories[{i}] has a number but no label")
    if problems:
        raise FitError("; ".join(problems))


def render(d, out: Path) -> list[Path]:
    validate(d)
    stories = d["stories"]
    total = len(stories) + 3
    svgs = ([slide_cover(d, total)]
            + [slide_story(d, s, i + 1, total, len(stories)) for i, s in enumerate(stories)]
            + [slide_signal(d, total - 2, total), slide_cta(d, total - 1, total)])
    x_svg = x_card(d)  # fit everything before writing anything

    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("li-*.jpg"):
        old.unlink()
    jpg = dict(quality=90, optimize=True, progressive=True, subsampling=0)
    slides, files = [], []
    for i, svg in enumerate(svgs, 1):
        im = Image.open(__import__("io").BytesIO(render_png(svg))).convert("RGB")
        p = out / f"li-{i:02d}.jpg"
        im.save(p, **jpg)
        slides.append(im)
        files.append(p)
    slides[0].save(out / "li-carousel.pdf", save_all=True, append_images=slides[1:], resolution=144, quality=88)
    Image.open(__import__("io").BytesIO(render_png(x_svg))).convert("RGB").save(out / "x-card.jpg", **jpg)
    return files + [out / "li-carousel.pdf", out / "x-card.jpg"]


def main(path: str) -> int:
    src = Path(path)
    raw = src.read_bytes()
    status = {"json_sha256": hashlib.sha256(raw).hexdigest()}
    try:
        d = json.loads(raw)
        d = d.get("social", d)
        files = render(d, src.parent)
        status.update(ok=True, slides=len(files) - 2, files=[f.name for f in files])
        code = 0
    except (FitError, ValueError, KeyError) as e:
        status.update(ok=False, error=f"{type(e).__name__}: {e}")
        code = 1
    (src.parent / "status.json").write_text(json.dumps(status, indent=2))
    print(json.dumps(status, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
