#!/usr/bin/env python3
"""PreToolUse hook: block Edit/Write/MultiEdit to files that must not be hand-edited.

- ``uv.lock`` changes only through uv (``uv add`` / ``uv sync`` / ``uv lock``);
  CI runs ``uv sync --locked`` and fails on a hand-edited, inconsistent lock.
- ``.streamlit/secrets.toml`` is gitignored secrets — never write it via an edit.
- anything under ``.git/`` is git internals and must not be hand-edited.

Exits 2 to block the call and explain why. Fails *open* (exit 0) on a malformed
payload or a path outside the project, so a hook bug never wedges normal editing.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROTECTED_NAMES = {"uv.lock"}  # matched by basename, anywhere
PROTECTED_RELPATHS = {".streamlit/secrets.toml"}  # matched repo-relative
PROTECTED_DIRS = {".git"}  # matched if any path segment is one of these


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    file_path = (data.get("tool_input") or {}).get("file_path", "") or ""
    if not file_path:
        return 0

    root = os.environ.get("CLAUDE_PROJECT_DIR")
    p = Path(file_path)
    try:
        rel = p.resolve().relative_to(Path(root).resolve()) if root else p
    except ValueError:
        rel = p  # outside the project tree — fall back to the raw path
    rel_str = rel.as_posix()

    if (
        p.name in PROTECTED_NAMES
        or rel_str in PROTECTED_RELPATHS
        or (set(rel.parts) & PROTECTED_DIRS)
    ):
        sys.stderr.write(
            f"Blocked edit to protected path '{rel_str}'.\n"
            "- uv.lock: change it with `uv add` / `uv sync` / `uv lock`, not by hand.\n"
            "- .streamlit/secrets.toml: never write secrets through an edit.\n"
            "- .git/: git internals must not be hand-edited.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
