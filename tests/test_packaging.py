"""Project packaging and licensing metadata tests.

Run with: ``uv run pytest``

These guard the licensing story so the places it lives can't silently drift
apart:

- ``pyproject.toml`` — the ``[project].license`` SPDX expression and the
  ``license-files`` entries that flow into the built package metadata,
- the ``LICENSE`` file — kept as *pristine* MIT text (nothing appended), so
  GitHub's license detector classifies the repo as "MIT" and not "Other",
- the ``NOTICE`` file — the third-party notice flagging the two proprietary
  layers it renders with (Highcharts JS / the export server, and the
  ``highcharts-core`` wrapper), split out of ``LICENSE`` precisely so the
  detector isn't thrown off,
- the ``README.md`` ``## License`` section.

They read the files directly (no build step), mirroring the mechanical-sync
idea behind ``test_theme_colors_stay_in_sync_with_config`` in
``test_smoke.py``: a dropped ``license`` field, a deleted ``LICENSE``, prose
re-appended onto ``LICENSE`` (which would re-break detection), or a notice that
quietly stops naming one of the proprietary layers fails fast here.
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
    # PEP 639 SPDX string form (as Streamlit already does), not the
    # deprecated ``license = {text = ...}`` table — so the build emits a
    # ``License-Expression``, and tooling/PyPI read "MIT" from the metadata.
    project = _project_metadata()
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE", "NOTICE"]


def test_license_files_entries_all_exist():
    # ``license-files`` must point at real files, or the built wheel/sdist would
    # advertise a LICENSE it never actually bundles.
    for rel in _project_metadata()["license-files"]:
        assert (ROOT / rel).is_file(), rel


def test_license_file_is_pristine_mit():
    # LICENSE must stay *pristine* MIT so GitHub's license detector — a whole-file
    # similarity match against the SPDX template — keeps classifying it as "MIT",
    # not "Other". The third-party notice lives in NOTICE, not here. Appending
    # ANYTHING after the MIT text (the notice or otherwise) is what re-broke
    # detection, so pin the file to end at the canonical closing sentence.
    text = (ROOT / "LICENSE").read_text()
    assert text.startswith("MIT License")
    assert "Copyright (c)" in text
    # Nothing substantive after the MIT grant, or the file drops below Licensee's
    # template-match threshold and re-classifies as "Other". Normalized
    # (whitespace-collapsed, lowercased) so it's robust to how the closing
    # sentence is line-wrapped; .strip() because _collapse_ws leaves the file's
    # trailing newline as a trailing space. Catches ANY re-append, not just
    # specific keywords — which is what the module docstring promises.
    assert (
        _collapse_ws(text)
        .strip()
        .endswith(
            "out of or in connection with the software or the use or other "
            "dealings in the software."
        )
    )


def test_license_notice_flags_both_proprietary_layers():
    # The value-add over stock MIT is the third-party notice, kept in NOTICE so
    # LICENSE stays detectable. It must name BOTH proprietary layers — the JS
    # everyone thinks of AND the highcharts-core wrapper that is itself
    # proprietary — and say they are not covered by the MIT grant. Dropping
    # either is the exact mistake this pins.
    text = _collapse_ws((ROOT / "NOTICE").read_text())
    assert "highcharts js" in text
    assert "export server" in text
    assert "highcharts-core" in text
    assert "proprietary" in text
    # ...and that the MIT grant is explicitly disclaimed over them (the notice's
    # legal crux) — not merely that the layers are named.
    assert "does not grant" in text


def test_readme_license_section_reflects_mit_and_the_notice():
    readme = (ROOT / "README.md").read_text()
    assert "## License" in readme
    section = _collapse_ws(readme.split("## License", 1)[1])
    # "mit license", not a bare "mit" (which "permit"/"commit" would satisfy).
    assert "mit license" in section
    # Both proprietary layers get surfaced to a reader who never opens LICENSE,
    # with the same proprietary framing the LICENSE-file test pins.
    assert "highcharts js" in section
    assert "export server" in section
    assert "highcharts-core" in section
    assert "proprietary" in section
    # The notice now lives in NOTICE, not LICENSE, so the section must point
    # readers at that file. Match the markdown link's close-bracket + target
    # (`](notice)`) so a stray prose "(NOTICE)" can't satisfy it.
    assert "](notice)" in section
