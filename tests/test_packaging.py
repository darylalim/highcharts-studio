"""Project packaging and licensing metadata tests.

Run with: ``uv run pytest``

These guard the packaging, licensing, and README metadata so the places each
lives can't silently drift apart:

- ``pyproject.toml`` — the ``[project].license`` SPDX expression and the
  ``license-files`` entries that flow into the built package metadata,
- the ``LICENSE`` file — kept as *pristine* MIT text (nothing appended), so
  GitHub's license detector classifies the repo as "MIT" and not "Other",
- the ``NOTICE`` file — the third-party notice flagging the two proprietary
  layers it renders with (Highcharts JS / the export server, and the
  ``highcharts-core`` wrapper), split out of ``LICENSE`` precisely so the
  detector isn't thrown off,
- the ``README.md`` ``## License`` section,
- the ``README.md`` header badges — the MIT / Python / Streamlit badges pinned
  to the same ``pyproject.toml`` facts they advertise (both the shields URL slug
  and the human-readable label), and the CI badge to a workflow file that exists
  with an owner/repo slug that agrees between its image and click-through link,
- the ``README.md`` ``## Contents`` table of contents — pinned to equal the
  real ``##`` section headings, so a renamed, added, or removed section can't
  leave a dead jump-link,
- the ``CHANGELOG.md`` newest entry — pinned to ``pyproject.toml``'s
  ``[project].version``, which until it had a changelog was the one packaging
  fact with *no second home*: the badges pin the version *floors*, the SPDX
  fields pin ``LICENSE``/``NOTICE``, but ``version`` itself was asserted by
  nothing, so nothing could catch a release that shipped without its notes.

They read the files directly (no build step), mirroring the mechanical-sync
idea behind ``test_theme_colors_stay_in_sync_with_config`` in
``test_smoke.py``: a dropped ``license`` field, a deleted ``LICENSE``, prose
re-appended onto ``LICENSE`` (which would re-break detection), a notice that
quietly stops naming one of the proprietary layers, a badge left stale after a
version bump, a section renamed out from under the table of contents, or a
version bumped without cutting a changelog section all fail fast here.
"""

import importlib.util
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_release():
    """Import ``.github/scripts/release.py`` — the canonical CHANGELOG parser, so
    the changelog-version test reuses its heading logic instead of re-encoding the
    ``## [x.y.z]`` regex (which would give the format a second home to drift in)."""
    path = ROOT / ".github" / "scripts" / "release.py"
    spec = importlib.util.spec_from_file_location("_release_for_packaging", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_release = _load_release()


def _project_metadata() -> dict:
    """The ``[project]`` table from ``pyproject.toml``."""
    return tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]


def _collapse_ws(text: str) -> str:
    """Lowercase and collapse whitespace runs so substring checks ignore how the
    prose is line-wrapped (e.g. "export server" split across two lines)."""
    return re.sub(r"\s+", " ", text.lower())


def _readme() -> str:
    """The README.md text."""
    return (ROOT / "README.md").read_text()


def _changelog() -> str:
    """The CHANGELOG.md text."""
    return (ROOT / "CHANGELOG.md").read_text()


def _strip_code_fences(md: str) -> str:
    """Drop ``` fenced blocks so shell snippets can't masquerade as ## headings."""
    return re.sub(r"```.*?```", "", md, flags=re.DOTALL)


def _github_slug(heading: str) -> str:
    """GitHub's header-anchor slug: lowercase, strip punctuation (keep word
    chars, spaces, hyphens), then spaces -> hyphens. "Lint & format" ->
    "lint--format"; "What it does" -> "what-it-does"."""
    return re.sub(r"[^\w\s-]", "", heading.strip().lower()).replace(" ", "-")


def _req_name(dep: str) -> str:
    """The PEP 508 project name from a dependency string — the part before any
    version specifier, marker, extras, or whitespace, lowercased so the match is
    case-insensitive (``Streamlit>=1.57`` and ``streamlit`` both -> "streamlit")."""
    return re.split(r"[<>=!~;\[\s]", dep, maxsplit=1)[0].strip().lower()


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
    readme = _readme()
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


def test_readme_badges_stay_in_sync_with_project():
    # The header badges surface packaging facts — the license and the
    # Python/Streamlit version floors — that already live in pyproject.toml, so
    # they silently lie the moment a floor is bumped and the badge isn't. Pin each
    # to its source of truth (same mechanical-sync idea as the license section,
    # extended to the shields.io badges).
    readme = _readme()
    project = _project_metadata()

    # MIT license badge <-> [project].license — both the shields URL slug and the
    # human-readable alt-text label (same line, but they can drift apart).
    assert project["license"] == "MIT"
    assert "License-MIT" in readme
    assert "License: MIT" in readme

    # Python floor badge <-> requires-python (e.g. ">=3.12" -> "python-3.12%2B"),
    # pinning the URL slug and the "Python 3.12+" label.
    py_match = re.search(r"(\d+\.\d+)", project["requires-python"])
    assert py_match, "requires-python floor is unparseable"
    py_floor = py_match.group(1)
    assert f"python-{py_floor}%2B" in readme, (
        f"Python badge should advertise the requires-python floor {py_floor}"
    )
    assert f"Python {py_floor}+" in readme, (
        f"Python badge label should read 'Python {py_floor}+'"
    )

    # Streamlit floor badge <-> the streamlit dependency floor. Match the PEP 508
    # name exactly (not a loose prefix, which would also catch a `streamlit-*`
    # plugin) and default None so a rename/typo fails with a clear message rather
    # than a bare StopIteration.
    st_dep = next(
        (d for d in project["dependencies"] if _req_name(d) == "streamlit"), None
    )
    assert st_dep, "no streamlit dependency found in pyproject dependencies"
    st_match = re.search(r">=(\d+\.\d+)", st_dep)
    assert st_match, f"streamlit dependency floor is unparseable: {st_dep!r}"
    st_floor = st_match.group(1)
    assert f"streamlit-{st_floor}%2B" in readme, (
        f"Streamlit badge should advertise the dependency floor {st_floor}"
    )
    assert f"Streamlit {st_floor}+" in readme, (
        f"Streamlit badge label should read 'Streamlit {st_floor}+'"
    )

    # CI badge must point at a workflow file that exists, and its image src and
    # the click-through link must agree on the owner/repo slug — a rename or a
    # typo in just one silently 404s the badge (broken image or dead link).
    ci_img = re.search(
        r"github\.com/([\w.-]+/[\w.-]+)/actions/workflows/([\w.-]+)/badge\.svg",
        readme,
    )
    assert ci_img, "CI status badge is missing or malformed"
    img_slug, workflow = ci_img.groups()
    assert (ROOT / ".github" / "workflows" / workflow).is_file()
    ci_link = re.search(
        r"github\.com/([\w.-]+/[\w.-]+)/actions/workflows/"
        + re.escape(workflow)
        + r"\)",
        readme,
    )
    assert ci_link, "CI badge click-through link is missing or malformed"
    assert img_slug == ci_link.group(1), (
        "CI badge image and link owner/repo slugs disagree"
    )


def test_readme_toc_covers_every_section():
    # The ## Contents jump-list duplicates the section structure, so a renamed,
    # added, or removed section silently breaks a link (or leaves a dead entry).
    # Pin the TOC targets to equal the real ## headings (minus Contents itself),
    # both directions — a missing OR a stale entry fails here.
    body = _strip_code_fences(_readme())
    headings = [h.strip() for h in re.findall(r"^## (.+)$", body, re.MULTILINE)]
    section_slugs = {_github_slug(h) for h in headings if h != "Contents"}

    toc_block = body.split("## Contents", 1)[1].split("\n## ", 1)[0]
    toc_anchors = set(re.findall(r"\]\(#([\w-]+)\)", toc_block))

    assert toc_anchors == section_slugs, (
        f"TOC out of sync with sections — "
        f"only in TOC: {toc_anchors - section_slugs}; "
        f"missing from TOC: {section_slugs - toc_anchors}"
    )


def test_changelog_documents_the_current_version():
    # ``version`` was the one packaging fact this suite left un-cross-checked. The
    # badges are pinned to the version *floors*, the SPDX fields to LICENSE/NOTICE,
    # the TOC to the real headings — but ``[project].version`` was asserted by
    # nothing, so it could neither drift nor be verified: a number with no second
    # home. That is not a hypothetical gap. Five chart types (sankey, boxplot,
    # waterfall, sunburst, xrange) all shipped while the version sat at 0.6.0,
    # because nothing asked it to move. CHANGELOG.md is the second home, and this
    # is the gate: bump one without the other and the release ships undocumented
    # (or the notes describe a version nobody cut).
    version = _project_metadata()["version"]

    # Keep a Changelog is reverse-chronological, so the FIRST ``## [x.y.z]`` heading
    # is the current release. ``changelog_versions`` (the release script's parser,
    # reused here so the heading regex has a single home) matches only released,
    # numbered sections, which is what lets an ``## [Unreleased]`` heading be kept
    # above it without being mistaken for one.
    versions = _release.changelog_versions(_changelog())
    assert versions, "CHANGELOG.md has no released `## [x.y.z]` section"
    assert versions[0] == version, (
        f"CHANGELOG.md's newest entry is {versions[0]}, but pyproject.toml "
        f"declares version {version} — one of the two was bumped and the other "
        f"was not."
    )
