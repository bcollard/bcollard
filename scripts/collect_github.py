#!/usr/bin/env python3
"""Snapshot everything the README needs from GitHub into data/github.json."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import gh, info, load_config, write_json  # noqa: E402

REPO_FIELDS = (
    "name,nameWithOwner,description,primaryLanguage,stargazerCount,forkCount,"
    "isFork,isPrivate,isArchived,updatedAt,url,homepageUrl"
)

LANG_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: OWNER,
                 isFork: false, privacy: PUBLIC) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        isArchived
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

CONTRIB_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    login
    bio
    company
    location
    websiteUrl
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoryContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""


def collect_repos(user: str) -> list[dict]:
    rows = gh("repo", "list", user, "--limit", "500", "--json", REPO_FIELDS)
    out = []
    for r in rows:
        out.append(
            {
                "name": r["name"],
                "nameWithOwner": r["nameWithOwner"],
                "description": r.get("description") or "",
                "language": (r.get("primaryLanguage") or {}).get("name") or "",
                "stars": r["stargazerCount"],
                "forks": r["forkCount"],
                "isFork": r["isFork"],
                "isPrivate": r["isPrivate"],
                "isArchived": r["isArchived"],
                "updatedAt": r["updatedAt"][:10],
                "url": r["url"],
                "homepage": r.get("homepageUrl") or "",
            }
        )
    return sorted(out, key=lambda r: (-r["stars"], r["name"].lower()))


def collect_prs(user: str) -> list[dict]:
    rows = gh(
        "search", "prs", "--author", user, "--limit", "1000",
        "--json", "repository,title,state,url,createdAt",
    )
    return sorted(
        (
            {
                "repo": r["repository"]["nameWithOwner"],
                "title": r["title"],
                "state": r["state"],
                "url": r["url"],
                "createdAt": r["createdAt"][:10],
            }
            for r in rows
        ),
        key=lambda r: (r["repo"].lower(), r["createdAt"]),
    )


def collect_issues(user: str) -> list[dict]:
    rows = gh(
        "search", "issues", "--author", user, "--limit", "500",
        "--json", "repository,title,state,url,createdAt",
    )
    return sorted(
        (
            {
                "repo": r["repository"]["nameWithOwner"],
                "title": r["title"],
                "state": r["state"],
                "url": r["url"],
                "createdAt": r["createdAt"][:10],
            }
            for r in rows
        ),
        key=lambda r: (r["repo"].lower(), r["createdAt"]),
    )


def collect_referenced(cfg: dict, owned: set[str]) -> list[dict]:
    """Fetch repos the config points at that the user does not own (e.g. Kong/*)."""
    wanted = {e["repo"] for e in cfg.get("toolbelt", [])}
    up = cfg.get("upstream", {})
    wanted |= set(up.get("order", []))
    wanted |= {h["repo"] for h in up.get("highlight", [])}

    out = []
    for full in sorted(wanted - owned):
        if "/" not in full:
            continue
        r = gh("api", f"repos/{full}")
        out.append(
            {
                "name": r["name"],
                "nameWithOwner": r["full_name"],
                "description": r.get("description") or "",
                "language": r.get("language") or "",
                "stars": r["stargazers_count"],
                "forks": r["forks_count"],
                "isFork": r["fork"],
                "isPrivate": r["private"],
                "isArchived": r["archived"],
                "updatedAt": r["updated_at"][:10],
                "url": r["html_url"],
                "homepage": r.get("homepage") or "",
                "external": True,
            }
        )
    return out


def collect_languages(user: str, exclude: set[str]) -> list[dict]:
    """Bytes per language across owned public non-fork repos, with GitHub's colours."""
    sizes: dict[str, int] = {}
    colors: dict[str, str] = {}
    cursor = None
    while True:
        args = ["api", "graphql", "-f", f"query={LANG_QUERY}", "-F", f"login={user}"]
        if cursor:
            args += ["-F", f"cursor={cursor}"]
        page = gh(*args)["data"]["user"]["repositories"]
        for repo in page["nodes"]:
            if repo["name"] in exclude or repo["isArchived"]:
                continue
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                sizes[name] = sizes.get(name, 0) + edge["size"]
                colors[name] = edge["node"]["color"] or "#8b949e"
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    total = sum(sizes.values()) or 1
    return [
        {"name": n, "bytes": b, "share": b / total, "color": colors[n]}
        for n, b in sorted(sizes.items(), key=lambda kv: -kv[1])
    ]


def collect_profile(user: str) -> dict:
    res = gh("api", "graphql", "-f", f"query={CONTRIB_QUERY}", "-F", f"login={user}")
    u = res["data"]["user"]
    c = u["contributionsCollection"]
    return {
        "name": u["name"],
        "login": u["login"],
        "bio": u["bio"] or "",
        "company": u["company"] or "",
        "location": u["location"] or "",
        "website": u["websiteUrl"] or "",
        "followers": u["followers"]["totalCount"],
        "contributions": {
            "lastYearTotal": c["contributionCalendar"]["totalContributions"],
            "commits": c["totalCommitContributions"],
            "pullRequests": c["totalPullRequestContributions"],
            "issues": c["totalIssueContributions"],
            "repositories": c["totalRepositoryContributions"],
        },
    }


def main() -> None:
    cfg = load_config()
    user = cfg["github"]["user"]

    info(f"github: profile for @{user}")
    profile = collect_profile(user)
    info("github: repositories")
    repos = collect_repos(user)
    info("github: pull requests")
    prs = collect_prs(user)
    info("github: issues")
    issues = collect_issues(user)
    info("github: repos referenced by config but not owned")
    repos += collect_referenced(cfg, {r["nameWithOwner"] for r in repos})

    excluded = set(cfg["github"].get("exclude", []))
    info("github: language breakdown")
    languages = collect_languages(user, excluded)
    taps = sorted(
        r["name"] for r in repos
        if r["name"].startswith("homebrew-")
        and not r["isPrivate"]
        and not r["isFork"]
        and r["name"] not in excluded
    )

    path = write_json(
        "github.json",
        {
            "profile": profile,
            "repos": repos,
            "prs": prs,
            "issues": issues,
            "taps": taps,
            "languages": languages,
            "totals": {
                "publicRepos": sum(
                    1 for r in repos
                    if not r["isPrivate"] and not r["isFork"] and not r.get("external")
                ),
                "stars": sum(
                    r["stars"] for r in repos
                    if not r["isPrivate"] and not r["isFork"] and not r.get("external")
                ),
                "mergedPRs": sum(1 for p in prs if p["state"] == "merged"),
                "upstreamRepos": len({
                    p["repo"] for p in prs
                    if p["repo"].split("/")[0].lower() != user.lower()
                }),
            },
        },
    )
    merged = sum(1 for p in prs if p["state"] == "merged")
    info(
        f"github: {len(repos)} repos ({sum(1 for r in repos if not r['isPrivate'])} public), "
        f"{len(prs)} PRs ({merged} merged), {len(issues)} issues, {len(taps)} taps"
    )
    print(path)


if __name__ == "__main__":
    main()
