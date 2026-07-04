"""Project packaging and licensing metadata tests.

Run with: ``uv run pytest``

These guard the licensing story so the three places it lives can't silently
drift apart:

- ``pyproject.toml`` — the ``[project].license`` SPDX expression and the
  ``license-files`` entry that flow into the built package metadata,
- the ``LICENSE`` file — the MIT text for this project's own code plus the
  third-party notice flagging the two proprietary layers it renders with
  (Highcharts JS / the export server, and the ``highcharts-core`` wrapper),
- the ``README.md`` ``## License`` section.

They read the files directly (no build step), mirroring the mechanical-sync
idea behind ``test_theme_colors_stay_in_sync_with_config`` in
``test_smoke.py``: a dropped ``license`` field, a deleted ``LICENSE``, or a
notice that quietly stops naming one of the proprietary layers fails fast here.
"""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _project_metadata() -> dict:
    """The ``[project]`` table from ``pyproject.toml``."""
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]


def _collapse_ws(text: str) -> str:
    """Lowercase and collapse whitespace runs so substring checks ignore how the
    prose is line-wrapped (e.g. "export server" split across two lines)."""
    return re.sub(r"\s+", " ", text.lower())


def test_pyproject_declares_mit_via_spdx():
    # PEP 639 SPDX string form (what Streamlit and pandas use), not the
    # deprecated ``license = {text = ...}`` table — so the build emits a
    # ``License-Expression``, and tooling/PyPI read "MIT" from the metadata.
    project = _project_metadata()
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]


def test_license_files_entries_all_exist():
    # ``license-files`` must point at real files, or the built wheel/sdist would
    # advertise a LICENSE it never actually bundles.
    for rel in _project_metadata()["license-files"]:
        assert (ROOT / rel).is_file(), rel


def test_license_file_is_mit():
    text = (ROOT / "LICENSE").read_text()
    assert text.startswith("MIT License")
    assert "Copyright (c)" in text


def test_license_notice_flags_both_proprietary_layers():
    # The value-add over stock MIT is the third-party notice. It must name BOTH
    # proprietary layers — the JS everyone thinks of AND the highcharts-core
    # wrapper that is itself proprietary — and say they are not covered by the
    # MIT grant. Dropping either is the exact mistake this pins.
    text = _collapse_ws((ROOT / "LICENSE").read_text())
    assert "highcharts js" in text
    assert "export server" in text
    assert "highcharts-core" in text
    assert "proprietary" in text


def test_readme_license_section_reflects_mit_and_the_notice():
    readme = (ROOT / "README.md").read_text()
    assert "## License" in readme
    section = _collapse_ws(readme.split("## License", 1)[1])
    assert "mit" in section
    # Both proprietary layers get surfaced to a reader who never opens LICENSE.
    assert "highcharts js" in section
    assert "highcharts-core" in section
