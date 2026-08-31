#!/usr/bin/env python3
"""Advisory report: what changed out there that the README does not know about.

Nothing here edits files. It answers "what should I consider adding or fixing?"
by diffing the live GitHub/blog snapshots against what README.md actually says.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import README, load_config, read_json  # noqa: E402

BULLET = "  - "


def heading(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")


def mentioned(readme: str, *needles: str) -> bool:
    return any(n and n.lower() in readme for n in needles)


def check_featured(cfg, gh, blog, readme, repos):
    """Featured repos that were renamed, archived, or went private."""
    problems = []
    for name in cfg.get("featured", []):
        repo = repos.get(name) or repos.get(f"{cfg['github']['user']}/{name}")
        if repo is None:
            problems.append(f"{name}: no longer exists under your account (renamed? deleted?)")
            continue
        if repo["isArchived"]:
            problems.append(f"{name}: archived on GitHub but still featured")
        if repo["isPrivate"]:
            problems.append(f"{name}: went private but is still linked publicly")
    if problems:
        heading("Featured projects needing attention")
        for p in problems:
            print(BULLET + p)


def check_unmentioned_repos(cfg, gh, blog, readme, repos):
    """Public, non-fork repos with traction that the README never mentions."""
    excluded = set(cfg["github"].get("exclude", []))
    rows = [
        r for r in gh["repos"]
        if not r["isPrivate"] and not r["isFork"] and not r["isArchived"]
        and not r.get("external") and not r["name"].startswith("homebrew-")
        and r["name"] not in excluded
        and not mentioned(readme, f"/{r['name']}", r["homepage"])
    ]
    rows.sort(key=lambda r: (r["stars"], r["updatedAt"]), reverse=True)

    # Old, unstarred repos are archaeology, not candidates. Collapse them
    # unless --all is passed.
    years = cfg.get("report", {}).get("stale_after_years", 3)
    cutoff = (date.today() - timedelta(days=365 * years)).isoformat()
    show_all = "--all" in sys.argv
    fresh = [r for r in rows if show_all or r["updatedAt"] >= cutoff or r["stars"] > 0]
    stale = len(rows) - len(fresh)

    if fresh:
        heading(f"Public repos not mentioned in the README ({len(fresh)})")
        for r in fresh:
            stars = f"⭐{r['stars']}" if r["stars"] else "  "
            print(f"{BULLET}{r['name']:<38} {stars:<5} {r['language'] or '-':<12} "
                  f"updated {r['updatedAt']}")
            if r["description"]:
                print(f"      {r['description'][:110]}")
        print("      → feature it, or add it to github.exclude in config/profile.toml")
    if stale:
        print(f"\n  (+{stale} untouched for {years}+ years and unstarred — `make report ARGS=--all` to list)")


def check_unmentioned_upstream(cfg, gh, blog, readme, repos):
    """Merged PRs in other people's repos that the README does not credit."""
    user = cfg["github"]["user"].lower()
    excluded = set(cfg.get("upstream", {}).get("exclude", []))
    tally = {}
    for pr in gh["prs"]:
        repo = pr["repo"]
        if repo.split("/")[0].lower() == user or repo in excluded:
            continue
        if pr["state"] not in {"merged", "open"}:
            continue
        if mentioned(readme, repo):
            continue
        t = tally.setdefault(repo, {"merged": 0, "open": 0, "last": "", "titles": []})
        t[pr["state"]] += 1
        t["last"] = max(t["last"], pr["createdAt"])
        t["titles"].append(pr["title"])
    if tally:
        heading(f"Upstream repos with contributions not credited ({len(tally)})")
        for repo, t in sorted(tally.items(), key=lambda kv: kv[1]["last"], reverse=True):
            print(f"{BULLET}{repo:<45} {t['merged']} merged, {t['open']} open  (last {t['last']})")
            print(f"      {t['titles'][-1][:110]}")
        print("      → add to upstream.order + upstream.highlight, or upstream.exclude")


def check_blog_drift(cfg, gh, blog, readme, repos):
    """Side projects on the blog but not the README, and vice versa."""
    missing = []
    for p in blog["sideProjects"]:
        if p["status"] not in {"live"}:
            continue
        if not mentioned(readme, p["repo"], p["url"], p["name"]):
            missing.append(p)
    if missing:
        heading(f"On the blog's side-projects page but not in the README ({len(missing)})")
        for p in missing:
            print(f"{BULLET}{p['name']:<38} {p['section']}")
            print(f"      {p['repo'] or p['url'] or '(no link)'}")

    blog_links = " ".join(p["repo"] + " " + p["url"] + " " + p["name"] for p in blog["sideProjects"]).lower()
    orphans = [
        name for name in cfg.get("featured", [])
        if name.lower() not in blog_links
    ]
    if orphans:
        heading("Featured in the README but missing from the blog's side-projects page")
        for name in orphans:
            print(BULLET + name)
        print("      → add a {{< project-card >}} in content/side-projects/_index.md")


def check_posts(cfg, gh, blog, readme, repos):
    """Recent posts not linked, and linked posts that are still drafts."""
    linked = {w["slug"] for w in cfg.get("writing", [])}
    recent = [p for p in blog["posts"] if not p["draft"] and p["slug"] not in linked][:5]
    if recent:
        heading("Recent posts not linked from the README")
        for p in recent:
            print(f"{BULLET}{p['date']}  {p['title']}")
            print(f"      {p['url']}")

    drafts = [p for p in blog["posts"] if p["draft"]]
    if drafts:
        heading(f"Blog posts still marked draft ({len(drafts)}) — these will 404 if linked")
        for p in drafts:
            print(f"{BULLET}{p['slug']}  ({p['file']})")

    talks = set(cfg.get("talks", {}).get("slugs", []))
    unclassified = [o for o in blog["other"] if o["slug"] not in talks]
    if unclassified:
        heading(f"content/other/ entries not listed as talks ({len(unclassified)})")
        print("      (external articles, presumably — add to talks.slugs if any is a talk)")
        for o in unclassified:
            print(f"{BULLET}{o['date']}  {o['title'][:80]}")


def check_profile_fields(cfg, gh, blog, readme, repos):
    """The sidebar fields the README cannot fill."""
    p = gh["profile"]
    gaps = [k for k in ("bio", "company", "location", "website") if not p.get(k)]
    if gaps:
        heading("Empty GitHub profile sidebar fields")
        print(BULLET + ", ".join(gaps))
        print("      → gh api -X PATCH user -f bio='...' -f company='...'")


CHECKS = [
    check_featured,
    check_unmentioned_repos,
    check_unmentioned_upstream,
    check_blog_drift,
    check_posts,
    check_profile_fields,
]


def main() -> None:
    cfg = load_config()
    gh = read_json("github.json")
    blog = read_json("blog.json")
    readme = README.read_text().lower()
    repos = {}
    for r in gh["repos"]:
        repos[r["nameWithOwner"]] = r
        repos.setdefault(r["name"], r)

    c = gh["profile"]["contributions"]
    print(f"\033[1m@{gh['profile']['login']}\033[0m — {c['lastYearTotal']} contributions in the last year "
          f"({c['commits']} commits, {c['pullRequests']} PRs), "
          f"{sum(1 for r in gh['repos'] if not r['isPrivate'] and not r.get('external'))} public repos, "
          f"{gh['profile']['followers']} followers")

    for check in CHECKS:
        check(cfg, gh, blog, readme, repos)
    print()


if __name__ == "__main__":
    main()
