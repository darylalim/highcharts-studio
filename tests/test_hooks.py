"""Tests for the Claude Code hook scripts in ``.claude/hooks/``.

Run with: ``uv run pytest``

The hooks are dev tooling — they mirror the CI gates (Ruff, ty, pytest) so
Claude's edits stay green — not app code, but they carry real decision logic
that deserves regression coverage:

- ``guard_paths.protected_reason`` — which paths a PreToolUse edit must be
  blocked for (``uv.lock``, ``.streamlit/secrets.toml``, ``.git/`` internals).
- ``post_edit_py.is_python_target`` — which edited files route to ruff + ty.
- ``pytest_stop.has_dirty_python`` — whether ``git status --porcelain`` output
  names a changed ``.py`` outside ``.claude/`` (the gate that keeps the Stop
  hook from running the suite on conversational turns).

Those pure functions are exercised directly (fast, no toolchain, no git repo,
reliable in CI). A few black-box tests then drive ``guard_paths.py`` and
``post_edit_py.py`` as real subprocesses over stdin to pin the exit-code
contract Claude Code relies on (2 blocks, 0 allows) — under the current
interpreter (``sys.executable``), not shelling out to uv/ruff/ty/pytest, so they
stay fast.

The scripts live outside any importable package, so they're loaded by file path
via ``importlib``; importing only defines functions (the work is behind an
``if __name__ == "__main__"`` guard), so it has no side effects.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = ROOT / ".claude" / "hooks"


def _load(name: str):
    """Import a hook script from ``.claude/hooks/<name>.py`` by file path."""
    spec = importlib.util.spec_from_file_location(
        f"_hook_{name}", HOOKS_DIR / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load("guard_paths")
post_edit = _load("post_edit_py")
pytest_stop = _load("pytest_stop")


def _run_hook(name: str, payload: dict) -> subprocess.CompletedProcess:
    """Run a hook script as a real subprocess with ``payload`` as stdin JSON."""
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / f"{name}.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env={"CLAUDE_PROJECT_DIR": str(ROOT)},
        cwd=str(ROOT),
    )


# --------------------------------------------------------------------------- #
# PreToolUse guard: protected_reason
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "rel",
    [
        "uv.lock",  # lock file: uv owns it, never hand-edited
        "sub/uv.lock",  # matched by basename, anywhere in the tree
        ".streamlit/secrets.toml",  # gitignored secrets, matched repo-relative
        ".git/config",  # git internals, matched by path segment
        ".git/hooks/pre-commit",
    ],
)
def test_guard_blocks_protected_paths(tmp_path, rel):
    # The reason is the repo-relative path, surfaced back to Claude on a block.
    reason = guard.protected_reason(str(tmp_path / rel), str(tmp_path))
    assert reason == rel


@pytest.mark.parametrize(
    "rel",
    [
        "streamlit_app.py",
        "highcharts_builder.py",
        "pyproject.toml",
        "tests/test_smoke.py",
        ".streamlit/config.toml",  # the committed theme config IS editable
    ],
)
def test_guard_allows_normal_paths(tmp_path, rel):
    assert guard.protected_reason(str(tmp_path / rel), str(tmp_path)) is None


def test_guard_empty_path_is_allowed():
    # A missing file_path must not blow up or block — nothing to protect.
    assert guard.protected_reason("", None) is None


# --------------------------------------------------------------------------- #
# PostToolUse routing: is_python_target
# --------------------------------------------------------------------------- #
def test_post_edit_targets_existing_python_file(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text("x = 1\n")
    assert post_edit.is_python_target(str(f)) is True


@pytest.mark.parametrize("name", ["notes.md", "data.csv", "config.toml"])
def test_post_edit_skips_non_python(tmp_path, name):
    f = tmp_path / name
    f.write_text("content\n")
    assert post_edit.is_python_target(str(f)) is False


def test_post_edit_skips_missing_file(tmp_path):
    # A rename/delete can leave a .py path that no longer exists — nothing to lint.
    assert post_edit.is_python_target(str(tmp_path / "gone.py")) is False


def test_post_edit_skips_empty_path():
    assert post_edit.is_python_target("") is False


# --------------------------------------------------------------------------- #
# Stop-hook gate: has_dirty_python (git porcelain parsing)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "porcelain",
    [
        " M streamlit_app.py\n",  # modified source
        "?? new_module.py\n",  # untracked new module
        "A  tests/test_new.py\n",  # staged new test
        " M a.txt\n M highcharts_builder.py\n",  # .py alongside a non-.py
        "R  old.py -> renamed.py\n",  # rename: new side is .py
        "R  legacy.py -> legacy.txt\n",  # rename: old side was .py (still counts)
        "?? .claude/hooks/guard_paths.py\n",  # hook scripts ARE tested (test_hooks.py)
    ],
)
def test_dirty_python_detects_changes(porcelain):
    assert pytest_stop.has_dirty_python(porcelain) is True


@pytest.mark.parametrize(
    "porcelain",
    [
        "",  # clean tree
        "?? .claude/\n",  # a wholly-untracked .claude dir (git collapses it)
        " M .claude/settings.json\n",  # .claude config (non-hook) isn't app code
        "?? .claude/scratch.py\n",  # a .py directly under .claude/ (not a hook) is excluded
        " M README.md\n M .streamlit/config.toml\n",  # only non-.py changes
        "R  notes.txt -> archive.md\n",  # rename with no .py on either side
    ],
)
def test_dirty_python_ignores_non_app_changes(porcelain):
    assert pytest_stop.has_dirty_python(porcelain) is False


# --------------------------------------------------------------------------- #
# Exit-code contract (black-box, python3-only — no uv/ruff/ty/pytest spawned)
# --------------------------------------------------------------------------- #
def test_guard_subprocess_blocks_with_exit_2():
    # PreToolUse blocks by exiting 2 with the reason on stderr (fed to Claude).
    proc = _run_hook(
        "guard_paths", {"tool_input": {"file_path": str(ROOT / "uv.lock")}}
    )
    assert proc.returncode == 2
    assert "uv.lock" in proc.stderr


def test_guard_subprocess_allows_normal_file_with_exit_0():
    proc = _run_hook(
        "guard_paths", {"tool_input": {"file_path": str(ROOT / "streamlit_app.py")}}
    )
    assert proc.returncode == 0
    assert proc.stderr == ""


def test_post_edit_subprocess_noops_on_non_python():
    # A non-.py edit exits 0 immediately, before any toolchain is invoked.
    proc = _run_hook(
        "post_edit_py", {"tool_input": {"file_path": str(ROOT / "README.md")}}
    )
    assert proc.returncode == 0
