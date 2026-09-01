#!/usr/bin/env python3
"""Render the stats cards as SVGs committed to this repo.

These used to come from the shared github-readme-stats instance, which is
paused often enough that the cards were simply broken on the profile. The data
is already in data/github.json, so draw it here: no third party, no rate
limit, and the cards keep working when someone else's free tier runs out.

Two files per card (light/dark) referenced from a <picture> element, which is
the variant GitHub honours in Markdown.
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import ROOT, info, load_config, read_json  # noqa: E402

ASSETS = ROOT / "assets"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

THEMES = {
    "light": {"fg": "#1f2328", "muted": "#59636e", "border": "#d1d9e0", "track": "#eaeef2"},
    "dark": {"fg": "#f0f6fc", "muted": "#9198a1", "border": "#3d444d", "track": "#2a313c"},
}

W, H, PAD, RADIUS = 440, 196, 20, 8


def frame(theme: dict, title: str, subtitle: str, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" \
viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}">
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="{RADIUS}"
        fill="none" stroke="{theme['border']}"/>
  <text x="{PAD}" y="34" font-family="{FONT}" font-size="15" font-weight="600"
        fill="{theme['fg']}">{escape(title)}</text>
  <text x="{W - PAD}" y="34" font-family="{FONT}" font-size="11"
        fill="{theme['muted']}" text-anchor="end">{escape(subtitle)}</text>
{body}
</svg>
"""


def human(n: int) -> str:
    return f"{n:,}".replace(",", " ")  # thin space, narrower than a comma


def stats_card(theme: dict, gh: dict) -> str:
    c = gh["profile"]["contributions"]
    t = gh["totals"]
    cells = [
        (human(c["lastYearTotal"]), "contributions"),
        (human(c["commits"]), "commits"),
        (human(t["mergedPRs"]), "merged PRs"),
        (human(t["upstreamRepos"]), "upstream repos"),
        (human(t["publicRepos"]), "public repos"),
        (human(t["stars"]), "stars earned"),
    ]
    rows = []
    for i, (value, label) in enumerate(cells):
        x = PAD + (i % 3) * 137
        y = 88 + (i // 3) * 54
        rows.append(
            f'  <text x="{x}" y="{y}" font-family="{FONT}" font-size="22" '
            f'font-weight="600" fill="{theme["fg"]}">{value}</text>\n'
            f'  <text x="{x}" y="{y + 17}" font-family="{FONT}" font-size="11" '
            f'fill="{theme["muted"]}">{label}</text>'
        )
    return frame(theme, "@bcollard", "commits & contributions: last 12 months", "\n".join(rows))


def languages_card(theme: dict, gh: dict, top: int = 8) -> str:
    langs = gh["languages"][:top]
    total = sum(l["share"] for l in langs) or 1

    bar_x, bar_y, bar_w, bar_h = PAD, 58, W - 2 * PAD, 12
    parts = [
        f'  <clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" '
        f'height="{bar_h}" rx="{bar_h / 2}"/></clipPath>',
        f'  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" '
        f'rx="{bar_h / 2}" fill="{theme["track"]}"/>',
        '  <g clip-path="url(#bar)">',
    ]
    offset = 0.0
    for lang in langs:
        width = lang["share"] / total * bar_w
        parts.append(
            f'    <rect x="{bar_x + offset:.2f}" y="{bar_y}" width="{width:.2f}" '
            f'height="{bar_h}" fill="{lang["color"]}"/>'
        )
        offset += width
    parts.append("  </g>")

    for i, lang in enumerate(langs):
        x = PAD + (i % 2) * 205
        y = 104 + (i // 2) * 23
        pct = f"{lang['share'] * 100:.1f}%"
        parts.append(
            f'  <circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{lang["color"]}"/>\n'
            f'  <text x="{x + 17}" y="{y}" font-family="{FONT}" font-size="12" '
            f'fill="{theme["fg"]}">{escape(lang["name"])}</text>\n'
            f'  <text x="{x + 180}" y="{y}" font-family="{FONT}" font-size="12" '
            f'fill="{theme["muted"]}" text-anchor="end">{pct}</text>'
        )
    return frame(theme, "Languages", "by bytes, public repos", "\n".join(parts))


CARDS = {"stats": stats_card, "languages": languages_card}


def main() -> None:
    load_config()
    gh = read_json("github.json")
    ASSETS.mkdir(parents=True, exist_ok=True)

    written = []
    for name, render in CARDS.items():
        for theme_name, theme in THEMES.items():
            path = ASSETS / f"{name}-{theme_name}.svg"
            svg = render(theme, gh)
            if not path.exists() or path.read_text() != svg:
                path.write_text(svg)
                written.append(path.name)
    info(f"cards: {'updated ' + ', '.join(written) if written else 'no changes'}")
    print(ASSETS)


if __name__ == "__main__":
    main()
