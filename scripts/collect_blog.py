#!/usr/bin/env python3
"""Snapshot the Hugo blog (posts, talks/articles, side projects) into data/blog.json."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import blog_dir, die, info, load_config, write_json  # noqa: E402

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
# Hugo shortcode: {{< project-card key="value" ... >}}body{{< /project-card >}}
CARD = re.compile(
    r"\{\{<\s*project-card\s+(?P<attrs>.*?)>\}\}(?P<body>.*?)\{\{<\s*/project-card\s*>\}\}",
    re.DOTALL,
)
ATTR = re.compile(r'(\w+)="([^"]*)"')
SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def parse_front_matter(text: str) -> dict:
    """Minimal `key: value` front-matter reader — enough for this blog."""
    m = FRONT_MATTER.match(text)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        fields[key.strip()] = value
    return fields


def collect_section(root: Path, section: str, base_url: str) -> list[dict]:
    directory = root / "content" / section
    if not directory.is_dir():
        die(f"blog section not found: {directory}")
    entries = []
    for path in sorted(directory.iterdir()):
        if path.suffix not in {".adoc", ".md"} or path.stem.startswith("_"):
            continue
        fm = parse_front_matter(path.read_text(errors="replace"))
        # Hugo lowercases the filename to build the slug unless overridden.
        slug = fm.get("slug") or path.stem.lower()
        entries.append(
            {
                "slug": slug,
                "title": fm.get("title", path.stem),
                "date": fm.get("date", "")[:10],
                "draft": fm.get("draft", "false").lower() == "true",
                "tags": re.findall(r'"([^"]+)"', fm.get("tags", "")),
                "description": fm.get("description", ""),
                "url": f"{base_url}/{section}/{slug}/",
                "file": str(path.relative_to(root)),
            }
        )
    return sorted(entries, key=lambda e: e["date"], reverse=True)


def collect_side_projects(root: Path) -> list[dict]:
    path = root / "content" / "side-projects" / "_index.md"
    if not path.exists():
        info(f"blog: no side-projects page at {path}, skipping")
        return []
    text = path.read_text(errors="replace")

    # Map each card to the `## ` heading above it.
    headings = [(m.start(), m.group(1)) for m in SECTION.finditer(text)]
    projects = []
    for m in CARD.finditer(text):
        attrs = dict(ATTR.findall(m.group("attrs")))
        section = ""
        for pos, title in headings:
            if pos < m.start():
                section = title
        projects.append(
            {
                "name": attrs.get("name", ""),
                "section": section,
                "status": attrs.get("status", ""),
                "repo": attrs.get("repo", ""),
                "url": attrs.get("url", ""),
                "tags": [t.strip() for t in attrs.get("tags", "").split(",") if t.strip()],
                "body": " ".join(m.group("body").split()),
            }
        )
    return projects


def main() -> None:
    cfg = load_config()
    root = blog_dir(cfg)
    base_url = cfg["blog"]["base_url"].rstrip("/")
    if not (root / "content").is_dir():
        die(f"{root} does not look like the Hugo blog (no content/). Set BLOG_DIR.")

    info(f"blog: reading {root}")
    posts = collect_section(root, "posts", base_url)
    other = collect_section(root, "other", base_url)
    projects = collect_side_projects(root)

    path = write_json(
        "blog.json",
        {"root": str(root), "baseUrl": base_url, "posts": posts, "other": other, "sideProjects": projects},
    )
    drafts = sum(1 for p in posts if p["draft"])
    info(
        f"blog: {len(posts)} posts ({drafts} draft), {len(other)} talks/articles, "
        f"{len(projects)} side projects"
    )
    print(path)


if __name__ == "__main__":
    main()
