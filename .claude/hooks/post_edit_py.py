#!/usr/bin/env python3
"""PostToolUse hook: keep edited Python files green against the CI gates.

Fires after Edit/Write/MultiEdit. For a ``.py`` file it:

1. runs ``ruff check --fix`` then ``ruff format`` on the file (mirrors the CI
   "Lint & format (Ruff)" gate) — deterministic and safe to apply unattended,
   so the edit lands lint-clean and formatted; and
2. runs ``ty check`` on the project (mirrors the CI "Type check (ty)" gate; ty
   needs the whole project to resolve pandas/streamlit/highcharts-core imports).
   On type errors it exits 2 so the diagnostics are fed back to Claude to fix.

ruff runs *before* ty in this one script (rather than as two separate hooks) so
the format write can't race ty's read. Any non-.py edit, a missing file, or a
missing toolchain is a silent no-op — a hook must never wedge editing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _read_file_path() -> str:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return ""
    return (data.get("tool_input") or {}).get("file_path", "") or ""


def is_python_target(file_path: str) -> bool:
    """True if ``file_path`` is an existing ``.py`` file worth linting.

    Pure and importable so the routing (which edits trigger ruff/ty) can be
    unit-tested without spawning the toolchain.
    """
    if not file_path:
        return False
    p = Path(file_path)
    return p.suffix == ".py" and p.exists()


def main() -> int:
    file_path = _read_file_path()
    if not is_python_target(file_path):
        return 0

    root = os.environ.get("CLAUDE_PROJECT_DIR") or None

    # 1) ruff: auto-fix lint + format in place. Best-effort; never block on it.
    for args in (
        ["ruff", "check", "--fix", "--quiet", file_path],
        ["ruff", "format", "--quiet", file_path],
    ):
        try:
            subprocess.run(["uv", "run", *args], capture_output=True, cwd=root)
        except FileNotFoundError:
            return 0  # no uv on PATH — nothing to enforce

    # 2) ty: type-check the project; feed any diagnostics back to Claude.
    try:
        proc = subprocess.run(
            ["uv", "run", "ty", "check"],
            capture_output=True,
            text=True,
            cwd=root,
        )
    except FileNotFoundError:
        return 0
    if proc.returncode != 0:
        sys.stderr.write(
            "ty reported type errors after this edit — please fix them:\n\n"
            + (proc.stdout or "")
            + (proc.stderr or "")
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
