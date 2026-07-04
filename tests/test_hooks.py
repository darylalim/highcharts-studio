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
stay fast. Under ``uv run pytest`` that interpreter is the project's 3.12 venv —
the same one settings.json runs the live hooks under (``uv run … python``) — so
the tests validate the interpreter the hooks actually use.

The scripts live outside any importable package, so they're loaded by file path
via ``importlib``; importing only defines functions (the work is behind an
``if __name__ == "__main__"`` guard), so it has no side effects.
"""

import importlib.util
import io
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


# --------------------------------------------------------------------------- #
# main() paths — monkeypatched so no real toolchain (uv/ruff/ty/git/pytest) runs.
#
# The hooks look up subprocess.run and sys.stdin at call time on the (shared)
# stdlib modules, so patching those on the imported hook module reaches the live
# code; monkeypatch reverts after each test. capsys captures what the hook writes
# to stderr. These cover the exit-code contract the black-box tests above can't
# reach without a real toolchain (their wiped PATH short-circuits first).
# --------------------------------------------------------------------------- #
class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _feed_stdin(monkeypatch, payload):
    """Point every hook's ``json.load(sys.stdin)`` at ``payload``.

    ``payload`` is a dict (JSON-encoded here) or a raw string (to test bad JSON).
    """
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


def _fake_run(handler, recorder=None):
    """A ``subprocess.run`` replacement that dispatches on the command list."""

    def run(cmd, *args, **kwargs):
        cmd = list(cmd)
        if recorder is not None:
            recorder.append(cmd)
        return handler(cmd)

    return run


def _never_run(*args, **kwargs):
    raise AssertionError("subprocess.run should not have been called")


def _git_then_pytest(dirty, pytest_proc):
    """Handler: git reports a dirty (or clean) tree, then pytest returns a code."""

    def handler(cmd):
        if cmd and cmd[0] == "git":
            return _FakeProc(0, stdout=" M streamlit_app.py\n" if dirty else "")
        return pytest_proc  # the `uv run pytest` call

    return handler


# ---- post_edit_py.main() ---------------------------------------------------- #
def test_post_edit_main_feeds_real_ty_errors(tmp_path, monkeypatch, capsys):
    f = tmp_path / "m.py"
    f.write_text("x = 1\n")
    _feed_stdin(monkeypatch, {"tool_input": {"file_path": str(f)}})
    calls = []

    def handler(cmd):
        if "ty" in cmd:
            return _FakeProc(1, stdout="error[bad-return-type]: nope\n")
        return _FakeProc(0)  # ruff

    monkeypatch.setattr(post_edit.subprocess, "run", _fake_run(handler, calls))
    assert post_edit.main() == 2
    assert "bad-return-type" in capsys.readouterr().err
    assert ["uv", "run", "ty", "check"] in calls  # ty was actually consulted


def test_post_edit_main_clean_ty_is_ok(tmp_path, monkeypatch, capsys):
    f = tmp_path / "m.py"
    f.write_text("x = 1\n")
    _feed_stdin(monkeypatch, {"tool_input": {"file_path": str(f)}})
    monkeypatch.setattr(
        post_edit.subprocess, "run", _fake_run(lambda cmd: _FakeProc(0))
    )
    assert post_edit.main() == 0
    assert capsys.readouterr().err == ""


def test_post_edit_main_ty_tooling_failure_is_noop(tmp_path, monkeypatch, capsys):
    # ty exit >=2 is a tooling/env failure (bad flag, unsynced venv), NOT type
    # errors — main() must no-op (exit 0), never feed a phantom error back.
    f = tmp_path / "m.py"
    f.write_text("x = 1\n")
    _feed_stdin(monkeypatch, {"tool_input": {"file_path": str(f)}})

    def handler(cmd):
        if "ty" in cmd:
            return _FakeProc(2, stderr="error: Failed to spawn\n")
        return _FakeProc(0)

    monkeypatch.setattr(post_edit.subprocess, "run", _fake_run(handler))
    assert post_edit.main() == 0
    assert "type errors" not in capsys.readouterr().err


def test_post_edit_main_no_uv_noops(tmp_path, monkeypatch):
    f = tmp_path / "m.py"
    f.write_text("x = 1\n")
    _feed_stdin(monkeypatch, {"tool_input": {"file_path": str(f)}})

    def boom(*a, **k):
        raise FileNotFoundError("uv")

    monkeypatch.setattr(post_edit.subprocess, "run", boom)
    assert post_edit.main() == 0


def test_post_edit_main_malformed_stdin_noops(monkeypatch):
    _feed_stdin(monkeypatch, "not json{")
    monkeypatch.setattr(post_edit.subprocess, "run", _never_run)  # must short-circuit
    assert post_edit.main() == 0


# ---- pytest_stop.main() ----------------------------------------------------- #
def test_pytest_stop_blocks_on_failure(monkeypatch, capsys):
    _feed_stdin(monkeypatch, {})
    monkeypatch.setattr(
        pytest_stop.subprocess,
        "run",
        _fake_run(_git_then_pytest(True, _FakeProc(1, stdout="1 failed\n"))),
    )
    assert pytest_stop.main() == 2
    assert "1 failed" in capsys.readouterr().err


def test_pytest_stop_loop_guard_exits_1(monkeypatch, capsys):
    # stop_hook_active + still failing: exit 1 (non-blocking) so the stop proceeds
    # but the warning still reaches the user (exit-0 stderr would be dropped).
    _feed_stdin(monkeypatch, {"stop_hook_active": True})
    monkeypatch.setattr(
        pytest_stop.subprocess,
        "run",
        _fake_run(_git_then_pytest(True, _FakeProc(1, stdout="1 failed\n"))),
    )
    assert pytest_stop.main() == 1
    assert "leaving it for you to review" in capsys.readouterr().err


def test_pytest_stop_tooling_failure_is_noop(monkeypatch, capsys):
    # pytest exit 4 (usage) / 3 (internal) aren't test failures — don't block.
    _feed_stdin(monkeypatch, {})
    monkeypatch.setattr(
        pytest_stop.subprocess,
        "run",
        _fake_run(_git_then_pytest(True, _FakeProc(4, stderr="usage error\n"))),
    )
    assert pytest_stop.main() == 0
    assert capsys.readouterr().err == ""


def test_pytest_stop_no_tests_collected_is_success(monkeypatch):
    _feed_stdin(monkeypatch, {})
    monkeypatch.setattr(
        pytest_stop.subprocess,
        "run",
        _fake_run(_git_then_pytest(True, _FakeProc(5))),
    )
    assert pytest_stop.main() == 0


def test_pytest_stop_skips_and_never_runs_pytest_when_clean(monkeypatch):
    _feed_stdin(monkeypatch, {})
    ran = []

    def handler(cmd):
        if cmd and cmd[0] == "git":
            return _FakeProc(0, stdout="")  # clean tree
        ran.append(cmd)  # a pytest invocation would land here
        return _FakeProc(0)

    monkeypatch.setattr(pytest_stop.subprocess, "run", _fake_run(handler))
    assert pytest_stop.main() == 0
    assert ran == []  # pytest was never spawned


def test_pytest_stop_no_uv_noops(monkeypatch):
    _feed_stdin(monkeypatch, {})

    def handler(cmd):
        if cmd and cmd[0] == "git":
            return _FakeProc(0, stdout=" M streamlit_app.py\n")
        raise FileNotFoundError("uv")  # dirty tree, but no uv to run pytest

    monkeypatch.setattr(pytest_stop.subprocess, "run", _fake_run(handler))
    assert pytest_stop.main() == 0


# ---- _dirty_python fallbacks (missing / erroring git) ----------------------- #
def test_dirty_python_no_git_runs_suite(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(pytest_stop.subprocess, "run", boom)
    assert pytest_stop._dirty_python(None) is True  # no git -> don't gate, run


def test_dirty_python_git_error_runs_suite(monkeypatch):
    monkeypatch.setattr(
        pytest_stop.subprocess,
        "run",
        _fake_run(lambda cmd: _FakeProc(128, stderr="fatal: not a git repo\n")),
    )
    assert pytest_stop._dirty_python(None) is True


# ---- guard_paths: fail-open + the root-less / outside-root match branches --- #
def test_guard_main_malformed_stdin_fails_open(monkeypatch, capsys):
    _feed_stdin(monkeypatch, "not json{")
    assert guard.main() == 0  # fail open, never block on a bad payload
    assert capsys.readouterr().err == ""


def test_guard_protects_basename_and_git_without_root():
    # root=None: the raw absolute path still matches by basename / .git segment.
    assert guard.protected_reason("/anywhere/uv.lock", None) == "/anywhere/uv.lock"
    assert guard.protected_reason("/x/.git/config", None) == "/x/.git/config"


def test_guard_protects_secrets_without_root():
    # Path-tail match: secrets.toml is guarded even when the root can't be
    # resolved and the path stays absolute (it has no distinctive basename).
    p = "/whatever/.streamlit/secrets.toml"
    assert guard.protected_reason(p, None) == p


def test_guard_blocks_git_outside_root(tmp_path):
    # A path outside the project root trips relative_to's ValueError, then matches
    # on the raw path's .git segment (fall-back-to-raw-path branch).
    outside = "/some/other/repo/.git/config"
    assert guard.protected_reason(outside, str(tmp_path)) == outside


# ---- has_dirty_python: git C-quoted / non-ASCII porcelain paths ------------- #
def test_dirty_python_detects_c_quoted_python():
    # git C-quotes non-ASCII names in double quotes (café.py -> "caf\303\251.py");
    # the .strip('"') keeps the `.py` suffix detectable.
    assert pytest_stop.has_dirty_python('?? "caf\\303\\251.py"\n') is True


def test_dirty_python_excludes_c_quoted_dotclaude_nonhook():
    # A quoted .py directly under .claude/ (not a hook) is still excluded.
    assert pytest_stop.has_dirty_python('?? ".claude/na\\303\\257ve.py"\n') is False
