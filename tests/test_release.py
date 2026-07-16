"""Tests for the release automation script in ``.github/scripts/release.py``.

Run with: ``uv run pytest``

``release.py`` is dev/CI tooling — the ``release`` job in ``.github/workflows/
ci.yml`` calls it to cut a tag + GitHub release when ``pyproject.toml``'s version
moves to a value with no ``v{version}`` tag yet. Its pure functions carry the only
logic worth regression-testing: reading the current version and slicing the
matching ``CHANGELOG.md`` section out **verbatim** (so the release notes can't
drift from the changelog). They're exercised directly here — no subprocess, no
git, no network — like the ``.claude/hooks/`` decision functions in
``test_hooks.py``.

The script lives outside any importable package, so it's loaded by file path via
``importlib`` (importing only defines functions; ``main()`` is behind an
``if __name__ == "__main__"`` guard, so there are no import side effects).
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / ".github" / "scripts" / "release.py"


def _load():
    """Import ``.github/scripts/release.py`` by file path."""
    spec = importlib.util.spec_from_file_location("_release", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = _load()

# A miniature CHANGELOG in the repo's real shape: a prose preamble (which must not
# be mistaken for a section), then reverse-chronological ``## [x.y.z]`` entries,
# some with an ``### Added``/``### Notes`` split, the oldest running to EOF.
SAMPLE = """# Changelog

Preamble prose. `0.7.0` was the first release; nothing here is a ## heading.

## [0.11.0] - 2026-07-16

### Added

- funnel and pyramid.

## [0.10.0] - 2026-07-15

### Added

- columnrange.

### Notes

- a measured note.

## [0.9.0] - 2026-07-15

- older stuff.
"""


def test_read_version_pulls_project_version():
    assert release.read_version('[project]\nversion = "1.2.3"\n') == "1.2.3"


def test_extract_release_notes_is_bounded_by_its_two_headings():
    notes = release.extract_release_notes(SAMPLE, "0.10.0")
    # Own body, verbatim, including the sub-headings.
    assert notes.startswith("### Added")
    assert "columnrange." in notes
    assert "### Notes" in notes
    assert "a measured note." in notes
    # No bleed from the newer section above it...
    assert "funnel and pyramid" not in notes
    # ...nor into the older one below it.
    assert "older stuff" not in notes


def test_extract_release_notes_last_section_runs_to_eof():
    # The oldest section has no following ``## [`` heading to stop at.
    assert release.extract_release_notes(SAMPLE, "0.9.0") == "- older stuff."


def test_extract_release_notes_strips_surrounding_blank_lines():
    # The heading is followed by a blank line and the section by another; neither
    # should survive into the emitted notes.
    notes = release.extract_release_notes(SAMPLE, "0.11.0")
    assert notes == "### Added\n\n- funnel and pyramid."


def test_extract_release_notes_missing_version_raises():
    with pytest.raises(ValueError, match="9.9.9"):
        release.extract_release_notes(SAMPLE, "9.9.9")


def test_extract_release_notes_empty_section_raises():
    # A version whose section body is only whitespace must fail loudly, never cut a
    # blank release.
    changelog = "## [1.0.0] - x\n\n## [0.9.0] - y\n\nbody\n"
    with pytest.raises(ValueError, match="empty"):
        release.extract_release_notes(changelog, "1.0.0")


def test_current_version_has_nonempty_release_notes():
    """No-drift, against the real files: the version the workflow will read has a
    non-empty CHANGELOG section, so a push that bumps it can actually be released.

    (``test_changelog_documents_the_current_version`` pins that the section is for
    the *right* version; this pins that the extractor the workflow runs can read
    it.)"""
    version = release.read_version((ROOT / "pyproject.toml").read_text())
    notes = release.extract_release_notes((ROOT / "CHANGELOG.md").read_text(), version)
    assert notes
