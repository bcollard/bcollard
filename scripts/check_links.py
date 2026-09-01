#!/usr/bin/env python3
"""Fetch every link in README.md and report the ones that do not resolve."""

from __future__ import annotations

import concurrent.futures
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import README, ROOT, die, load_config  # noqa: E402

URL = re.compile(r"https?://[^\s\"'()<>\]]+")
# src="assets/x.svg" / srcset="..." / markdown ![alt](path) — relative paths only.
LOCAL = re.compile(r'(?:src|srcset)="(?!https?:|data:)([^"]+)"|\]\((?!https?:|#)([^)\s]+)\)')
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) profile-readme-linkcheck"
TIMEOUT = 15


def fetch(url: str) -> tuple[str, int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return url, resp.status, ""
    except urllib.error.HTTPError as e:
        return url, e.code, e.reason or ""
    except Exception as e:  # DNS, TLS, timeout, redirect loops
        return url, 0, f"{type(e).__name__}: {e}"


def check_local(text: str) -> list[tuple[str, str]]:
    """Relative paths in the README must exist on disk, or the image is broken."""
    missing = []
    seen = set()
    for m in LOCAL.finditer(text):
        rel = (m.group(1) or m.group(2) or "").strip()
        if not rel or rel in seen:
            continue
        seen.add(rel)
        if not (ROOT / rel).exists():
            missing.append((rel, "no such file"))
    print(f"checking {len(seen)} local path(s)")
    for rel in sorted(seen):
        ok = (ROOT / rel).exists()
        print(f"  {'ok ' if ok else 'FAIL'}       {rel}")
    print()
    return missing


def main() -> None:
    cfg = load_config()
    skip = cfg.get("links", {}).get("skip", [])
    if not README.exists():
        die(f"missing {README}")
    local_missing = check_local(README.read_text())

    urls = sorted({u.rstrip(".,;") for u in URL.findall(README.read_text())})
    checked = [u for u in urls if not any(s in u for s in skip)]
    print(f"checking {len(checked)} links ({len(urls) - len(checked)} skipped)\n")

    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for url, status, note in pool.map(fetch, checked):
            ok = 200 <= status < 400
            if not ok:
                failures.append((url, status, note))
            print(f"  {'ok ' if ok else 'FAIL'} {status or '---'}  {url}" + (f"  {note}" if note else ""))

    print()
    for rel, note in local_missing:
        failures.append((rel, 0, note))
    if failures:
        print(f"{len(failures)} broken link(s):", file=sys.stderr)
        for url, status, note in failures:
            print(f"  {status or '---'}  {url}  {note}", file=sys.stderr)
        raise SystemExit(1)
    print("all links resolve")


if __name__ == "__main__":
    main()
