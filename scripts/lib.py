"""Shared helpers for the profile README tooling."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "profile.toml"
DATA = ROOT / "data"
README = ROOT / "README.md"

# <!-- profile:begin:name -->  ...generated...  <!-- profile:end:name -->
MARKER = re.compile(
    r"(?P<open><!--\s*profile:begin:(?P<name>[\w-]+)\s*-->\n)"
    r"(?P<body>.*?)"
    r"(?P<close>\n?<!--\s*profile:end:(?P=name)\s*-->)",
    re.DOTALL,
)


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def info(msg: str) -> None:
    print(f"  {msg}", file=sys.stderr)


def load_config() -> dict:
    if not CONFIG.exists():
        die(f"missing config file: {CONFIG}")
    with CONFIG.open("rb") as fh:
        cfg = tomllib.load(fh)
    # BLOG_DIR env var wins over the configured path.
    blog = cfg.setdefault("blog", {})
    blog["path"] = os.environ.get("BLOG_DIR") or blog.get("path", "../blog")
    return cfg


def blog_dir(cfg: dict) -> Path:
    p = Path(cfg["blog"]["path"]).expanduser()
    return p if p.is_absolute() else (ROOT / p).resolve()


def read_json(name: str) -> dict:
    path = DATA / name
    if not path.exists():
        die(f"missing {path}. Run `make data` first.")
    return json.loads(path.read_text())


def write_json(name: str, payload: dict) -> Path:
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    return path


def gh(*args: str) -> object:
    """Run a `gh` command that emits JSON and return the decoded payload."""
    cmd = ["gh", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        die(f"`{' '.join(cmd)}` failed:\n{proc.stderr.strip()}")
    out = proc.stdout.strip()
    return json.loads(out) if out else None


def replace_regions(text, blocks):
    """Swap the body of every `profile:begin/end` region named in `blocks`.

    Returns (new_text, changed_names, unknown_names_found_in_file).
    """
    changed = []
    unknown = []

    def sub(m):
        name = m.group("name")
        if name not in blocks:
            unknown.append(name)
            return m.group(0)
        body = blocks[name].rstrip("\n")
        if body != m.group("body").rstrip("\n"):
            changed.append(name)
        return f"{m.group('open')}{body}\n<!-- profile:end:{name} -->"

    return MARKER.sub(sub, text), changed, unknown


def region_names(text):
    return {m.group("name") for m in MARKER.finditer(text)}
