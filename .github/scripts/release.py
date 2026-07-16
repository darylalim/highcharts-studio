#!/usr/bin/env python3
"""Release automation for highcharts-studio.

Stdlib-only, importable, and runnable as a CLI. The ``release`` job in
``.github/workflows/ci.yml`` calls it to cut a tag + GitHub release the moment
``pyproject.toml``'s version moves to a value that has no ``v{version}`` tag yet —
so a merged version bump can never sit un-released again. (The drift this closes:
the code reached ``0.11.0`` on ``main`` while the newest GitHub release was still
``0.9.0``, because tagging + releasing was a manual step that lagged the merge.)

The two facts a release needs — the current version and that version's changelog
notes — already live in ``pyproject.toml`` and ``CHANGELOG.md``, and are already
pinned to each other by
``tests/test_packaging.py::test_changelog_documents_the_current_version``. This
script only *reads* them, so the release notes are the ``CHANGELOG.md`` section
verbatim and cannot drift from it. The section-extraction and version-reading
logic is kept in pure, importable functions (as the ``.claude/hooks/`` scripts
keep theirs) so ``tests/test_release.py`` can cover it without a subprocess or a
network call; ``main()`` is the thin file-IO/stdout wrapper the workflow calls.
"""

import re
import sys
import tomllib
from pathlib import Path

# release.py lives at <root>/.github/scripts/release.py, so root is two up.
ROOT = Path(__file__).resolve().parents[2]


def read_version(pyproject_text: str) -> str:
    """The ``[project].version`` string from ``pyproject.toml`` text."""
    return tomllib.loads(pyproject_text)["project"]["version"]


def extract_release_notes(changelog_text: str, version: str) -> str:
    """The body of ``CHANGELOG.md``'s ``## [<version>]`` section, verbatim.

    Returns everything between that heading and the next ``## [`` heading (or the
    end of the file), stripped of surrounding blank lines — keyed on the same
    heading shape ``test_changelog_documents_the_current_version`` matches. Raises
    ``ValueError`` if the section is absent or empty, so the release step fails
    loudly rather than cutting a release with no notes (belt-and-braces: on a green
    build that test already guarantees the current version has a section here).
    """
    heading = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n", changelog_text, re.M)
    if heading is None:
        raise ValueError(f"CHANGELOG.md has no `## [{version}]` section")
    rest = changelog_text[heading.end() :]
    nxt = re.search(r"^## \[", rest, re.M)
    body = (rest[: nxt.start()] if nxt else rest).strip()
    if not body:
        raise ValueError(f"CHANGELOG.md's `## [{version}]` section is empty")
    return body


def main(argv: list[str] | None = None) -> int:
    """CLI: ``version`` prints the current version, ``notes`` prints its notes."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in {"version", "notes"}:
        print("usage: release.py {version|notes}", file=sys.stderr)
        return 2
    version = read_version((ROOT / "pyproject.toml").read_text())
    if args[0] == "version":
        print(version)
    else:  # notes
        print(extract_release_notes((ROOT / "CHANGELOG.md").read_text(), version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
