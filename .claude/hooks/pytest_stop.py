#!/usr/bin/env python3
"""Stop hook: run the pytest suite when Claude finishes a turn.

Fires when the main agent stops. It runs ``uv run pytest`` only when the working
tree has uncommitted changes to a ``.py`` file — app, test, or the hook scripts
under ``.claude/hooks/`` (other ``.claude/`` files don't count) — that changed
this turn; on a real failure it exits 2 so the output is fed back to Claude to
fix. On a clean tree — or a purely conversational turn — it is a silent no-op, so
the suite doesn't run after every message, and it doesn't nag once changes are
committed. Only pytest exit 1/2 (failures / collection error) count as a failure;
other non-zero codes (3/4 internal-or-usage, or a broken toolchain) are a no-op
so an environment problem isn't mislabeled as a test failure.

Loop guard: Claude Code sets ``stop_hook_active`` to true once it is already
continuing because of this hook. If tests are still failing on that follow-up
pass, the hook exits 1 (non-blocking, but its warning is shown to the user)
instead of looping. pytest's "no tests collected" (exit 5) is treated as success.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


def has_dirty_python(porcelain: str) -> bool:
    """True if ``git status --porcelain`` output names a changed .py worth testing.

    Pure and importable so the change-detection can be unit-tested without a git
    repo. Either side of a rename ("old -> new") counts, so renaming a .py to
    another name still registers as a Python change. ``.claude/`` files are
    ignored (Claude config isn't app code) EXCEPT the hook scripts under
    ``.claude/hooks/``, which ``tests/test_hooks.py`` covers — so editing a hook
    still re-runs the suite.
    """
    for line in porcelain.splitlines():
        entry = line[3:].strip()  # drop the "XY " porcelain status prefix
        parts = entry.split(" -> ")  # rename "old -> new"; otherwise a 1-elem list
        for path in parts:
            # git C-quotes non-ASCII paths in double quotes; stripping the quotes
            # is enough because we only test ASCII-safe markers (.py, .claude/)
            # that git never escapes.
            path = path.strip().strip('"')
            if path.startswith(".claude/") and not path.startswith(".claude/hooks/"):
                continue
            if path.endswith(".py"):
                return True
    return False


def _dirty_python(root: str | None) -> bool:
    """True if the working tree has modified/added .py files worth testing."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=root,
        )
    except FileNotFoundError:
        return True  # no git available — don't gate, just run
    if out.returncode != 0:
        return True
    return has_dirty_python(out.stdout)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:  # malformed / empty stdin (JSONDecodeError is a ValueError)
        data = {}
    stop_hook_active = bool(data.get("stop_hook_active"))
    root = os.environ.get("CLAUDE_PROJECT_DIR") or None

    if not _dirty_python(root):
        return 0  # nothing Python changed this turn; don't run the suite

    try:
        proc = subprocess.run(
            ["uv", "run", "pytest", "-q"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=root,
        )
    except FileNotFoundError:
        return 0  # no uv on PATH — nothing to run
    # pytest exit codes: 0 pass, 1 failures, 2 collection error/interrupt,
    # 3 internal, 4 usage, 5 no tests. Only 1/2 are the user's tests to fix;
    # anything else (green, no-tests, or a tooling/env failure) is a no-op, so a
    # broken toolchain is never mislabeled as a test failure.
    if proc.returncode not in (1, 2):
        return 0

    output = (proc.stdout or "") + (proc.stderr or "")
    tail = "\n".join(output.splitlines()[-100:])
    if stop_hook_active:
        # Already gave Claude a chance to fix; don't loop. Exit 1 (non-blocking) so
        # the stop proceeds but the warning still reaches the user — an exit-0
        # stderr write would be silently dropped by Claude Code.
        sys.stderr.write(
            "pytest is still failing after a fix attempt — leaving it for you to "
            "review rather than looping:\n\n" + tail + "\n"
        )
        return 1
    sys.stderr.write(
        "pytest failed after your changes — please fix the failing tests:\n\n"
        + tail
        + "\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
