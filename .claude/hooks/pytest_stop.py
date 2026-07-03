#!/usr/bin/env python3
"""Stop hook: run the pytest suite when Claude finishes a turn.

Fires when the main agent stops. It runs ``uv run pytest`` only when the working
tree has uncommitted changes to a ``.py`` file outside ``.claude/`` (i.e. app or
test code actually changed this turn); on failure it exits 2 so the failing
output is fed back to Claude to fix. On a clean tree — or a purely
conversational turn — it is a silent no-op, so the suite doesn't run after every
message, and it doesn't nag once changes are committed.

Loop guard: Claude Code sets ``stop_hook_active`` to true once it is already
continuing because of this hook. If tests are still failing on that follow-up
pass, the hook stops blocking (exit 0) and only warns, so it can never loop
forever. pytest's "no tests collected" (exit 5) is treated as success.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys


def _dirty_python(root: str | None) -> bool:
    """True if the working tree has modified/added .py files outside .claude/."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=root,
        )
    except FileNotFoundError:
        return True  # no git available — don't gate, just run
    if out.returncode != 0:
        return True
    for line in out.stdout.splitlines():
        path = line[3:].strip().strip('"')  # porcelain: "XY <path>"
        if " -> " in path:  # rename: "old -> new"
            path = path.split(" -> ", 1)[1]
        if path.startswith(".claude/"):
            continue  # Claude config/hooks aren't app code
        if path.endswith(".py"):
            return True
    return False


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
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
            cwd=root,
        )
    except FileNotFoundError:
        return 0  # no uv on PATH — nothing to run
    if proc.returncode in (0, 5):  # 5 == no tests collected
        return 0  # green — let Claude stop

    output = (proc.stdout or "") + (proc.stderr or "")
    tail = "\n".join(output.splitlines()[-100:])
    if stop_hook_active:
        # Already gave Claude a chance to fix; don't loop — warn and allow stop.
        sys.stderr.write(
            "pytest is still failing after a fix attempt — leaving it for you to "
            "review rather than looping:\n\n" + tail + "\n"
        )
        return 0
    sys.stderr.write(
        "pytest failed after your changes — please fix the failing tests:\n\n"
        + tail
        + "\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
