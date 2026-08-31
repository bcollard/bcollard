#!/usr/bin/env python3
"""Regenerate the machine-maintained regions of README.md.

Prose stays hand-written. Only text between matching
`<!-- profile:begin:NAME -->` / `<!-- profile:end:NAME -->` markers is touched.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    README, die, info, load_config, read_json, region_names, replace_regions,
)

STARS = re.compile(r"\{stars:([\w.-]+)\}")


def month_year(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %Y")
    except ValueError:
        return ""


def index_repos(gh: dict) -> dict:
    by = {}
    for r in gh["repos"]:
        by[r["nameWithOwner"]] = r
        by.setdefault(r["name"], r)
    return by


def expand_stars(text: str, repos: dict) -> str:
    def sub(m):
        repo = repos.get(m.group(1))
        return str(repo["stars"]) if repo else m.group(0)
    return STARS.sub(sub, text)


# --------------------------------------------------------------------------- #
# Regions
# --------------------------------------------------------------------------- #

def render_toolbelt(cfg: dict, gh: dict, blog: dict, repos: dict) -> str:
    rows = ["| | | |", "|---|---|---|"]
    for entry in cfg.get("toolbelt", []):
        full = entry["repo"]
        repo = repos.get(full)
        if repo is None:
            die(f"toolbelt: {full} is not in data/github.json (renamed? private?)")
        if repo["isArchived"]:
            info(f"toolbelt: warning — {full} is archived")
        name = entry.get("name", repo["name"])
        site = entry.get("site") or repo["homepage"]
        cell = f"**[{name}]({repo['url']})**"
        if site:
            cell += f" · [site]({site})"
        lang = entry.get("lang") or repo["language"] or "—"
        rows.append(f"| {cell} | {entry['blurb']} | `{lang}` |")
    return "\n".join(rows)


def render_taps(cfg: dict, gh: dict, blog: dict, repos: dict) -> str:
    user = cfg["github"]["user"]
    links = [
        f"[`{user}/{tap.removeprefix('homebrew-')}`](https://github.com/{user}/{tap})"
        for tap in gh["taps"]
    ]
    return "Taps: " + " · ".join(links)


def render_upstream(cfg: dict, gh: dict, blog: dict, repos: dict) -> str:
    conf = cfg.get("upstream", {})
    user = cfg["github"]["user"].lower()
    excluded = set(conf.get("exclude", []))
    threshold = conf.get("count_threshold", 5)
    highlights = {h["repo"]: h for h in conf.get("highlight", [])}

    tally: dict[str, dict[str, int]] = {}
    for pr in gh["prs"]:
        repo = pr["repo"]
        if repo.split("/")[0].lower() == user or repo in excluded:
            continue
        counts = tally.setdefault(repo, {"merged": 0, "open": 0, "closed": 0, "last": ""})
        counts[pr["state"]] = counts.get(pr["state"], 0) + 1
        counts["last"] = max(counts["last"], pr["createdAt"])

    ordered = [r for r in conf.get("order", []) if r in tally]
    # Everything else, most recently contributed to first.
    rest = sorted(
        (r for r in tally if r not in ordered),
        key=lambda r: (tally[r]["last"], r.lower()),
        reverse=True,
    )

    lines = []
    for repo in ordered:
        hl = highlights.get(repo, {})
        counts = tally[repo]
        label = f"**[{repo}](https://github.com/{repo})**"
        if hl.get("suffix"):
            label += f" {hl['suffix']}"
        detail = hl.get("text", "")
        if counts["merged"] >= threshold:
            detail = f"~{counts['merged']} merged PRs" + (f": {detail}" if detail else "")
        lines.append(f"- {label}" + (f" — {detail}" if detail else ""))

    if rest:
        also = " · ".join(f"**[{r}](https://github.com/{r})**" for r in rest)
        lines.append(f"- {also}")
    return "\n".join(lines)


def render_writing(cfg: dict, gh: dict, blog: dict, repos: dict) -> str:
    by_slug = {p["slug"]: p for p in blog["posts"]}
    lines = []
    for entry in cfg.get("writing", []):
        slug = entry["slug"]
        post = by_slug.get(slug)
        if post is None:
            die(f"writing: no blog post with slug '{slug}' (renamed? deleted?)")
        if post["draft"]:
            info(f"writing: warning — '{slug}' is a draft and may 404")
        title = entry.get("title") or post["title"]
        line = f"- [{title}]({post['url']})"
        if entry.get("note"):
            line += f" — {expand_stars(entry['note'], repos)}"
        lines.append(line)
    return "\n".join(lines)


def render_talks(cfg: dict, gh: dict, blog: dict, repos: dict) -> str:
    by_slug = {o["slug"]: o for o in blog["other"]}
    items = []
    for slug in cfg.get("talks", {}).get("slugs", []):
        item = by_slug.get(slug)
        if item is None:
            die(f"talks: no entry with slug '{slug}' under content/other/")
        items.append(item)

    lines = []
    for item in sorted(items, key=lambda i: i["date"], reverse=True):
        when = month_year(item["date"])
        title = item["title"].replace(" - ", " — ")
        lines.append(f"- [{title}]({item['url']})" + (f" · *{when}*" if when else ""))
    return "\n".join(lines)


RENDERERS = {
    "toolbelt": render_toolbelt,
    "taps": render_taps,
    "upstream": render_upstream,
    "writing": render_writing,
    "talks": render_talks,
}


def main() -> None:
    cfg = load_config()
    gh = read_json("github.json")
    blog = read_json("blog.json")
    repos = index_repos(gh)

    if not README.exists():
        die(f"missing {README}")
    text = README.read_text()

    present = region_names(text)
    missing = set(RENDERERS) - present
    if missing:
        die(
            "README.md has no markers for: " + ", ".join(sorted(missing))
            + "\nAdd <!-- profile:begin:NAME --> / <!-- profile:end:NAME --> around each block."
        )

    blocks = {name: fn(cfg, gh, blog, repos) for name, fn in RENDERERS.items()}
    new_text, changed, unknown = replace_regions(text, blocks)

    for name in sorted(set(unknown)):
        info(f"render: warning — region '{name}' in README.md has no renderer")

    if new_text == text:
        info("render: no changes")
    else:
        README.write_text(new_text)
        info("render: updated " + ", ".join(sorted(changed)))
    print(README)


if __name__ == "__main__":
    main()
