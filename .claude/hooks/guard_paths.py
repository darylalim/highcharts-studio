#!/usr/bin/env python3
"""PreToolUse hook: block Edit/Write/MultiEdit to files that must not be hand-edited.

- ``uv.lock`` changes only through uv (``uv add`` / ``uv sync`` / ``uv lock``);
  CI runs ``uv sync --locked`` and fails on a hand-edited, inconsistent lock.
- ``.streamlit/secrets.toml`` is gitignored secrets — never write it via an edit.
- anything under ``.git/`` is git internals and must not be hand-edited.

Exits 2 to block the call and explain why. Fails *open* (exit 0) only on a
malformed payload, so a hook bug never wedges normal editing. Matching is by
basename (``uv.lock``), path tail (``.streamlit/secrets.toml``), and path segment
(``.git/``) — so a protected file is caught even when the project root can't be
resolved (``CLAUDE_PROJECT_DIR`` unset -> the path stays absolute).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROTECTED_NAMES = {"uv.lock"}  # matched by basename, anywhere
# Matched against the path tail (not just repo-relative), so secrets.toml — which
# has no distinctive basename — is still caught when the root can't be resolved
# and the path stays absolute.
PROTECTED_SUFFIXES = (".streamlit/secrets.toml",)
PROTECTED_DIRS = {".git"}  # matched if any path segment is one of these


def protected_reason(file_path: str, root: str | None) -> str | None:
    """Return the offending path if it must not be hand-edited, else None.

    Pure and importable so the guard logic can be unit-tested without a
    subprocess. ``root`` is the project root (``$CLAUDE_PROJECT_DIR``); the path
    is matched repo-relative where possible, else by the raw (absolute) path — so
    the basename / path-tail / ``.git`` rules still apply when ``root`` is unset.
    """
    if not file_path:
        return None
    p = Path(file_path)
    try:
        rel = p.resolve().relative_to(Path(root).resolve()) if root else p
    except ValueError:
        rel = p  # outside the project tree — fall back to the raw path
    rel_str = rel.as_posix()
    if (
        p.name in PROTECTED_NAMES
        or rel_str.endswith(PROTECTED_SUFFIXES)
        or (set(rel.parts) & PROTECTED_DIRS)
    ):
        return rel_str
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:  # malformed / empty stdin (JSONDecodeError is a ValueError)
        return 0
    file_path = (data.get("tool_input") or {}).get("file_path", "") or ""
    reason = protected_reason(file_path, os.environ.get("CLAUDE_PROJECT_DIR") or None)
    if reason is not None:
        sys.stderr.write(
            f"Blocked edit to protected path '{reason}'.\n"
            "- uv.lock: change it with `uv add` / `uv sync` / `uv lock`, not by hand.\n"
            "- .streamlit/secrets.toml: never write secrets through an edit.\n"
            "- .git/: git internals must not be hand-edited.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
