"""Smoke and behavior tests for the Highcharts builder and the Streamlit app.

Run with: ``uv run pytest``

Layers:

- ``build_options`` unit tests covering every supported chart type, the
  missing-data and scatter/bubble edge cases (NaN -> ``EnforcedNull`` for
  cartesian and radar series, dropped points/slices elsewhere, numeric vs
  non-numeric x, and bubble's (x, y, size) triples whose series share one size
  column, its ``highcharts-more`` module resolution, and its dimension-naming
  tooltip), non-finite data (an ``inf`` is not missing but can't be serialized —
  ``to_js_literal`` emits the bare token ``inf``, a JS ReferenceError, and the
  export server 400s — so every type applies its own missing-data policy to it,
  swept over ``SUPPORTED_TYPES``), radar's polar-line shape (chart.type "line" + ``chart.polar``,
  sharing the ``highcharts-more`` module), heatmap's category × category value
  matrix (``[x, y, value]`` cells colored by a ``colorAxis``, empty cells kept as
  ``EnforcedNull``, resolving its own ``modules/heatmap.js``), treemap's
  value-sized tiles (``{name, value}`` leaves colored categorically via
  ``colorByPoint``, missing values dropped like pie, resolving its own
  ``modules/treemap.js``), sankey's node-link flows (``{from, to, weight}`` links
  over two node columns, rows missing any of the three dropped like pie's slices,
  its node tooltip and its per-link weight labels each pinned to the one place
  highcharts-core doesn't silently drop them, those labels gated on link count,
  resolving its own ``modules/sankey.js``), boxplot's per-category Tukey
  distributions (the one AGGREGATING builder: raw observations grouped by a
  repeating ``x_col`` into positional ``[low, q1, median, q3, high]`` 5-arrays,
  outliers split off into a linked scatter series emitted only when they exist,
  the ``iqr == 0`` degeneracies that the inclusive fence saves, the matplotlib
  whisker clamp, an all-missing group kept as an ``EnforcedNull`` box, and the
  ``fillColor``/``stemColor`` silent drop that leaves its box interior unsettable —
  sharing bubble's and radar's ``highcharts-more``), the brand-palette
  (``DEFAULT_COLORS`` / ``colors`` override), and the validation guards
  (unsupported type, empty ``y_cols``, the category-x x-in-y rule widened to
  heatmap and boxplot, the bubble size-column requirement, and sankey's required,
  distinct target column).
- light/dark theming: dark mode paints the chart background (light leaves it
  unset), the chart chrome (axes/text/gridlines, pie labels, and the tooltip)
  flips while the ``DEFAULT_COLORS`` palette stays shared across modes,
  ``build_chart_html`` gives the iframe body a background that tracks the mode,
  and it pins the chart's ``color-scheme`` so Highcharts' own ``light-dark()``
  defaults resolve to the export server's values rather than the viewer's browser.
- ``sample_data`` unit tests: every built-in dataset is plottable (fresh,
  non-empty, with a numeric column).
- Headless ``AppTest`` interaction tests that drive the full Streamlit app's
  control flow — switching chart type (including bubble, which reveals a
  Size (Z) control, radar, heatmap, treemap, sankey, which reveals a
  Target (to) control, and boxplot, which reveals a single-select Y and no extra
  control at all), title, and series, revealing
  the generated Highcharts config
  behind its toggle, the KPI metric row, the wide-CSV multiselect fallback, and
  the render-mode selector's two modes (interactive iframe / static PNG), plus
  tripping the x-in-y warning and the no-CSV-uploaded info guard — asserting on
  the generated config (incl. the brand palette) and the guard messages.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest
from highcharts_core.constants import EnforcedNull

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from highcharts_builder import (  # noqa: E402
    CARTESIAN_TYPES,
    CATEGORY_X_TYPES,
    DEFAULT_COLORS,
    SUPPORTED_TYPES,
    build_chart_html,
    build_options,
)


@pytest.fixture
def labeled_frame() -> pd.DataFrame:
    """A label column plus a numeric column — valid input for every chart type.

    The second label column ("target") is there for sankey alone, whose links need a
    node column at each end. Every other type names the columns it reads, so the
    extra one is inert (it isn't numeric, so it can't perturb a y-column sweep).
    """
    return pd.DataFrame(
        {"label": ["a", "b", "c"], "target": ["x", "y", "z"], "value": [1.0, 2.0, 3.0]}
    )


def _size_for(chart_type: str) -> str | None:
    """The size column the SUPPORTED_TYPES-parametrized tests pass for the bubble
    case: bubble requires one (its marker-size dimension); other types ignore it,
    so it's None. The shared ``labeled_frame`` has "value" as its only numeric
    column, so it doubles as the size."""
    return "value" if chart_type == "bubble" else None


def _target_for(chart_type: str) -> str | None:
    """The target column those same sweeps pass for the sankey case: sankey requires
    one (the far end of every link); other types ignore it, so it's None. The
    ``_size_for`` idea, for the other type with a required companion column — the
    sweeps assert invariants that must hold for *every* type (it builds, it carries
    the palette, dark mode paints the background), so a type that needs an extra
    column adapts its input rather than dropping out."""
    return "target" if chart_type == "sankey" else None


# Radar is the one "meta" type: Highcharts has no radar series type, so it renders
# as a polar *line* chart — its chart.type serializes as "line", not "radar".
# Every other supported type's chart.type equals its own name.
_HC_TYPE = {"radar": "line"}


def _hc_type(chart_type: str) -> str:
    """The Highcharts ``chart.type`` a supported type renders as: identity for all
    but radar, which is a polar line."""
    return _HC_TYPE.get(chart_type, chart_type)


# --------------------------------------------------------------------------- #
# Every supported type builds
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_supported_type_builds(labeled_frame, chart_type):
    opts = build_options(
        labeled_frame,
        chart_type,
        "label",
        ["value"],
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
    )
    assert opts["chart"]["type"] == _hc_type(chart_type)
    assert opts["series"]  # at least one series/data set was produced


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_supported_type_builds_a_working_highcharts_core_chart(
    labeled_frame, chart_type
):
    # build_options's SUPPORTED_TYPES check only guards against a Python-level
    # typo — it can't catch a chart_type string highcharts-core itself would
    # reject. Drive every type through the real pipeline (make_chart ->
    # Chart.from_options -> to_js_literal), not just the options dict. This is the
    # only test that proves the pie, scatter, and radar branches serialize: they
    # hardcode their chart.type literal (scatter also its zooming block, radar its
    # `line` + polar) rather than using the chart_type variable, so nothing else
    # validates those literals end to end. Radar renders as a polar line, so its
    # serialized type is "line" (see _hc_type), not "radar".
    from highcharts_builder import make_chart

    js = make_chart(
        labeled_frame,
        chart_type,
        "label",
        ["value"],
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
    ).to_js_literal()
    assert js and f"type: '{_hc_type(chart_type)}'" in js


@pytest.fixture
def non_finite_frame() -> pd.DataFrame:
    """``labeled_frame``'s shape, but the numeric column carries an infinity at each end
    and one drawable value. Every type reads x from "label" and y from "value", so the
    one frame exercises all of them (bubble takes "value" as its size too, sankey as its
    weight — see ``_size_for``/``_target_for``)."""
    return pd.DataFrame(
        {
            "label": ["a", "b", "c"],
            "target": ["x", "y", "z"],
            "value": [float("inf"), float("-inf"), 9.0],
        }
    )


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_no_supported_type_emits_a_non_finite_js_literal(non_finite_frame, chart_type):
    # An infinity is not missing — pd.isna(inf) is False — but it cannot be serialized:
    # to_js_literal renders it as the bare token `inf`, which is not a JavaScript
    # identifier (JS spells it `Infinity`), so the whole Highcharts.chart(...) call dies
    # with a ReferenceError and the iframe renders blank. The static path fares no better:
    # the export server is handed the non-standard JSON literal `Infinity` and answers
    # 400, which the app then misreports as an unreachable server. Both were live bugs in
    # every type before `_plottable`. Only the emitted JS can prove the fix, and this
    # sweeps SUPPORTED_TYPES so a newly added type is covered the day it is added.
    from highcharts_builder import make_chart

    js = make_chart(
        non_finite_frame,
        chart_type,
        "label",
        ["value"],
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
    ).to_js_literal()
    assert js
    # `Infinity` is capitalized, so a lowercase "inf" can only be the broken token. None
    # of the column names, titles or type names above contains "inf"/"nan" either.
    for token in ("inf", "nan", "NaN"):
        assert token not in js, f"{chart_type} emitted a non-finite literal: {token}"


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_missing_or_non_finite_label_drops_the_row_in_every_type(chart_type):
    # The counterpart to the value-column sweep above, for the LABEL column (the one that
    # NAMES a mark: a pie slice, an axis category, a sankey node, a boxplot group). A
    # missing or non-finite label names nothing drawable, so its row is dropped in EVERY
    # type — not rendered as a slice/category/node/box labelled the literal "nan"/"inf".
    # This is the value-column missing-data policy extended to the label column, and it is
    # uniform now: before, most types kept the "nan" mark and only sankey and boxplot
    # dropped it. Proven on the emitted JS (a kept NaN/inf label stringifies to the quoted
    # category 'nan'/'inf', which contains the token; the good rows never do).
    from highcharts_builder import make_chart

    # A NaN in a STRING label column (object dtype, so scatter/bubble take the
    # non-numeric-x path) and an inf in a NUMERIC label column (so they take the numeric-x
    # path `_plottable` guards) — both label channels, so no type slips through on either.
    nan_df = pd.DataFrame(
        {
            "label": ["a", float("nan"), "c"],
            "to": ["x", "y", "z"],
            "value": [1.0, 2.0, 3.0],
        }
    )
    inf_df = pd.DataFrame(
        {
            "label": [1.0, float("inf"), 3.0],
            "to": [9.0, 8.0, 7.0],
            "value": [1.0, 2.0, 3.0],
        }
    )
    for df, token in ((nan_df, "nan"), (inf_df, "inf")):
        js = make_chart(
            df,
            chart_type,
            "label",
            ["value"],
            size_col=_size_for(chart_type),
            target_col="to" if chart_type == "sankey" else None,
        ).to_js_literal()
        assert js and token not in js.lower(), f"{chart_type} kept a '{token}' label"


def test_num_maps_missing_and_non_finite_to_enforced_null():
    from highcharts_builder import _num, _plottable

    assert _num(1.5) == 1.5
    assert _num(float("nan")) is EnforcedNull
    assert _num(float("inf")) is EnforcedNull  # not missing, but not drawable
    assert _num(float("-inf")) is EnforcedNull
    # The drop-path predicate agrees with the keep-the-slot one on what is drawable.
    assert _plottable(1.5)
    assert not _plottable(float("nan"))
    assert not _plottable(float("inf"))
    assert not _plottable(float("-inf"))


@pytest.mark.parametrize("chart_type", CATEGORY_X_TYPES)
def test_category_x_non_finite_becomes_enforced_null(chart_type):
    # The keep-the-slot family treats an infinity exactly as it treats a NaN: a gap in the
    # line, not a dropped point — so the categories stay aligned with the data.
    df = pd.DataFrame({"x": ["a", "b", "c"], "y": [1.0, float("inf"), 3.0]})
    data = build_options(df, chart_type, "x", ["y"])["series"][0]["data"]
    assert data == [1.0, EnforcedNull, 3.0]


def test_heatmap_non_finite_cell_becomes_enforced_null():
    df = pd.DataFrame({"day": ["Mon", "Tue"], "AM": [1.0, float("-inf")]})
    data = build_options(df, "heatmap", "day", ["AM"])["series"][0]["data"]
    assert len(data) == 2  # the grid never collapses
    assert data[1][2] is EnforcedNull


@pytest.mark.parametrize("chart_type", ["pie", "treemap"])
def test_single_value_types_drop_a_non_finite_row(chart_type):
    # The drop-the-row family drops an infinity exactly as it drops a NaN: a slice or tile
    # can no more be sized by infinity than by nothing.
    df = pd.DataFrame({"n": ["a", "b", "c"], "v": [1.0, float("inf"), 3.0]})
    data = build_options(df, chart_type, "n", ["v"])["series"][0]["data"]
    assert [point["name"] for point in data] == ["a", "c"]


def test_scatter_and_bubble_drop_non_finite_points():
    inf = float("inf")
    xy = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [10.0, inf, 30.0]})
    assert build_options(xy, "scatter", "x", ["y"])["series"][0]["data"] == [
        [1.0, 10.0],
        [3.0, 30.0],
    ]
    # An infinite x drops the point too, not just an infinite y.
    xinf = pd.DataFrame({"x": [1.0, inf, 3.0], "y": [10.0, 20.0, 30.0]})
    assert build_options(xinf, "scatter", "x", ["y"])["series"][0]["data"] == [
        [1.0, 10.0],
        [3.0, 30.0],
    ]
    # And so does an infinite SIZE, which would otherwise ask for a bubble of infinite area.
    zinf = pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0], "s": [5.0, -inf]})
    assert build_options(zinf, "bubble", "x", ["y"], size_col="s")["series"][0][
        "data"
    ] == [[1.0, 3.0, 5.0]]


def test_sankey_drops_a_non_finite_weight_and_a_non_finite_node_label():
    inf = float("inf")
    df = pd.DataFrame({"s": ["a", "b"], "t": ["c", "d"], "w": [inf, 5.0]})
    assert _links(build_options(df, "sankey", "s", ["w"], target_col="t")) == [
        {"from": "b", "to": "d", "weight": 5.0}
    ]
    # A node column is a LABEL, and a non-finite label names nothing drawable: it would
    # stringify to a node literally named "inf". Under the uniform label policy (`_label_ok`)
    # that row is dropped in EITHER end — the source (filtered up front) or the target
    # (checked in the sankey branch) — exactly as every other type now drops a "nan"/"inf"
    # label, rather than the old sankey-only exception that kept the "inf" node.
    src_inf = pd.DataFrame({"s": [inf, "a"], "t": ["d", "e"], "w": [5.0, 6.0]})
    assert _links(build_options(src_inf, "sankey", "s", ["w"], target_col="t")) == [
        {"from": "a", "to": "e", "weight": 6.0}
    ]
    dst_inf = pd.DataFrame({"s": ["a", "b"], "t": [inf, "e"], "w": [5.0, 6.0]})
    assert _links(build_options(dst_inf, "sankey", "s", ["w"], target_col="t")) == [
        {"from": "b", "to": "e", "weight": 6.0}
    ]


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_default_title_per_type(labeled_frame, chart_type):
    opts = build_options(
        labeled_frame,
        chart_type,
        "label",
        ["value"],
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
    )
    assert opts["title"]["text"] == f"{chart_type.title()} chart"


def test_explicit_title_overrides_default(labeled_frame):
    opts = build_options(labeled_frame, "line", "label", ["value"], title="Custom")
    assert opts["title"]["text"] == "Custom"


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_default_palette_applied_per_type(labeled_frame, chart_type):
    # Every chart type carries the brand palette so all render modes share a look.
    opts = build_options(
        labeled_frame,
        chart_type,
        "label",
        ["value"],
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
    )
    assert opts["colors"] == list(DEFAULT_COLORS)


def test_colors_override(labeled_frame):
    opts = build_options(
        labeled_frame, "line", "label", ["value"], colors=["#000000", "#ffffff"]
    )
    assert opts["colors"] == ["#000000", "#ffffff"]


# --------------------------------------------------------------------------- #
# Dark theme: only the chart "chrome" flips; the series palette is shared across
# modes (so a series keeps its color when the viewer toggles), and light mode is
# a byte-for-byte no-op.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_dark_mode_sets_chart_background(labeled_frame, chart_type):
    # Dark mode paints the chart background so it matches the dark app shell
    # (kept in sync with .streamlit/config.toml [theme.dark] backgroundColor).
    opts = build_options(
        labeled_frame,
        chart_type,
        "label",
        ["value"],
        dark=True,
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
    )
    assert opts["chart"]["backgroundColor"] == "#0f172a"


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_light_mode_leaves_chart_background_unset(labeled_frame, chart_type):
    # Light mode is a no-op: no backgroundColor is injected, so the output is
    # exactly what it was before dark mode existed.
    opts = build_options(
        labeled_frame,
        chart_type,
        "label",
        ["value"],
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
    )
    assert "backgroundColor" not in opts["chart"]


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_dark_mode_keeps_the_shared_palette(labeled_frame, chart_type):
    opts = build_options(
        labeled_frame,
        chart_type,
        "label",
        ["value"],
        dark=True,
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
    )
    assert opts["colors"] == list(DEFAULT_COLORS)


def test_dark_mode_themes_cartesian_axes_text_and_legend():
    # Two series so the legend is enabled and its recoloring is meaningful.
    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2], "z": [3, 4]})
    opts = build_options(df, "line", "x", ["y", "z"], dark=True)
    assert opts["title"]["style"]["color"] == "#e2e8f0"
    # Axis labels + title, and the line/tick/gridline colors, all flip.
    assert opts["xAxis"]["labels"]["style"]["color"] == "#94a3b8"
    assert opts["xAxis"]["title"]["style"]["color"] == "#94a3b8"
    assert opts["xAxis"]["lineColor"] == "#475569"
    assert opts["xAxis"]["tickColor"] == "#475569"
    assert opts["yAxis"]["gridLineColor"] == "#334155"
    # Legend text recolors too (dark-on-dark would be unreadable otherwise).
    assert opts["legend"]["itemStyle"]["color"] == "#e2e8f0"
    assert opts["legend"]["itemHoverStyle"]["color"] == "#94a3b8"


@pytest.mark.parametrize("chart_type", ["column", "bar"])
def test_dark_mode_matches_column_bar_borders_to_the_background(chart_type):
    # column/bar draw a 1px border per bar that defaults to the light background
    # variable; the color-scheme pin keeps it white even in dark mode, ringing every
    # bar. Match it to the dark background so the separators vanish as they do in light
    # mode — the pie/treemap/sankey slice-gap rule, which these two were missing. The
    # cartesian branch emits no plotOptions, so the hook must create it.
    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2]})
    opts = build_options(df, chart_type, "x", ["y"], dark=True)
    assert opts["plotOptions"][chart_type]["borderColor"] == "#0f172a"
    # The line family draws no such border, so it stays untouched (no dead plotOptions).
    assert "plotOptions" not in build_options(df, "line", "x", ["y"], dark=True)
    # Light mode is the documented no-op: no border injected at all.
    assert "plotOptions" not in build_options(df, chart_type, "x", ["y"])


def test_dark_mode_themes_pie_labels_and_skips_axes():
    df = pd.DataFrame({"name": ["A", "B"], "v": [1.0, 2.0]})
    opts = build_options(df, "pie", "name", ["v"], dark=True)
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    assert opts["plotOptions"]["pie"]["dataLabels"]["color"] == "#e2e8f0"
    # Pie has no axes, so the axis-theming loop must simply skip it (not crash).
    assert "xAxis" not in opts


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_dark_mode_themes_the_tooltip(labeled_frame, chart_type):
    # The tooltip is lazily rendered by Highcharts and defaults to a light box, so
    # dark mode must theme it explicitly or it floats light-on-dark on hover.
    opts = build_options(
        labeled_frame,
        chart_type,
        "label",
        ["value"],
        dark=True,
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
    )
    assert opts["tooltip"]["backgroundColor"] == "#0f172a"
    assert opts["tooltip"]["borderColor"] == "#475569"
    assert opts["tooltip"]["style"]["color"] == "#e2e8f0"


def test_dark_mode_tooltip_merge_preserves_pie_point_format():
    # Theming MERGES rather than clobbers: the pie path's custom pointFormat lives.
    opts = build_options(
        pd.DataFrame({"name": ["A", "B"], "v": [1.0, 2.0]}),
        "pie",
        "name",
        ["v"],
        dark=True,
    )
    assert opts["tooltip"]["backgroundColor"] == "#0f172a"
    assert "point.percentage" in opts["tooltip"]["pointFormat"]


def test_light_mode_leaves_tooltip_chrome_unset():
    # Light mode stays a no-op: cartesian output has no tooltip key at all, and the
    # pie tooltip keeps only its pointFormat with no injected dark chrome.
    line = build_options(
        pd.DataFrame({"x": ["a", "b"], "y": [1, 2]}), "line", "x", ["y"]
    )
    assert "tooltip" not in line
    pie = build_options(
        pd.DataFrame({"name": ["A", "B"], "v": [1.0, 2.0]}), "pie", "name", ["v"]
    )
    assert "backgroundColor" not in pie["tooltip"]


def test_build_chart_html_body_background_tracks_mode():
    # The iframe body background is painted to match the chart so there's no
    # light flash at the edges in dark mode; light stays white.
    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2]})
    assert "background:#0f172a" in build_chart_html(df, "line", "x", ["y"], dark=True)
    assert "background:#ffffff" in build_chart_html(df, "line", "x", ["y"])


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("chart_type", ["line", "boxplot"])
def test_build_chart_html_pins_the_chart_color_scheme(chart_type, dark):
    # Highcharts >= 13 defines its defaults as `light-dark()` CSS variables, so every
    # color we don't set explicitly would resolve against the VIEWER'S BROWSER rather
    # than our `dark` flag. Two real failures followed: a light-mode chart painted itself
    # dark (#141414 background, pale text) on a dark-OS browser, and a boxplot's box fill
    # — the one mark color highcharts-core cannot express — differed between the iframe
    # and the export-server PNG. Pinning the chart root to `only light` makes the iframe
    # resolve those defaults exactly as the export server does, in BOTH modes, leaving
    # `_themed` the single source of truth for dark mode.
    #
    # The selector must be `.highcharts-root` (the <svg>): Highcharts sets `color-scheme`
    # on that element, so a rule on `html` is overridden by it.
    df = pd.DataFrame({"g": ["a", "a", "b", "b"], "v": [1.0, 2.0, 3.0, 4.0]})
    html = build_chart_html(df, chart_type, "g", ["v"], dark=dark)
    assert ".highcharts-root{color-scheme:only light}" in html
    # It is pinned regardless of mode — dark mode is expressed in the options, not here.
    assert "color-scheme:only dark" not in html


def test_theme_colors_stay_in_sync_with_config():
    # A few chart-chrome colors duplicate config.toml theme values (the builder
    # is Streamlit-free, so it can't read the resolved theme at runtime). Guard
    # the sync mechanically here instead of relying on cross-referencing comments.
    import tomllib

    from highcharts_builder import _DARK_CHROME

    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["theme"]
    assert _DARK_CHROME["bg"] == theme["dark"]["backgroundColor"]
    assert _DARK_CHROME["text"] == theme["dark"]["textColor"]
    assert DEFAULT_COLORS[0] == theme["light"]["primaryColor"]


# --------------------------------------------------------------------------- #
# Cartesian: line / spline / area / areaspline / column / bar
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("chart_type", CARTESIAN_TYPES)
def test_cartesian_categories_and_series(chart_type):
    df = pd.DataFrame({"x": ["a", "b", "c"], "y": [1, 2, 3]})
    opts = build_options(df, chart_type, "x", ["y"])
    assert opts["chart"]["type"] == chart_type
    assert opts["xAxis"]["categories"] == ["a", "b", "c"]
    assert opts["xAxis"]["title"]["text"] == "x"
    assert opts["series"][0]["name"] == "y"
    assert opts["series"][0]["data"] == [1.0, 2.0, 3.0]


@pytest.mark.parametrize("chart_type", CATEGORY_X_TYPES)
def test_category_x_missing_value_becomes_enforced_null(chart_type):
    # The category-x family (cartesian + radar) shares one series build, so a NaN
    # is an EnforcedNull gap (a break in the line/polygon), not a dropped point —
    # unlike pie/scatter/bubble, which drop missing rows entirely.
    df = pd.DataFrame({"x": ["a", "b", "c"], "y": [1.0, float("nan"), 3.0]})
    data = build_options(df, chart_type, "x", ["y"])["series"][0]["data"]
    assert data[0] == 1.0
    assert data[1] is EnforcedNull  # missing point, not Python None
    assert data[2] == 3.0


@pytest.mark.parametrize("chart_type", CATEGORY_X_TYPES)
def test_category_x_numeric_x_becomes_string_categories(chart_type):
    # A numeric x column is coerced to string category *labels* (Highcharts
    # categories are labels, not values) — shared by cartesian and radar, so a
    # numeric CSV x-column plots as discrete categories, not along a value axis.
    # Pins the str() coercion in the category-x branch (a no-op on the string-x
    # data every other categories assertion here feeds).
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    opts = build_options(df, chart_type, "x", ["y"])
    assert opts["xAxis"]["categories"] == ["1", "2", "3"]


@pytest.mark.parametrize(
    ("y_cols", "legend_enabled"),
    [(["y"], False), (["y", "z"], True)],
)
def test_legend_enabled_only_with_multiple_series(y_cols, legend_enabled):
    df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2], "z": [3, 4]})
    opts = build_options(df, "line", "x", y_cols)
    assert opts["legend"]["enabled"] is legend_enabled
    assert len(opts["series"]) == len(y_cols)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_rejects_unsupported_type():
    df = pd.DataFrame({"x": [1], "y": [1]})
    with pytest.raises(ValueError):
        build_options(df, "bogus", "x", ["y"])


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_rejects_empty_y_cols(chart_type):
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    with pytest.raises(ValueError):
        build_options(df, chart_type, "x", [])


@pytest.mark.parametrize("chart_type", CATEGORY_X_TYPES)
def test_category_x_rejects_x_in_y(chart_type):
    # The category-x family (cartesian + radar, i.e. CATEGORY_X_TYPES) treats
    # x_col as the category/angular axis, so it can't double as a y value series.
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    with pytest.raises(ValueError):
        build_options(df, chart_type, "y", ["y"])


def test_scatter_allows_x_in_y():
    # The x-in-y guard is category-x-only (cartesian + radar); scatter happily
    # pairs a column with itself (a diagonal of points).
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0]})
    opts = build_options(df, "scatter", "a", ["a"])
    assert opts["chart"]["type"] == "scatter"
    assert opts["series"][0]["data"] == [[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]]


# --------------------------------------------------------------------------- #
# Pie
# --------------------------------------------------------------------------- #
def test_pie_builds_slices_and_skips_missing():
    df = pd.DataFrame({"name": ["A", "B", "C"], "v": [10.0, float("nan"), 30.0]})
    opts = build_options(df, "pie", "name", ["v"])
    assert opts["chart"]["type"] == "pie"
    assert opts["series"][0]["name"] == "v"
    # The NaN-valued slice (B) is dropped, not rendered as a null point.
    assert opts["series"][0]["data"] == [
        {"name": "A", "y": 10.0},
        {"name": "C", "y": 30.0},
    ]


def test_pie_uses_only_first_y_col():
    df = pd.DataFrame({"name": ["A", "B"], "v": [1.0, 2.0], "v2": [9.0, 9.0]})
    opts = build_options(df, "pie", "name", ["v", "v2"])
    assert opts["series"][0]["name"] == "v"
    assert [pt["y"] for pt in opts["series"][0]["data"]] == [1.0, 2.0]


# --------------------------------------------------------------------------- #
# Scatter
# --------------------------------------------------------------------------- #
def test_scatter_numeric_x_makes_xy_pairs_and_drops_missing():
    df = pd.DataFrame({"h": [1.0, 2.0, 3.0], "w": [10.0, float("nan"), 30.0]})
    opts = build_options(df, "scatter", "h", ["w"])
    assert opts["chart"]["type"] == "scatter"
    # Numeric x: points are [x, y] pairs; the row with a NaN y is dropped.
    assert opts["series"][0]["data"] == [[1.0, 10.0], [3.0, 30.0]]
    # No category axis for a numeric x.
    assert "categories" not in opts["xAxis"]


def test_scatter_non_numeric_x_uses_positions_and_categories():
    df = pd.DataFrame({"label": ["p", "q", "r"], "w": [10.0, float("nan"), 30.0]})
    opts = build_options(df, "scatter", "label", ["w"])
    # Non-numeric x: points use row position as x; the dropped point (q) leaves
    # a gap in positions (0, 2) rather than renumbering the rest.
    assert opts["series"][0]["data"] == [[0, 10.0], [2, 30.0]]
    # Every x value still labels the axis — including q, whose point was dropped.
    assert opts["xAxis"]["categories"] == ["p", "q", "r"]


def test_scatter_multiple_y_cols_make_one_series_each_with_legend():
    # The app reaches scatter with a multiselect, so verify the multi-y shape:
    # one [x, y]-pair series per y column, and the legend on once there's >1.
    df = pd.DataFrame(
        {"h": [1.0, 2.0, 3.0], "w": [10.0, 20.0, 30.0], "z": [100.0, 200.0, 300.0]}
    )
    opts = build_options(df, "scatter", "h", ["w", "z"])
    assert [s["name"] for s in opts["series"]] == ["w", "z"]
    assert opts["series"][0]["data"] == [[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]]
    assert opts["series"][1]["data"] == [[1.0, 100.0], [2.0, 200.0], [3.0, 300.0]]
    assert opts["legend"]["enabled"] is True


# --------------------------------------------------------------------------- #
# Bubble (scatter + a size dimension)
# --------------------------------------------------------------------------- #
def test_bubble_numeric_x_makes_xyz_triples_and_drops_missing():
    df = pd.DataFrame(
        {
            "x": [1.0, 2.0, 3.0],
            "y": [10.0, 20.0, 30.0],
            "size": [5.0, float("nan"), 15.0],
        }
    )
    opts = build_options(df, "bubble", "x", ["y"], size_col="size")
    assert opts["chart"]["type"] == "bubble"
    # Numeric x: points are [x, y, z] triples; the row with a NaN size is dropped.
    assert opts["series"][0]["data"] == [[1.0, 10.0, 5.0], [3.0, 30.0, 15.0]]
    # No category axis for a numeric x (same rule as scatter).
    assert "categories" not in opts["xAxis"]


def test_bubble_non_numeric_x_uses_positions_and_categories():
    df = pd.DataFrame(
        {
            "label": ["p", "q", "r"],
            "y": [10.0, 20.0, 30.0],
            "size": [5.0, float("nan"), 15.0],
        }
    )
    opts = build_options(df, "bubble", "label", ["y"], size_col="size")
    # Non-numeric x: points use row position as x; the NaN-size row (q) is dropped,
    # leaving a gap in positions (0, 2) rather than renumbering the rest.
    assert opts["series"][0]["data"] == [[0, 10.0, 5.0], [2, 30.0, 15.0]]
    # Every x value still labels the axis — including q, whose point was dropped.
    assert opts["xAxis"]["categories"] == ["p", "q", "r"]


def test_bubble_multiple_y_cols_share_the_size_column():
    # Like scatter, each y column is its own series; every series carries the one
    # size column as its z, and the legend turns on once there's more than one.
    df = pd.DataFrame(
        {"x": [1.0, 2.0], "a": [10.0, 20.0], "b": [100.0, 200.0], "size": [3.0, 4.0]}
    )
    opts = build_options(df, "bubble", "x", ["a", "b"], size_col="size")
    assert [s["name"] for s in opts["series"]] == ["a", "b"]
    assert opts["series"][0]["data"] == [[1.0, 10.0, 3.0], [2.0, 20.0, 4.0]]
    assert opts["series"][1]["data"] == [[1.0, 100.0, 3.0], [2.0, 200.0, 4.0]]
    assert opts["legend"]["enabled"] is True


def test_bubble_requires_a_size_column():
    # Bubble minus its size dimension is just a scatter, so the size column is
    # mandatory — omitting it is a ValueError, not a silent 2-D fallback.
    df = pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})
    with pytest.raises(ValueError):
        build_options(df, "bubble", "x", ["y"])  # no size_col


def test_bubble_serializes_and_pulls_in_the_more_module():
    # End to end: the [x, y, z] shape must serialize AND resolve highcharts-more,
    # the module bubble lives in — a plain scatter/core template renders blank
    # because the browser never loads that module.
    from highcharts_builder import make_chart

    df = pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0], "size": [5.0, 6.0]})
    chart = make_chart(df, "bubble", "x", ["y"], size_col="size")
    js = chart.to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and "type: 'bubble'" in js
    assert "highcharts-more" in chart.get_script_tags(as_str=True)


def test_bubble_tooltip_names_the_size_column_and_survives_dark_merge():
    # The bubble tooltip names all three dimensions (the default shows a bare
    # x/y/z); the size column in particular is labelled by name.
    df = pd.DataFrame({"gdp": [1.0, 2.0], "life": [3.0, 4.0], "population": [5.0, 6.0]})
    light = build_options(df, "bubble", "gdp", ["life"], size_col="population")
    fmt = light["tooltip"]["pointFormat"]
    assert "population" in fmt and "{point.z}" in fmt  # size named + wired
    assert "gdp" in fmt and "{point.x}" in fmt  # numeric x -> point.x
    # Dark mode merges chrome onto the tooltip without dropping the pointFormat
    # (the same merge the pie path relies on).
    dark = build_options(
        df, "bubble", "gdp", ["life"], size_col="population", dark=True
    )
    assert dark["tooltip"]["backgroundColor"] == "#0f172a"
    assert "population" in dark["tooltip"]["pointFormat"]


def test_bubble_tooltip_uses_category_for_non_numeric_x():
    # With a non-numeric x the point's x is a row index, so the tooltip references
    # the category label instead of the bare position.
    df = pd.DataFrame({"country": ["A", "B"], "life": [3.0, 4.0], "pop": [5.0, 6.0]})
    opts = build_options(df, "bubble", "country", ["life"], size_col="pop")
    fmt = opts["tooltip"]["pointFormat"]
    assert "{point.category}" in fmt and "{point.x}" not in fmt


def test_bubble_tooltip_sanitizes_user_column_names():
    # Column names are user/CSV-controlled and land in a Highcharts format string:
    # braces would be parsed as (empty) value tokens and HTML would inject, so the
    # interpolated x/size names are brace-stripped and HTML-escaped.
    df = pd.DataFrame({"w {kg}": [1.0], "y": [2.0], "<b>pop</b>": [3.0]})
    fmt = build_options(df, "bubble", "w {kg}", ["y"], size_col="<b>pop</b>")[
        "tooltip"
    ]["pointFormat"]
    # Braces stripped from the label, so Highcharts won't tokenize `{kg}` away.
    assert "{kg}" not in fmt
    assert "w kg: " in fmt
    # HTML in the size column name is escaped, not emitted as live markup.
    assert "<b>pop</b>" not in fmt
    assert "&lt;b&gt;pop&lt;/b&gt;" in fmt
    # The genuine Highcharts tokens are untouched.
    assert "{point.z}" in fmt


# --------------------------------------------------------------------------- #
# Radar (a polar line chart over the categories)
# --------------------------------------------------------------------------- #
def test_radar_builds_polar_line_over_categories():
    # Radar shares the cartesian category-x shape but renders on polar axes: the
    # chart.type is "line" (Highcharts has no radar type) with chart.polar set,
    # the x values become the angular categories, and each y column is a series.
    df = pd.DataFrame({"attr": ["a", "b", "c"], "p": [1, 2, 3], "q": [3, 2, 1]})
    opts = build_options(df, "radar", "attr", ["p", "q"])
    assert opts["chart"]["type"] == "line"
    assert opts["chart"]["polar"] is True
    assert opts["xAxis"]["categories"] == ["a", "b", "c"]
    assert [s["name"] for s in opts["series"]] == ["p", "q"]
    assert opts["series"][0]["data"] == [1.0, 2.0, 3.0]
    # Two series -> legend on; the value axis is left to auto-scale (no forced
    # min), like the cartesian one, and draws polygon gridlines for the web look.
    assert opts["legend"]["enabled"] is True
    assert "min" not in opts["yAxis"]
    assert opts["yAxis"]["gridLineInterpolation"] == "polygon"


def test_radar_dark_mode_themes_the_polar_axes():
    # The polygon rings (yAxis gridlines) and the category labels must recolor in
    # dark mode, or the web is invisible against the dark background.
    df = pd.DataFrame({"attr": ["a", "b"], "p": [1, 2]})
    opts = build_options(df, "radar", "attr", ["p"], dark=True)
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    assert opts["yAxis"]["gridLineColor"] == "#334155"
    assert opts["xAxis"]["labels"]["style"]["color"] == "#94a3b8"


def test_radar_serializes_and_pulls_in_the_more_module():
    # End to end: the polar chart must serialize AND resolve highcharts-more, the
    # module chart.polar lives in (like bubble) — without it the browser draws a
    # plain, non-polar line instead of the radar.
    from highcharts_builder import make_chart

    df = pd.DataFrame({"attr": ["a", "b", "c"], "p": [1.0, 2.0, 3.0]})
    chart = make_chart(df, "radar", "attr", ["p"])
    js = chart.to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and "type: 'line'" in js and "polar: true" in js
    assert "highcharts-more" in chart.get_script_tags(as_str=True)


# --------------------------------------------------------------------------- #
# Heatmap (an x-category × y-category value matrix, colored by a colorAxis)
# --------------------------------------------------------------------------- #
def test_heatmap_builds_matrix_over_category_axes():
    # Wide-form: x_col's values are the X categories, each y column *name* is a Y
    # category, and every cell is [x_index, y_index, value] — the category-x shape
    # reinterpreted as a grid. Cells are colored by a sequential colorAxis, not the
    # categorical DEFAULT_COLORS palette (still carried, unused, for consistency).
    df = pd.DataFrame({"day": ["Mon", "Tue"], "AM": [1.0, 2.0], "PM": [3.0, 4.0]})
    opts = build_options(df, "heatmap", "day", ["AM", "PM"])
    assert opts["chart"]["type"] == "heatmap"
    assert opts["xAxis"]["categories"] == ["Mon", "Tue"]
    assert opts["yAxis"]["categories"] == ["AM", "PM"]
    # One [x_index, y_index, value] cell per (row, column): 2 rows × 2 columns = 4.
    assert opts["series"][0]["data"] == [
        [0, 0, 1.0],
        [1, 0, 2.0],
        [0, 1, 3.0],
        [1, 1, 4.0],
    ]
    assert opts["colorAxis"]["maxColor"] == DEFAULT_COLORS[0]
    assert opts["colors"] == list(DEFAULT_COLORS)
    assert opts["legend"]["enabled"] is True
    # The Y categories are self-labelling, so Highcharts' default "Values" y-axis
    # title is suppressed with an empty string (None would be dropped and leak the
    # default back in).
    assert opts["yAxis"]["title"]["text"] == ""
    # The color scale sits vertically to the right (the heatmap convention).
    assert opts["legend"]["layout"] == "vertical"
    # The tooltip names both category axes so a hovered cell says which (row,
    # column) it is — not just the bare value.
    fmt = opts["tooltip"]["pointFormat"]
    assert "xAxis.categories" in fmt and "yAxis.categories" in fmt
    assert "{point.value}" in fmt
    # A small grid (4 cells) prints each cell's value inside it.
    assert opts["plotOptions"]["heatmap"]["dataLabels"]["enabled"] is True


def test_heatmap_missing_cell_becomes_enforced_null_and_keeps_the_grid():
    # Unlike pie/scatter/bubble (which drop missing rows), a heatmap KEEPS the slot
    # for a missing cell — as EnforcedNull (an empty nullColor cell) — so the grid
    # stays aligned rather than shifting the remaining cells.
    df = pd.DataFrame({"day": ["Mon", "Tue"], "AM": [1.0, float("nan")]})
    data = build_options(df, "heatmap", "day", ["AM"])["series"][0]["data"]
    assert len(data) == 2  # both slots kept, none dropped
    assert data[0] == [0, 0, 1.0]
    assert data[1][:2] == [1, 0]
    assert data[1][2] is EnforcedNull  # missing cell, not Python None or dropped


def test_heatmap_rejects_x_in_y():
    # The X column is a category axis (its values label the columns), so it can't
    # also be one of the Y value columns — the category-x rule, widened to heatmap.
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    with pytest.raises(ValueError):
        build_options(df, "heatmap", "a", ["a"])


def test_heatmap_dark_mode_themes_the_color_axis():
    # The colorAxis gradient legend + its labels aren't reached by the generic
    # xAxis/yAxis theming loop, so dark mode must flip them explicitly (a dark ramp
    # + muted labels) and recolor the empty-cell nullColor — or the color legend
    # renders light-on-dark.
    df = pd.DataFrame({"day": ["Mon", "Tue"], "AM": [1.0, 2.0]})
    opts = build_options(df, "heatmap", "day", ["AM"], dark=True)
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    assert opts["colorAxis"]["minColor"] == "#1e293b"
    assert opts["colorAxis"]["maxColor"] == "#60a5fa"
    assert opts["colorAxis"]["labels"]["style"]["color"] == "#94a3b8"
    # The gradient legend's tick lines (full-width gridlines + the shorter edge ticks)
    # default to white and cross the bar as bright dashes; both are muted to the axis
    # colors, or the gridlines stay white while only the ticks flip.
    assert opts["colorAxis"]["gridLineColor"] == "#334155"
    assert opts["colorAxis"]["tickColor"] == "#475569"
    assert opts["plotOptions"]["heatmap"]["nullColor"] == "#334155"
    # The category axes still recolor via the shared loop.
    assert opts["xAxis"]["labels"]["style"]["color"] == "#94a3b8"


def test_heatmap_serializes_and_pulls_in_the_heatmap_module():
    # End to end: the [x, y, value] + colorAxis shape must serialize AND resolve
    # the heatmap module (modules/heatmap.js) — a DIFFERENT module from bubble/
    # radar's highcharts-more; without it the browser renders the chart blank.
    from highcharts_builder import make_chart

    df = pd.DataFrame({"day": ["Mon", "Tue"], "AM": [1.0, 2.0], "PM": [3.0, 4.0]})
    chart = make_chart(df, "heatmap", "day", ["AM", "PM"])
    js = chart.to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and "type: 'heatmap'" in js and "colorAxis" in js
    tags = chart.get_script_tags(as_str=True)
    assert "modules/heatmap.js" in tags
    assert "highcharts-more" not in tags  # heatmap's own module, not bubble/radar's


def test_heatmap_numeric_x_becomes_string_categories():
    # Heatmap has its OWN str() coercion (via _category_labels), separate from the
    # cartesian/radar branch and deliberately excluded from the CATEGORY_X_TYPES
    # parametrization — so a numeric x column must still become string category
    # labels here, or highcharts-core raises CannotCoerceError on render for any
    # user who picks a numeric X.
    df = pd.DataFrame({"week": [1, 2, 3], "AM": [4.0, 5.0, 6.0]})
    opts = build_options(df, "heatmap", "week", ["AM"])
    assert opts["xAxis"]["categories"] == ["1", "2", "3"]


def test_heatmap_light_mode_shape():
    # The dark test pins the dark counterparts; pin the light-mode chrome + tooltip
    # here so the pair reads symmetrically. reversed=True is load-bearing (flips the
    # Y-row order, changing how the whole grid reads); the category-naming tooltip
    # and the light nullColor/minColor are deliberate and otherwise unguarded.
    df = pd.DataFrame({"day": ["Mon", "Tue"], "AM": [1.0, 2.0]})
    opts = build_options(df, "heatmap", "day", ["AM"])
    assert opts["colorAxis"]["minColor"] == "#e0ecff"
    assert opts["plotOptions"]["heatmap"]["nullColor"] == "#f1f5f9"
    assert opts["yAxis"]["reversed"] is True
    assert opts["series"][0]["name"] == "value"
    assert opts["tooltip"]["headerFormat"] == ""
    assert "{point.value}" in opts["tooltip"]["pointFormat"]


def test_heatmap_large_grid_omits_data_labels():
    # Per-cell value labels help on a small grid but overprint into noise on a big
    # one, so they're gated on the cell count: past the threshold, none are drawn.
    from highcharts_builder import _HEATMAP_DATALABEL_MAX_CELLS

    rows = _HEATMAP_DATALABEL_MAX_CELLS + 1  # one column, so cells == rows
    df = pd.DataFrame({"x": [str(i) for i in range(rows)], "v": list(range(rows))})
    opts = build_options(df, "heatmap", "x", ["v"])
    assert len(opts["series"][0]["data"]) == rows
    assert "dataLabels" not in opts["plotOptions"]["heatmap"]


def test_heatmap_all_nan_column_serializes_null_cells():
    # A fully-missing Y column must keep ALL its cells (as EnforcedNull) — the grid
    # can't collapse — and those nulls must survive to_js_literal (Python None would
    # be silently dropped; the other serialize test uses all-valid data, so nothing
    # else proves an EnforcedNull cell reaches the JS).
    from highcharts_builder import make_chart

    df = pd.DataFrame(
        {"day": ["Mon", "Tue"], "AM": [1.0, 2.0], "PM": [float("nan"), float("nan")]}
    )
    opts = build_options(df, "heatmap", "day", ["AM", "PM"])
    assert len(opts["series"][0]["data"]) == 2 * 2  # full grid, nothing dropped
    pm_cells = [cell for cell in opts["series"][0]["data"] if cell[1] == 1]  # PM col
    assert pm_cells and all(cell[2] is EnforcedNull for cell in pm_cells)
    js = make_chart(df, "heatmap", "day", ["AM", "PM"]).to_js_literal()
    # A null closing a cell array — distinct from the unconditional nullColor key
    # (whose substring makes a bare "null" check vacuous) — so this proves the
    # EnforcedNull cell actually reached the data array.
    assert js and "null]" in js


# --------------------------------------------------------------------------- #
# Treemap (nested rectangles sized by value, colored categorically like pie)
# --------------------------------------------------------------------------- #
def test_treemap_builds_leaves_and_skips_missing():
    # Treemap shares pie's single-value shape (a label column + one value column)
    # but is its own branch: leaves are keyed "value" (NOT pie's "y" — highcharts-
    # core's treemap point model reads "value" and ignores a stray "y"), colored
    # categorically via colorByPoint, and laid out by the squarified algorithm.
    # Like pie, a NaN-valued row is dropped (a tile can't be sized without a value).
    df = pd.DataFrame({"name": ["A", "B", "C"], "v": [10.0, float("nan"), 30.0]})
    opts = build_options(df, "treemap", "name", ["v"])
    assert opts["chart"]["type"] == "treemap"
    assert opts["series"][0]["name"] == "v"
    # The NaN-valued tile (B) is dropped; leaves use "value", not "y".
    assert opts["series"][0]["data"] == [
        {"name": "A", "value": 10.0},
        {"name": "C", "value": 30.0},
    ]
    tm = opts["plotOptions"]["treemap"]
    assert tm["colorByPoint"] is True
    assert tm["layoutAlgorithm"] == "squarified"
    # Colored categorically from the shared palette (like pie), NOT a colorAxis —
    # so this is not a value-colored type (unlike heatmap).
    assert opts["colors"] == list(DEFAULT_COLORS)
    assert "colorAxis" not in opts


def test_treemap_uses_only_first_y_col():
    # Single-value like pie: only the first selected column sizes the tiles.
    df = pd.DataFrame({"name": ["A", "B"], "v": [1.0, 2.0], "v2": [9.0, 9.0]})
    opts = build_options(df, "treemap", "name", ["v", "v2"])
    assert opts["series"][0]["name"] == "v"
    assert [pt["value"] for pt in opts["series"][0]["data"]] == [1.0, 2.0]


def test_treemap_dark_mode_themes_tiles_and_skips_axes():
    # Dark mode paints the background and matches the tile gaps (borderColor) to it
    # so they don't read as white grid-lines — as pie does for its slice gaps. The
    # data-label color stays "contrast" (NOT flipped to light like pie's): treemap
    # labels sit on the palette-colored tile, not the chart background, so the same
    # value stays legible in both themes.
    df = pd.DataFrame({"name": ["A", "B"], "v": [1.0, 2.0]})
    opts = build_options(df, "treemap", "name", ["v"], dark=True)
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    assert opts["plotOptions"]["treemap"]["borderColor"] == "#0f172a"
    assert opts["plotOptions"]["treemap"]["dataLabels"]["color"] == "contrast"
    # Treemap has no axes, so the axis-theming loop must simply skip it (not crash).
    assert "xAxis" not in opts


def test_treemap_serializes_and_pulls_in_the_treemap_module():
    # End to end: the {name, value} leaf shape must serialize AND resolve
    # modules/treemap.js — treemap's own module, distinct from bubble/radar's
    # highcharts-more; without it the browser renders the chart blank.
    from highcharts_builder import make_chart

    df = pd.DataFrame({"name": ["A", "B", "C"], "v": [1.0, 2.0, 3.0]})
    chart = make_chart(df, "treemap", "name", ["v"])
    js = chart.to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and "type: 'treemap'" in js
    tags = chart.get_script_tags(as_str=True)
    assert "modules/treemap.js" in tags
    assert "highcharts-more" not in tags  # treemap's own module, not bubble/radar's


def test_treemap_light_mode_shape():
    # The dark test pins the dark counterparts; pin the light-mode chrome here so
    # the pair reads symmetrically (mirrors test_heatmap_light_mode_shape). These
    # treemap-specific choices are otherwise unguarded: the {name, value} tooltip
    # (headerFormat blanked so a hovered tile isn't a bare value), the disabled
    # legend (the in-tile labels carry identity, so a legend would just repeat
    # them), and the two-line name+value "contrast" tile labels (printed in the
    # mark so the Static-PNG mode, which has no hover, still shows the numbers —
    # like pie and heatmap).
    df = pd.DataFrame({"name": ["A", "B"], "v": [1.0, 2.0]})
    opts = build_options(df, "treemap", "name", ["v"])
    assert opts["legend"]["enabled"] is False
    assert opts["tooltip"]["headerFormat"] == ""
    assert opts["tooltip"]["pointFormat"] == "{point.name}: <b>{point.value}</b>"
    labels = opts["plotOptions"]["treemap"]["dataLabels"]
    assert labels["enabled"] is True
    assert labels["format"] == "{point.name}<br>{point.value}"
    assert labels["color"] == "contrast"
    # Light mode injects no dark chrome onto the tooltip (a no-op, as elsewhere).
    assert "backgroundColor" not in opts["tooltip"]


@pytest.mark.parametrize("chart_type", ["pie", "treemap"])
def test_single_value_numeric_labels_coerce_to_strings(chart_type):
    # The single-value point-name types (pie, treemap) build leaves as
    # {"name": str(label), ...}. That str() is load-bearing: highcharts-core's
    # point model rejects a non-string name (CannotCoerceError on render), so a
    # user who picks a numeric label column (years, IDs) would otherwise get a
    # blank/erroring chart. This is the point-name analog of the category-axis
    # coercion tests (test_category_x_numeric_x_becomes_string_categories,
    # test_heatmap_numeric_x_becomes_string_categories); the shared labeled_frame
    # sweeps only use string labels, so nothing else pins it for these two.
    df = pd.DataFrame({"yr": [2001, 2002], "v": [1.0, 2.0]})
    data = build_options(df, chart_type, "yr", ["v"])["series"][0]["data"]
    assert [pt["name"] for pt in data] == ["2001", "2002"]  # strings, not ints


# --------------------------------------------------------------------------- #
# Sankey (node-link flows: source -> target links sized by weight)
# --------------------------------------------------------------------------- #
def _links(opts) -> list[dict]:
    """The sankey links with their per-link ``dataLabels`` stripped, so the shape
    tests read as the plain edge list. Those labels are pinned separately by
    test_sankey_labels_its_nodes_and_links, and their absence on a large diagram by
    test_sankey_many_links_omit_the_weight_labels."""
    return [
        {key: value for key, value in link.items() if key != "dataLabels"}
        for link in opts["series"][0]["data"]
    ]


def test_sankey_builds_links_and_skips_missing():
    # Sankey is the one type whose data is a *graph*, not a table: every row is a
    # link, keyed {from, to, weight}. Not the [x, y, value] arrays heatmap builds
    # (highcharts-core rejects the equivalent array-form sankey series outright),
    # and not pie's "y". A row with a missing weight can't size a link — and
    # serializes silently, as an invisible zero-width one — so it's dropped, as a
    # valueless pie slice is. No EnforcedNull: unlike the heatmap grid, there's no
    # cell here to keep aligned.
    df = pd.DataFrame(
        {
            "src": ["Coal", "Gas", "Wind"],
            "dst": ["Power", "Power", "Power"],
            "w": [42.0, float("nan"), 26.0],
        }
    )
    opts = build_options(df, "sankey", "src", ["w"], target_col="dst")
    assert opts["chart"]["type"] == "sankey"
    assert opts["series"][0]["name"] == "w"
    # The NaN-weighted link (Gas) is dropped; links use from/to/weight.
    assert _links(opts) == [
        {"from": "Coal", "to": "Power", "weight": 42.0},
        {"from": "Wind", "to": "Power", "weight": 26.0},
    ]
    # Nodes are colored categorically from the shared palette (like pie/treemap),
    # NOT by a colorAxis — so this is not a value-colored type (unlike heatmap).
    assert opts["colors"] == list(DEFAULT_COLORS)
    assert "colorAxis" not in opts
    # A flow diagram has no axes at all.
    assert "xAxis" not in opts and "yAxis" not in opts


def test_sankey_drops_rows_missing_either_node():
    # Not only a missing weight: a link with no source, or no target, isn't an edge
    # either — all three columns are required per row.
    df = pd.DataFrame(
        {"src": ["A", None, "C"], "dst": ["X", "Y", None], "w": [1.0, 2.0, 3.0]}
    )
    opts = build_options(df, "sankey", "src", ["w"], target_col="dst")
    assert _links(opts) == [{"from": "A", "to": "X", "weight": 1.0}]


def test_sankey_uses_only_first_y_col():
    # Single-value like pie/treemap: only the first selected column weights the
    # links (the app gives sankey a single-select Y for exactly this reason).
    df = pd.DataFrame({"src": ["A"], "dst": ["B"], "w": [1.0], "w2": [9.0]})
    opts = build_options(df, "sankey", "src", ["w", "w2"], target_col="dst")
    assert opts["series"][0]["name"] == "w"
    assert [link["weight"] for link in opts["series"][0]["data"]] == [1.0]


def test_sankey_requires_a_target_column():
    # A sankey without its target column has only one end per link, so the target is
    # mandatory — a ValueError, not a silent fallback (as bubble's size_col is).
    df = pd.DataFrame({"src": ["A"], "dst": ["B"], "w": [1.0]})
    with pytest.raises(ValueError):
        build_options(df, "sankey", "src", ["w"])  # no target_col


def test_sankey_rejects_source_as_target():
    # One column can't name both ends of a link: every row would be a self-loop.
    # This is sankey's OWN guard, not the category-x x-in-y rule — target_col is
    # never among y_cols, so X_IN_Y_GUARD_TYPES structurally can't express it, which
    # is why sankey is absent from that constant.
    df = pd.DataFrame({"src": ["A"], "w": [1.0]})
    with pytest.raises(ValueError):
        build_options(df, "sankey", "src", ["w"], target_col="src")


def test_sankey_allows_the_weight_to_repeat_a_node_column():
    # The guard is source-vs-target ONLY. Weighting a link by the same column that
    # names one of its nodes is odd but well-defined, so it builds — the same
    # deliberate restraint as test_scatter_allows_x_in_y. Also pins that a numeric
    # node column is stringified into a node name.
    df = pd.DataFrame({"src": ["A", "B"], "w": [1.0, 2.0]})
    opts = build_options(df, "sankey", "src", ["w"], target_col="w")
    assert _links(opts) == [
        {"from": "A", "to": "1.0", "weight": 1.0},
        {"from": "B", "to": "2.0", "weight": 2.0},
    ]


def test_sankey_node_tooltip_lives_in_plot_options_not_the_tooltip():
    # The node-hover format MUST sit under plotOptions.sankey.tooltip: highcharts-
    # core's Tooltip model has no nodeFormat, so a top-level one is accepted by
    # Chart.from_options and then SILENTLY DROPPED from the emitted JS — the same
    # class of trap as treemap's "value" vs "y" leaf key. Only the serialized JS
    # proves it arrived, so assert on that too, not just the options dict.
    from highcharts_builder import make_chart

    df = pd.DataFrame({"src": ["A"], "dst": ["B"], "w": [1.0]})
    opts = build_options(df, "sankey", "src", ["w"], target_col="dst")
    assert "nodeFormat" not in opts["tooltip"]  # would vanish if it were here
    assert (
        opts["plotOptions"]["sankey"]["tooltip"]["nodeFormat"]
        == "{point.name}: <b>{point.sum}</b>"
    )
    js = make_chart(df, "sankey", "src", ["w"], target_col="dst").to_js_literal()
    assert js and "nodeFormat" in js and "point.sum" in js


def test_sankey_serializes_and_pulls_in_the_sankey_module():
    # End to end: the {from, to, weight} link shape must serialize AND resolve
    # modules/sankey.js — sankey's own module, distinct from bubble/radar's
    # highcharts-more; without it the browser renders the chart blank. The link keys
    # in particular must reach the JS: highcharts-core builds a typed point model
    # and silently discards any key it doesn't recognize.
    from highcharts_builder import make_chart

    df = pd.DataFrame({"src": ["A", "B"], "dst": ["C", "C"], "w": [1.0, 2.0]})
    chart = make_chart(df, "sankey", "src", ["w"], target_col="dst")
    js = chart.to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and "type: 'sankey'" in js
    assert "from: 'A'" in js and "to: 'C'" in js and "weight: 1.0" in js
    # The per-link weight label must reach the JS too — a series-level dataLabels
    # format is the one thing that WOULD survive serialization while rendering the
    # wrong chart (it labels the links with the node format and blanks the names),
    # so the options-dict assertions alone can't prove this arrived intact.
    assert "format: '{point.weight}'" in js
    tags = chart.get_script_tags(as_str=True)
    assert "modules/sankey.js" in tags
    assert "highcharts-more" not in tags  # sankey's own module, not bubble/radar's


def test_sankey_labels_its_nodes_and_links():
    # Nodes are named and links carry their weight — the value printed IN the mark,
    # as pie/heatmap/treemap print theirs, so the Static-PNG mode (no hover) still
    # shows the numbers. Getting BOTH takes two separate places, and the reason is a
    # silent drop: highcharts-core discards plotOptions.sankey.dataLabels.nodeFormat,
    # and the `format` that does survive there applies to nodes AND links, so setting
    # it series-wide would label every link with the node format and blank the node
    # names. Hence: an empty series-level dataLabels (Highcharts' own default
    # nodeFormat names the nodes) plus a per-link label carrying the weight. No color
    # is set anywhere — Highcharts' `contrast` default handles both themes.
    df = pd.DataFrame({"src": ["A", "B"], "dst": ["C", "C"], "w": [1.0, 2.0]})
    opts = build_options(df, "sankey", "src", ["w"], target_col="dst")
    series_labels = opts["plotOptions"]["sankey"]["dataLabels"]
    assert series_labels == {"enabled": True}  # no `format`: it would blank the names
    for link in opts["series"][0]["data"]:
        assert link["dataLabels"] == {"enabled": True, "format": "{point.weight}"}
    # Each link's label dict is its own object, so nothing can mutate the module
    # constant through one of them (the _HEATMAP_GRADIENT copy rule).
    first, second = (link["dataLabels"] for link in opts["series"][0]["data"])
    assert first is not second


def test_sankey_many_links_omit_the_weight_labels():
    # Per-link weight labels help on a small diagram but overprint into noise on a
    # big one, so they're gated on the link count: past the threshold, none are
    # attached. The sankey counterpart of test_heatmap_large_grid_omits_data_labels.
    from highcharts_builder import _SANKEY_DATALABEL_MAX_LINKS

    rows = _SANKEY_DATALABEL_MAX_LINKS + 1
    df = pd.DataFrame(
        {
            "src": [f"s{i}" for i in range(rows)],
            "dst": ["hub"] * rows,
            "w": [float(i + 1) for i in range(rows)],
        }
    )
    links = build_options(df, "sankey", "src", ["w"], target_col="dst")["series"][0][
        "data"
    ]
    assert len(links) == rows
    assert all("dataLabels" not in link for link in links)
    # The node names still render — those come from the series-level dataLabels.
    assert build_options(df, "sankey", "src", ["w"], target_col="dst")["plotOptions"][
        "sankey"
    ]["dataLabels"] == {"enabled": True}


def test_sankey_light_mode_shape():
    # Mirrors test_treemap_light_mode_shape: pin the light-mode choices that nothing
    # else guards — the link tooltip naming both ends (headerFormat blanked so a
    # hovered link isn't a bare number) and the disabled legend (each node is
    # labelled on the chart, so a legend would only repeat them).
    df = pd.DataFrame({"src": ["A"], "dst": ["B"], "w": [1.0]})
    opts = build_options(df, "sankey", "src", ["w"], target_col="dst")
    assert opts["legend"]["enabled"] is False
    assert opts["tooltip"]["headerFormat"] == ""
    assert opts["tooltip"]["pointFormat"] == "src → dst: <b>{point.weight}</b>"
    # Light mode injects no dark chrome anywhere (a no-op, as elsewhere).
    assert "backgroundColor" not in opts["tooltip"]
    assert "borderColor" not in opts["plotOptions"]["sankey"]


def test_sankey_dark_mode_themes_borders_and_skips_axes():
    # Only the borders flip: they default to light and would read as white outlines
    # against the dark background, exactly as pie's slice gaps do. The node and link
    # LABELS are deliberately left alone — Highcharts draws them in its `contrast`
    # color, computed against whatever each sits on, so they stay legible in both
    # themes without a flip (the treemap reasoning, not pie's).
    df = pd.DataFrame({"src": ["A"], "dst": ["B"], "w": [1.0]})
    opts = build_options(df, "sankey", "src", ["w"], target_col="dst", dark=True)
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    assert opts["plotOptions"]["sankey"]["borderColor"] == "#0f172a"
    assert "color" not in opts["plotOptions"]["sankey"]["dataLabels"]
    assert all("color" not in link["dataLabels"] for link in opts["series"][0]["data"])
    # The dark tooltip merge keeps the link pointFormat (as the pie path relies on).
    assert opts["tooltip"]["backgroundColor"] == "#0f172a"
    assert "{point.weight}" in opts["tooltip"]["pointFormat"]
    # Sankey has no axes, so the axis-theming loop must simply skip it (not crash).
    assert "xAxis" not in opts


def test_sankey_tooltip_sanitizes_user_column_names():
    # Both node column names land in a Highcharts format string as literal text, so
    # — like bubble's x/size names — they're brace-stripped (Highcharts would parse
    # `{...}` as a value token) and HTML-escaped (tooltips render as HTML).
    df = pd.DataFrame({"from {a}": ["A"], "<b>to</b>": ["B"], "w": [1.0]})
    fmt = build_options(df, "sankey", "from {a}", ["w"], target_col="<b>to</b>")[
        "tooltip"
    ]["pointFormat"]
    # Braces stripped, so Highcharts won't tokenize `{a}` away.
    assert "{a}" not in fmt
    assert "from a" in fmt
    # HTML in the target column name is escaped, not emitted as live markup.
    assert "<b>to</b>" not in fmt
    assert "&lt;b&gt;to&lt;/b&gt;" in fmt
    # The genuine Highcharts token is untouched.
    assert "{point.weight}" in fmt


def test_sankey_numeric_node_labels_coerce_to_strings():
    # Both node columns are stringified: highcharts-core's point model rejects a
    # non-string node name, so a user picking numeric ids would otherwise get a
    # blank/erroring chart. The pie/treemap coercion test
    # (test_single_value_numeric_labels_coerce_to_strings) for the one type with
    # *two* label columns — the shared labeled_frame sweeps use string nodes only.
    df = pd.DataFrame({"src": [1, 2], "dst": [10, 20], "w": [1.0, 2.0]})
    opts = build_options(df, "sankey", "src", ["w"], target_col="dst")
    assert _links(opts) == [
        {"from": "1", "to": "10", "weight": 1.0},
        {"from": "2", "to": "20", "weight": 2.0},
    ]


# --------------------------------------------------------------------------- #
# Boxplot (per-category Tukey distributions, aggregated from raw observations)
# --------------------------------------------------------------------------- #
def _boxes(opts) -> list:
    """The box series' data: one positional ``[low, q1, median, q3, high]`` 5-array (or
    ``EnforcedNull``) per category."""
    return opts["series"][0]["data"]


def test_boxplot_builds_boxes_over_categories():
    # Boxplot is the one type whose builder AGGREGATES: the frame is long/tidy (x_col
    # REPEATS, one row per observation) and each distinct x_col value becomes ONE box
    # over that group's raw y_cols[0] numbers. Points are positional 5-arrays matched to
    # xAxis.categories BY POSITION — not the {name, low, ...} dict form, which
    # highcharts-core collapses with the name in the leading x slot.
    df = pd.DataFrame(
        {"svc": ["a", "a", "a", "b", "b", "b"], "ms": [1.0, 2.0, 3.0, 5.0, 6.0, 7.0]}
    )
    opts = build_options(df, "boxplot", "svc", ["ms"])
    assert opts["chart"]["type"] == "boxplot"
    assert opts["xAxis"]["categories"] == ["a", "b"]
    assert opts["xAxis"]["title"]["text"] == "svc"
    assert opts["yAxis"]["title"]["text"] == "ms"
    assert opts["series"][0]["name"] == "ms"
    # [low, q1, median, q3, high] — pandas' default linear quantiles.
    assert _boxes(opts) == [
        [1.0, 1.5, 2.0, 2.5, 3.0],
        [5.0, 5.5, 6.0, 6.5, 7.0],
    ]
    # Boxes are colored categorically from the shared palette (like pie/treemap/sankey),
    # NOT by a colorAxis — so this is not a value-colored type (unlike heatmap).
    assert opts["plotOptions"]["boxplot"]["colorByPoint"] is True
    assert opts["colors"] == list(DEFAULT_COLORS)
    assert "colorAxis" not in opts


def test_boxplot_tukey_outliers_become_a_linked_scatter_series():
    # Observations strictly beyond the 1.5 x IQR fences are drawn individually, as a
    # SECOND series linked to the boxes. The whiskers stop at the most extreme point
    # still inside the fence (13.0), never at the fence value itself.
    df = pd.DataFrame({"g": ["a"] * 5, "v": [10.0, 11.0, 12.0, 13.0, 100.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    assert _boxes(opts) == [
        [10.0, 11.0, 12.0, 13.0, 13.0]
    ]  # high is the whisker, not 100
    outliers = opts["series"][1]
    assert outliers["type"] == "scatter"
    assert outliers["linkedTo"] == ":previous"
    assert outliers["data"] == [[0, 100.0]]  # [category_index, value]
    # A fixed brand hue, read from DEFAULT_COLORS rather than the overridable `colors`
    # list (a short custom palette would IndexError), and never dark-flipped.
    assert outliers["marker"]["fillColor"] == DEFAULT_COLORS[3]


def test_boxplot_without_outliers_emits_a_single_series():
    # The linked scatter is emitted ONLY when there are outliers — an empty one would be
    # dead config (the restraint heatmap/sankey show in gating their labels on count).
    df = pd.DataFrame({"g": ["a"] * 4, "v": [10.0, 11.0, 12.0, 13.0]})
    assert len(build_options(df, "boxplot", "g", ["v"])["series"]) == 1


def test_boxplot_single_observation_group_is_a_flat_box():
    # n == 1: every quantile is that value, so iqr == 0 and the box is a flat line. This
    # is not a corner case to tolerate but the one the SUPPORTED_TYPES sweeps hit —
    # `labeled_frame` gives boxplot three groups of exactly one observation.
    df = pd.DataFrame({"g": ["a", "b"], "v": [7.0, 9.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    assert _boxes(opts) == [[7.0] * 5, [9.0] * 5]
    assert len(opts["series"]) == 1  # a flat box is not an outlier


def test_boxplot_two_observation_group_has_no_false_outliers():
    df = pd.DataFrame({"g": ["a", "a"], "v": [3.0, 9.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    assert _boxes(opts) == [[3.0, 4.5, 6.0, 7.5, 9.0]]
    assert len(opts["series"]) == 1


def test_boxplot_identical_observations_have_zero_iqr_and_no_outliers():
    # THE degenerate case. All values equal -> q1 == q3 -> iqr == 0 -> both fences
    # collapse onto that value. Because fence membership is INCLUSIVE (>=/<=), every
    # observation sits ON the fence and none is flagged. A strict (>/<) test would
    # classify the entire group as outliers — and would fail the sweeps above, which
    # feed boxplot single-observation groups.
    df = pd.DataFrame({"g": ["a"] * 4, "v": [5.0, 5.0, 5.0, 5.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    assert _boxes(opts) == [[5.0] * 5]
    assert len(opts["series"]) == 1


def test_boxplot_zero_iqr_with_genuine_tails_still_flags_them():
    # The other half of the iqr == 0 story: over half the mass on one value collapses the
    # fences, but the real tails ARE strictly beyond them, so they are correctly flagged.
    # The inclusive fence spares the 5s; it does not spare the 1 and the 9.
    df = pd.DataFrame({"g": ["a"] * 10, "v": [1.0] + [5.0] * 8 + [9.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    assert _boxes(opts) == [[5.0] * 5]
    assert opts["series"][1]["data"] == [[0, 1.0], [0, 9.0]]


def test_boxplot_whisker_includes_a_value_exactly_on_the_fence():
    # q1 == 4, q3 == 8, iqr == 4, so the lower fence lands exactly on -2. Inclusive
    # membership keeps it as the whisker end rather than exiling it as an outlier.
    df = pd.DataFrame({"g": ["a"] * 5, "v": [-2.0, 4.0, 6.0, 8.0, 10.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    assert _boxes(opts) == [[-2.0, 4.0, 6.0, 8.0, 10.0]]
    assert len(opts["series"]) == 1


def test_boxplot_whiskers_are_clamped_to_the_quartiles():
    # On a small, sharply skewed group the interpolated q1 can fall BELOW every
    # non-outlier observation: here q1 == 75 while the lowest in-fence point is 100. Left
    # alone, `low` would be 100 and the box's lower edge (75) would sit beneath its own
    # whisker. matplotlib clamps (`if np.min(wisklo) > q1: whislo = q1`) and so do we, so
    # low <= q1 <= median <= q3 <= high holds for every input. The 0 is still an outlier.
    df = pd.DataFrame({"g": ["a"] * 4, "v": [0.0, 100.0, 101.0, 102.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    low, q1, median, q3, high = _boxes(opts)[0]
    assert low == q1 == 75.0  # clamped, not 100.0
    assert [median, q3, high] == [100.5, 101.25, 102.0]
    assert low <= q1 <= median <= q3 <= high
    assert opts["series"][1]["data"] == [[0, 0.0]]


def test_boxplot_high_whisker_is_clamped_to_the_upper_quartile():
    # The mirror of the test above, and the reason the clamp is two-sided. Skew the group
    # the OTHER way and the interpolated q3 (27.0) rises above every non-outlier
    # observation (the largest is 2.0), so `high` must be clamped UP to q3 or the box's
    # upper edge would sit above its own whisker. Without this test the `max(..., q3)`
    # term is unexercised — the whole boxplot suite passes with it deleted.
    df = pd.DataFrame({"g": ["a"] * 4, "v": [0.0, 1.0, 2.0, 102.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    low, q1, median, q3, high = _boxes(opts)[0]
    assert high == q3 == 27.0  # clamped up, not the in-fence maximum of 2.0
    assert [low, q1, median] == [0.0, 0.75, 1.5]
    assert low <= q1 <= median <= q3 <= high
    assert opts["series"][1]["data"] == [[0, 102.0]]


def test_boxplot_non_finite_observations_are_dropped():
    # An infinity can't size a whisker, and left in it poisons the WHOLE box: the
    # quantiles go infinite, so iqr = inf - inf = nan, both fences are nan, every fence
    # comparison is false, and the five numbers all come back nan. Aggregation is what
    # makes this bite — a lone inf only spoils its own point in the pointwise branches.
    # So the non-finite values are dropped up front, exactly as NaN is.
    inf = float("inf")
    df = pd.DataFrame({"g": ["a"] * 4, "v": [1.0, 2.0, 3.0, inf]})
    assert _boxes(build_options(df, "boxplot", "g", ["v"]))[0] == [
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
    ]
    # Dropped, not flagged as an outlier — it can't be drawn at any coordinate.
    assert len(build_options(df, "boxplot", "g", ["v"])["series"]) == 1
    # Nothing finite left is just an empty group: keep the slot, like an all-NaN one.
    both = pd.DataFrame({"g": ["a", "a", "b", "b"], "v": [-inf, inf, 5.0, 7.0]})
    boxes = _boxes(build_options(both, "boxplot", "g", ["v"]))
    assert boxes[0] is EnforcedNull
    assert boxes[1] == [5.0, 5.5, 6.0, 6.5, 7.0]


def test_boxplot_finite_but_overflowing_group_becomes_enforced_null():
    # Dropping non-finite INPUTS is not enough for the one type that does arithmetic on
    # the values: a group of finite-but-huge numbers overflows during aggregation. With a
    # spread near the double range, iqr = q3 - q1 (and numpy's quantile interpolation,
    # a + (b - a) * frac) exceeds it and returns +/-inf, so a fence or the median itself
    # goes non-finite while the rest stay finite — smuggling the bare token `inf` past the
    # input guard and into the emitted JS (a blank iframe, a 400 from the export server).
    # The whole group is treated as unplottable, the same EnforcedNull box an all-missing
    # group gets. Reachable from a plain CSV: read_csv parses -9e307/9e307 as finite floats.
    big = 9e307  # finite (max double ~1.8e308), but 9e307 - (-9e307) overflows to inf
    df = pd.DataFrame({"g": ["a"] * 4, "v": [-big, -big, big, big]})
    boxes = _boxes(build_options(df, "boxplot", "g", ["v"]))
    assert boxes[0] is EnforcedNull
    # And it must not have leaked into the serialized JS (the sweep's non_finite_frame
    # only carries infinities in a value column that gets DROPPED, never this arithmetic
    # path, so it can't catch this — hence the direct assertion here).
    from highcharts_builder import make_chart

    js = make_chart(df, "boxplot", "g", ["v"]).to_js_literal()
    assert js and "inf" not in js


def test_boxplot_rejects_a_non_numeric_value_column():
    # The observations are cast to float64 before aggregating, so a text column raises
    # ValueError — the same contract the pointwise branches get for free from `float(v)`
    # (column/pie/scatter/treemap all raise it). Without the cast, `.quantile()` surfaces
    # an opaque dtype error from pandas' engine instead.
    df = pd.DataFrame({"g": ["a", "a"], "v": ["x", "y"]})
    with pytest.raises(ValueError):
        build_options(df, "boxplot", "g", ["v"])
    # A bool column still works, and means 1.0/0.0 — as `float(True)` does elsewhere.
    flags = pd.DataFrame({"g": ["a", "a"], "v": [True, False]})
    assert _boxes(build_options(flags, "boxplot", "g", ["v"]))[0] == [
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
    ]


def test_boxplot_all_missing_group_keeps_its_slot_as_enforced_null():
    # A group with no observations can't be summarized, but its category still exists, so
    # the slot is KEPT as EnforcedNull (heatmap's keep-the-axis-aligned rule, not pie's
    # drop-the-row one) — dropping it would slide every later box one place left. The
    # whole POINT is EnforcedNull; highcharts-core expands it to five nulls in the JS.
    from highcharts_builder import make_chart

    df = pd.DataFrame({"g": ["a", "a", "b", "b"], "v": [1.0, 2.0, float("nan"), None]})
    opts = build_options(df, "boxplot", "g", ["v"])
    assert opts["xAxis"]["categories"] == ["a", "b"]  # both slots kept
    boxes = _boxes(opts)
    assert boxes[0] == [1.0, 1.25, 1.5, 1.75, 2.0]
    assert boxes[1] is EnforcedNull  # missing box, not Python None or dropped
    js = make_chart(df, "boxplot", "g", ["v"]).to_js_literal()
    # A null closing the point array proves the EnforcedNull reached the data (Python
    # None would have been silently dropped) — as the heatmap null-cell test does.
    assert js and "null]" in js


def test_boxplot_missing_category_key_forms_no_group():
    # The other missing-data axis: a row whose x_col is NaN names no category at all, so
    # pandas' groupby(dropna=True) drops it. There is no slot to keep — unlike the
    # all-missing-observations group above, whose category the other rows still name.
    df = pd.DataFrame({"g": ["a", None, "b"], "v": [1.0, 2.0, 3.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    assert opts["xAxis"]["categories"] == ["a", "b"]
    assert len(_boxes(opts)) == 2


def test_boxplot_group_order_is_first_appearance():
    # groupby(sort=False): the boxes keep the frame's row order, the same fidelity every
    # other category-x type has (_category_labels never sorts). Sorted order would silently
    # reorder a user's meaningful sequence (Mon..Sun, or a funnel's stages).
    df = pd.DataFrame({"g": ["c", "a", "b", "a"], "v": [1.0, 2.0, 3.0, 4.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    assert opts["xAxis"]["categories"] == ["c", "a", "b"]


def test_boxplot_numeric_category_labels_coerce_to_strings():
    # The category-axis coercion, for the one type whose categories come from groupby keys
    # rather than _category_labels: highcharts-core rejects a non-string category
    # (CannotCoerceError on render), so a numeric grouping column must be stringified.
    df = pd.DataFrame({"yr": [2001, 2001, 2002], "v": [1.0, 2.0, 3.0]})
    assert build_options(df, "boxplot", "yr", ["v"])["xAxis"]["categories"] == [
        "2001",
        "2002",
    ]


def test_boxplot_uses_only_first_y_col():
    # Single-value like pie/treemap/sankey: only the first selected column is the
    # observations column (the app gives boxplot a single-select Y for exactly this).
    df = pd.DataFrame({"g": ["a", "a"], "v": [1.0, 3.0], "v2": [9.0, 9.0]})
    opts = build_options(df, "boxplot", "g", ["v", "v2"])
    assert opts["series"][0]["name"] == "v"
    assert _boxes(opts) == [[1.0, 1.5, 2.0, 2.5, 3.0]]


def test_boxplot_rejects_x_in_y():
    # The X column groups the observations, so it can't also BE them: every box would hold
    # one observation equal to its own label. The category-x rule, widened to boxplot.
    df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
    with pytest.raises(ValueError):
        build_options(df, "boxplot", "a", ["a"])


def test_boxplot_fill_color_is_accepted_then_silently_dropped():
    # THE boxplot trap, and the reason its box interior can't be themed at all. Both
    # `fillColor` and `stemColor` are read by BoxPlotOptions._get_kwargs_from_dict and
    # then never emitted by _to_untrimmed_dict, because the model has no such property —
    # so Chart.from_options ACCEPTS them and the JS silently lacks them. The same class of
    # trap as sankey's top-level tooltip.nodeFormat and treemap's "y"-instead-of-"value".
    # Only the serialized JS can prove it, so assert there. The fill therefore falls back
    # to Highcharts' `var(--highcharts-background-color)`, pinned to white by
    # _LIGHT_COLOR_SCHEME_CSS (see test_build_chart_html_pins_the_chart_color_scheme).
    # If a future highcharts-core starts honoring fillColor, this fails — and _themed
    # should then grow a boxplot hook that paints the interior with the theme.
    from highcharts_core.chart import Chart

    df = pd.DataFrame({"g": ["a", "a"], "v": [1.0, 2.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    # We don't set it — precisely because it wouldn't work.
    assert "fillColor" not in opts["plotOptions"]["boxplot"]
    assert "stemColor" not in opts["plotOptions"]["boxplot"]
    opts["plotOptions"]["boxplot"]["fillColor"] = "#123456"
    opts["plotOptions"]["boxplot"]["stemColor"] = "#654321"
    js = Chart.from_options(opts).to_js_literal()
    assert js and "type: 'boxplot'" in js  # it built and serialized...
    assert "123456" not in js  # ...and swallowed both colors whole
    assert "654321" not in js


def test_boxplot_serializes_and_pulls_in_the_more_module():
    # End to end: the 5-array box shape and its linked outlier scatter must serialize AND
    # resolve highcharts-more — the module boxplot shares with bubble and radar, not a
    # modules/*.js of its own. Assert on the compacted JS: the box must reach the data as
    # a positional array, which is the whole reason we don't build {name, low, ...} dicts
    # (highcharts-core collapses those with the name in the leading x slot).
    from highcharts_builder import make_chart

    df = pd.DataFrame({"g": ["a"] * 5, "v": [10.0, 11.0, 12.0, 13.0, 100.0]})
    chart = make_chart(df, "boxplot", "g", ["v"])
    js = chart.to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and "type: 'boxplot'" in js
    compact = "".join(js.split())
    assert "[10.0,11.0,12.0,13.0,13.0]" in compact  # the 5-array, not a dict point
    assert "linkedTo:':previous'" in compact  # the outlier series survived
    assert "type:'scatter'" in compact
    tags = chart.get_script_tags(as_str=True)
    assert "highcharts-more" in tags  # bubble/radar's module, shared
    assert "modules/" not in tags  # boxplot has no module of its own


def test_boxplot_light_mode_shape():
    # Mirrors the treemap/sankey light-mode tests: pin the choices nothing else guards.
    # The tooltip lives under plotOptions.boxplot (scoping it to the boxes, so the linked
    # outlier scatter keeps Highcharts' own point tooltip) and RENAMES the caps —
    # Highcharts calls point.low/point.high "Minimum"/"Maximum", a lie once an outlier is
    # drawn as its own point. The legend is off: it would only repeat the y-axis title.
    df = pd.DataFrame({"g": ["a", "a"], "v": [1.0, 2.0]})
    opts = build_options(df, "boxplot", "g", ["v"])
    assert opts["legend"]["enabled"] is False
    assert (
        "tooltip" not in opts
    )  # no top-level tooltip in light mode (a no-op, as ever)
    box_opts = opts["plotOptions"]["boxplot"]
    assert set(box_opts) == {"colorByPoint", "tooltip"}
    fmt = box_opts["tooltip"]["pointFormat"]
    assert "Upper whisker" in fmt and "Lower whisker" in fmt  # not Maximum/Minimum
    assert "{point.q1}" in fmt and "{point.median}" in fmt and "{point.q3}" in fmt
    assert box_opts["tooltip"]["headerFormat"] == "<b>{point.key}</b><br/>"


def test_boxplot_dark_mode_needs_no_box_hook():
    # Boxplot is the one mark-styling type with NO branch in _themed. Its box interior is
    # unsettable (see the fillColor trap) and so stays white in both themes, while
    # colorByPoint draws the border, whisker, stem and median in a palette hue legible
    # against that white — so there is nothing left to flip. Only the generic chrome moves.
    df = pd.DataFrame({"g": ["a", "a"], "v": [1.0, 2.0]})
    opts = build_options(df, "boxplot", "g", ["v"], dark=True)
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    assert opts["xAxis"]["labels"]["style"]["color"] == "#94a3b8"
    assert opts["yAxis"]["gridLineColor"] == "#334155"
    assert (
        opts["tooltip"]["backgroundColor"] == "#0f172a"
    )  # chrome _themed auto-creates
    # Untouched: no borderColor/fillColor/medianColor injected, unlike pie/treemap/sankey.
    assert set(opts["plotOptions"]["boxplot"]) == {"colorByPoint", "tooltip"}


# --------------------------------------------------------------------------- #
# Static-PNG failure messages (the export server's three different answers)
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeRequestError(OSError):
    """Stands in for a ``requests`` exception: they all subclass ``OSError`` and carry a
    ``response`` (``None`` when no HTTP answer ever arrived). Faked rather than imported,
    for the same reason the helper doesn't import requests — and so these tests need no
    network."""

    def __init__(self, status_code: int | None = None):
        super().__init__("boom")
        self.response = _FakeResponse(status_code) if status_code else None


def test_export_failure_explains_a_build_error_without_blaming_the_network():
    # `except Exception` also catches a ValueError raised by build_options before any
    # request is made. Telling that user to check their network sends them somewhere the
    # bug isn't. Non-OSError == it never left the process.
    from highcharts_builder import explain_export_failure

    message = explain_export_failure(ValueError("At least one y column is required."))
    assert "could not be built" in message
    assert "not with your network" in message
    assert "export server" in message  # names what it did NOT reach


def test_export_failure_explains_an_unreachable_server():
    from highcharts_builder import explain_export_failure

    message = explain_export_failure(_FakeRequestError())  # no HTTP response at all
    assert "could not be reached" in message
    assert "Check your network" in message


@pytest.mark.parametrize("status", [400, 413, 422])
def test_export_failure_explains_a_rejected_chart(status):
    # The case that most needs saying out loud: the server answered, so it is plainly
    # reachable, and the fault is in the payload we sent it.
    from highcharts_builder import explain_export_failure

    message = explain_export_failure(_FakeRequestError(status))
    assert f"HTTP {status}" in message
    assert "rejected this chart" in message
    assert "not at your network" in message
    assert "check your network" not in message.lower()  # the old, wrong advice


@pytest.mark.parametrize("status", [500, 502, 503])
def test_export_failure_explains_a_server_side_error(status):
    from highcharts_builder import explain_export_failure

    message = explain_export_failure(_FakeRequestError(status))
    assert f"HTTP {status}" in message
    assert "internal error" in message
    assert "rejected" not in message


def test_app_static_png_error_uses_the_export_failure_explainer():
    # The helper is only worth having if the app calls it, and the AppTest suite stays on
    # the network-free interactive path, so it can never reach that except block. Pin the
    # call site by reading the source — the same mechanical-sync idea as
    # test_theme_colors_stay_in_sync_with_config.
    source = (ROOT / "streamlit_app.py").read_text()
    assert "explain_export_failure" in source
    assert "explain_export_failure(exc)" in source
    # And the old advice, which asserted a cause it could not know, is gone for good.
    assert (
        "This usually means the Highcharts export server is unreachable" not in source
    )


# --------------------------------------------------------------------------- #
# Sample datasets
# --------------------------------------------------------------------------- #
def test_sample_datasets_are_plottable_and_fresh():
    from sample_data import SAMPLES

    assert SAMPLES  # the app offers these when no CSV is uploaded
    for label, factory in SAMPLES.items():
        df = factory()
        assert not df.empty, label
        # The app stops with an error unless a dataset has a numeric column.
        assert df.select_dtypes("number").shape[1] >= 1, label

    # Each call returns a fresh frame, so per-session mutation can't leak.
    factory = next(iter(SAMPLES.values()))
    assert factory() is not factory()


def test_daily_temperature_sample_builds_an_areaspline_chart():
    # The areaspline sample is wired to its intended type: plot the real sample
    # as an areaspline and pin the shape it produces (24 hourly categories, one
    # full series) — ties the new dataset to the new chart type end to end.
    from sample_data import _daily_temperature

    df = _daily_temperature()
    opts = build_options(df, "areaspline", "hour", ["temp_c"])
    assert opts["chart"]["type"] == "areaspline"
    assert opts["series"][0]["name"] == "temp_c"
    assert opts["xAxis"]["categories"][0] == "00:00"
    assert len(opts["xAxis"]["categories"]) == len(opts["series"][0]["data"]) == 24


def test_country_economics_sample_builds_a_bubble_chart():
    # Ties the new bubble sample to its intended type end to end: a numeric GDP (X)
    # and life-expectancy (Y) pair with a population size column produces one
    # [x, y, z] triple per country row.
    from sample_data import _country_economics

    df = _country_economics()
    opts = build_options(
        df, "bubble", "gdp_per_capita_k", ["life_expectancy"], size_col="population_m"
    )
    assert opts["chart"]["type"] == "bubble"
    assert opts["series"][0]["name"] == "life_expectancy"
    assert len(opts["series"][0]["data"]) == len(df)
    assert len(opts["series"][0]["data"][0]) == 3  # [x, y, z]


def test_product_ratings_sample_builds_a_radar_chart():
    # Ties the new radar sample to its intended type end to end: a category axis
    # (attribute) with two numeric product-score series produces a polar line
    # chart, one series per product, each covering every attribute row.
    from sample_data import _product_ratings

    df = _product_ratings()
    opts = build_options(df, "radar", "attribute", ["Aurora", "Zephyr"])
    assert opts["chart"]["type"] == "line" and opts["chart"]["polar"] is True
    assert [s["name"] for s in opts["series"]] == ["Aurora", "Zephyr"]
    assert opts["xAxis"]["categories"][0] == "Design"
    assert len(opts["series"][0]["data"]) == len(df)
    assert opts["legend"]["enabled"] is True


def test_website_activity_sample_builds_a_heatmap_chart():
    # Ties the new heatmap sample to its intended type end to end: a weekday
    # category (X) plus four numeric time-block columns (Y) produce a full grid of
    # [x, y, value] cells — one per (weekday, block), none dropped.
    from sample_data import _weekly_activity

    df = _weekly_activity()
    y_cols = ["Night", "Morning", "Afternoon", "Evening"]
    opts = build_options(df, "heatmap", "weekday", y_cols)
    assert opts["chart"]["type"] == "heatmap"
    assert opts["yAxis"]["categories"] == y_cols
    assert opts["xAxis"]["categories"][0] == "Mon"
    assert len(opts["series"][0]["data"]) == len(df) * len(y_cols)


def test_company_market_cap_sample_builds_a_treemap_chart():
    # Ties the new treemap sample to its intended type end to end: a company label
    # (X) plus one market-cap value column (Y) produce one sized tile per company
    # row, each a {name, value} leaf.
    from sample_data import _company_market_cap

    df = _company_market_cap()
    opts = build_options(df, "treemap", "company", ["market_cap_b"])
    assert opts["chart"]["type"] == "treemap"
    assert opts["series"][0]["name"] == "market_cap_b"
    assert len(opts["series"][0]["data"]) == len(df)
    assert opts["series"][0]["data"][0]["name"] == "Apple"
    assert "value" in opts["series"][0]["data"][0]


def test_energy_flow_sample_builds_a_sankey_chart():
    # Ties the new sankey sample to its intended type end to end: two node columns
    # plus a numeric weight produce one link per row. Unlike every other sample, its
    # source values REPEAT, and "Electricity" is both a link target and a link
    # source — that is what makes the second hop appear rather than a bipartite fan.
    from sample_data import _energy_flow

    df = _energy_flow()
    opts = build_options(
        df, "sankey", "source", ["terawatt_hours"], target_col="target"
    )
    assert opts["chart"]["type"] == "sankey"
    assert opts["series"][0]["name"] == "terawatt_hours"
    links = _links(opts)
    assert len(links) == len(df)
    assert links[0] == {"from": "Coal", "to": "Electricity", "weight": 42.0}
    sources = {link["from"] for link in links}
    targets = {link["to"] for link in links}
    assert "Electricity" in sources & targets  # the two-hop node
    # The flow balances: everything generated is consumed.
    generated = sum(link["weight"] for link in links if link["to"] == "Electricity")
    consumed = sum(link["weight"] for link in links if link["from"] == "Electricity")
    assert generated == consumed == 150.0


def test_response_times_sample_builds_a_boxplot_chart():
    # Ties the new boxplot sample to its intended type end to end. Like the sankey sample
    # (and unlike every other, which has one row per unique x value) its x values REPEAT
    # — that is the long/tidy shape boxplot aggregates. 60 rows collapse to 4 boxes, and
    # the lone 890 ms spike in `search` (category index 1) is the frame's only Tukey
    # outlier, so the linked scatter has exactly one point to draw.
    from sample_data import _response_times

    df = _response_times()
    opts = build_options(df, "boxplot", "service", ["response_ms"])
    assert opts["chart"]["type"] == "boxplot"
    assert opts["series"][0]["name"] == "response_ms"
    assert opts["xAxis"]["categories"] == ["auth", "search", "checkout", "profile"]
    assert len(_boxes(opts)) == df["service"].nunique() == 4
    assert len(df) == 60  # ~15 raw observations per service, not one row per box
    # search's box stops at its 120 ms whisker; the 890 ms spike is the sole outlier.
    assert _boxes(opts)[1] == [85.0, 94.0, 101.0, 109.0, 120.0]
    assert opts["series"][1]["data"] == [[1, 890.0]]
    # Every box is well formed: low <= q1 <= median <= q3 <= high.
    for box in _boxes(opts):
        assert list(box) == sorted(box)


# --------------------------------------------------------------------------- #
# Full app, headless (Streamlit AppTest)
#
# These drive the UI control flow, not chart correctness (the builder tests
# above own that). The rendered chart lives in an opaque st.iframe that AppTest
# can't see into, but the "generated config" toggle reveals the Highcharts JS
# literal via st.code — so, after switching that toggle on, we assert the
# controls actually reach the builder. (It's a toggle rather than an expander
# because a collapsed expander body still runs on every rerun; the toggle skips
# building the JS until asked, and unlike an expander AppTest can switch it on.)
# Sidebar widgets are addressed by position: selectbox [0] Dataset, [1] Chart
# type, [2] X axis; segmented_control [0] Source, [1] Render mode; pills [0] the
# Y series (a wide CSV upload swaps these pills for a multiselect); toggle [0] the
# generated-config reveal. Those indices hold for every type, because the two
# type-specific extra controls are created *after* the X selectbox: bubble's
# "Size (Z)" and sankey's "Target (to)". Both are addressed by LABEL rather than
# index, since they shift the widgets that follow them. Everything here stays on
# the network-free interactive path (the Static PNG mode would call the export
# server).
# --------------------------------------------------------------------------- #
@pytest.fixture
def app():
    """A freshly loaded, run-once AppTest for the Streamlit app."""
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60).run()


def _reveal_config(app):
    """Flip the generated-config toggle on (revealing the st.code panel)."""
    app.toggle[0].set_value(True).run()


def _metrics(app) -> dict[str, str]:
    """The KPI metric row as a ``{label: value}`` dict."""
    return {m.label: m.value for m in app.metric}


def test_app_config_hidden_by_default_then_revealed_by_toggle(app):
    # The point of the toggle (vs an always-rendering expander): on a default run
    # the config JS is NOT built or shown; it appears only once the toggle is on.
    assert not app.code  # nothing rendered while the toggle is off
    _reveal_config(app)
    assert not app.exception
    assert app.code and "Highcharts" in app.code[0].value  # config now rendered


def test_app_switch_to_pie_regenerates_config(app):
    app.selectbox[1].set_value("pie")  # Chart type -> pie
    _reveal_config(app)
    assert not app.exception
    assert "type: 'pie'" in app.code[0].value


def test_app_switch_to_bubble_shows_size_control_and_regenerates_config(app):
    # Bubble adds a "Size (Z)" selectbox that no other type shows, and drives the
    # config through the size_col plumbing. Stays on the network-free config path.
    assert not any(sb.label == "Size (Z)" for sb in app.selectbox)  # absent by default
    app.selectbox[1].set_value("bubble").run()  # Chart type -> bubble
    assert not app.exception
    assert any(sb.label == "Size (Z)" for sb in app.selectbox)  # now present
    _reveal_config(app)
    assert not app.exception
    assert "type: 'bubble'" in app.code[0].value


def test_app_switch_to_radar_regenerates_config(app):
    # Radar renders as a polar line chart; switching to it drives the config
    # through the shared category-x path. `polar: true` (absent from a plain line)
    # proves the radar branch — not the cartesian one — produced it. Network-free.
    app.selectbox[1].set_value("radar").run()  # Chart type -> radar
    assert not app.exception
    _reveal_config(app)
    assert not app.exception
    assert "polar: true" in app.code[0].value


def test_app_switch_to_heatmap_regenerates_config(app):
    # Heatmap reinterprets the category-x data as a value matrix colored by a
    # colorAxis; switching to it drives the config through the heatmap branch.
    # `type: 'heatmap'` + the colorAxis prove it — heatmap adds no extra sidebar
    # control, so the positional widget indices are unchanged. Network-free.
    app.selectbox[1].set_value("heatmap").run()  # Chart type -> heatmap
    assert not app.exception
    _reveal_config(app)
    assert not app.exception
    assert "type: 'heatmap'" in app.code[0].value
    assert "colorAxis" in app.code[0].value


def test_app_switch_to_treemap_regenerates_config(app):
    # Treemap is single-value like pie, so switching to it swaps the Y pills for a
    # single-select Y (an extra selectbox, exactly as pie does) and drives the
    # config through the treemap branch. `type: 'treemap'` proves that branch
    # produced it. Modeled on the pie test (widgets addressed by index [1]) — NOT
    # heatmap, whose multi=True pills leave the widget indices unchanged. Network-free.
    app.selectbox[1].set_value("treemap").run()  # Chart type -> treemap
    assert not app.exception
    _reveal_config(app)
    assert not app.exception
    assert "type: 'treemap'" in app.code[0].value


def test_app_switch_to_sankey_shows_target_control_and_regenerates_config(app):
    # Sankey is the second type with a required extra column (after bubble): it
    # reveals a "Target (to)" selectbox that no other type shows, and drives the
    # config through the target_col plumbing. Addressed by LABEL, not index — unlike
    # bubble's Size (Z), the Target control sits between the X and the single-select
    # Y widgets, so the positional indices past [2] shift. Stays network-free.
    assert not any(sb.label == "Target (to)" for sb in app.selectbox)  # absent
    app.selectbox[1].set_value("sankey").run()  # Chart type -> sankey
    assert not app.exception
    assert any(sb.label == "Target (to)" for sb in app.selectbox)  # now present
    # Single-select Y (the weight), like pie/treemap — not the multi-select pills.
    assert any(sb.label == "Flow value (weight)" for sb in app.selectbox)
    assert not app.pills
    _reveal_config(app)
    assert not app.exception
    assert "type: 'sankey'" in app.code[0].value


def test_app_sankey_target_survives_a_source_change(app):
    # The keyless-widget trap the Target selectbox's `index` guards against. These
    # widgets carry no key, so Streamlit folds `index` into their identity: a default
    # derived from x_col (the tempting "the column after Source") would re-mint the
    # widget whenever Source changed, silently discarding the user's Target. Pick a
    # Target, change Source, and assert the Target survives. A dynamic index makes
    # this fail — nothing else in the suite would notice.
    app.selectbox[1].set_value("sankey").run()  # Chart type -> sankey
    target = next(sb for sb in app.selectbox if sb.label == "Target (to)")
    target.set_value("cost").run()  # the third column, not the default
    assert not app.exception
    app.selectbox[2].set_value("revenue").run()  # Source (from): month -> revenue
    assert not app.exception
    target = next(sb for sb in app.selectbox if sb.label == "Target (to)")
    assert target.value == "cost"  # not reset to the default


def test_app_sankey_source_equals_target_shows_guard_warning(app):
    # Sankey's own guard, NOT the category-x x-in-y rule (which the Target column
    # can't trip — it's never among the Y series): naming one column as both ends of
    # a link would make every link a self-loop. The default Source is the first
    # column, so pointing Target at it collides.
    app.selectbox[1].set_value("sankey").run()  # Chart type -> sankey
    target = next(sb for sb in app.selectbox if sb.label == "Target (to)")
    target.set_value("month").run()  # == the default Source column
    assert not app.exception
    assert app.warning
    assert "Source and Target must be different" in app.warning[0].value


def test_app_sankey_kpi_shows_flows(app):
    # Sankey is one series of links, so the KPI swaps "Series plotted" (which would
    # read a bare 1) for "Flows" = the rows that become links — mirroring heatmap's
    # "Cells" and treemap's "Tiles". The default dataset has no missing values, so
    # every row is a flow.
    from sample_data import SAMPLES

    app.selectbox[1].set_value("sankey").run()  # Chart type -> sankey
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    default_df = next(iter(SAMPLES.values()))()
    assert metrics["Flows"] == f"{len(default_df):,}"


def test_app_switch_to_boxplot_shows_single_select_y_and_regenerates_config(app):
    # Boxplot reads its Y as one column of raw observations, so — like pie/treemap/sankey
    # — it swaps the multi-select Y pills for a single selectbox. It needs no EXTRA
    # column selector (unlike bubble's Size and sankey's Target), so it adds exactly one
    # widget. Modeled on the pie/treemap tests, not heatmap's (whose multi=True pills
    # leave the widget indices unchanged). Network-free.
    app.selectbox[1].set_value("boxplot").run()  # Chart type -> boxplot
    assert not app.exception
    assert not app.pills  # single-select Y, so the pills are gone
    assert any(sb.label == "Observations (Y)" for sb in app.selectbox)
    assert not any(sb.label == "Size (Z)" for sb in app.selectbox)  # no extra selector
    assert not any(sb.label == "Target (to)" for sb in app.selectbox)
    _reveal_config(app)
    assert not app.exception
    assert "type: 'boxplot'" in app.code[0].value


def test_app_boxplot_kpi_shows_boxes(app):
    # Boxplot is one series of boxes, so the KPI swaps "Series plotted" (which would read
    # a bare 1) for "Boxes" = the distinct categories — mirroring heatmap's "Cells",
    # treemap's "Tiles" and sankey's "Flows". The default dataset has one row per month,
    # so each month is a (degenerate, single-observation) box.
    from sample_data import SAMPLES

    app.selectbox[1].set_value("boxplot").run()  # Chart type -> boxplot
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    default_df = next(iter(SAMPLES.values()))()
    # The app's default X is the first column, as the X selectbox's default index shows.
    expected = default_df[default_df.columns[0]].nunique()
    assert metrics["Boxes"] == f"{expected:,}"


def test_app_chart_type_selector_offers_every_supported_type(app):
    # Contract test mirroring test_app_render_mode_selector_offers_the_two_modes:
    # the chart-type selectbox offers exactly SUPPORTED_TYPES (so a new builder
    # type shows up in the UI, and a removed/renamed one fails here) and defaults
    # to the first. Also pins the positional index [1] other app tests rely on.
    selector = app.selectbox[1]
    assert selector.label == "Chart type"
    assert list(selector.options) == list(SUPPORTED_TYPES)
    assert selector.value == SUPPORTED_TYPES[0]


def test_app_custom_title_flows_into_config(app):
    app.text_input(key="chart_title").set_value("My Title")
    _reveal_config(app)
    assert not app.exception
    assert "My Title" in app.code[0].value


def test_app_multiple_series_selected(app):
    # The revenue-vs-cost sample has two numeric columns; select both via pills.
    app.pills[0].set_value(["revenue", "cost"])
    _reveal_config(app)
    assert not app.exception
    js = app.code[0].value
    assert "revenue" in js and "cost" in js


def test_app_x_equals_y_shows_guard_warning(app):
    # Force the category-x "X can't also be a Y series" guard (CATEGORY_X_TYPES)
    # from the UI, exercised here via the default line/cartesian type: set the X
    # axis to a numeric column and pick that same column as the Y series.
    app.selectbox[2].set_value("revenue").run()  # Category (X) axis
    app.pills[0].set_value(["revenue"]).run()  # Series (Y)
    assert not app.exception
    assert app.warning
    assert "can't also be a Y series" in app.warning[0].value


def test_app_upload_csv_with_no_file_shows_info_guard(app):
    # The second data source: switching to "Upload CSV" with no file uploaded
    # hits the st.info + st.stop guard. Network-free (no CSV read, no render).
    app.segmented_control[0].set_value("Upload CSV").run()  # Source
    assert not app.exception
    assert app.info
    assert "Upload a CSV" in app.info[0].value


def test_app_render_mode_selector_offers_the_two_modes(app):
    # After removing the click-events mode, the Render selector offers exactly
    # two modes and defaults to the interactive one. This pins the two-mode
    # contract (a re-added or renamed mode fails here) and guards the positional
    # index [1] the other app tests rely on.
    mode = app.segmented_control[1]
    assert mode.label == "Mode"
    assert list(mode.options) == ["Interactive", "Static PNG"]
    assert mode.value == "Interactive"


def test_app_default_interactive_mode_shows_iframe_caption(app):
    # The default (Interactive) render shows the iframe (CDN) caption; the
    # negative check that no click-events caption appears is a light backstop —
    # the selector-options test above owns the two-mode contract.
    assert not app.exception
    assert any(
        "Highcharts JS is loaded from the CDN" in cap.value for cap in app.caption
    )
    assert not any("Custom Component" in cap.value for cap in app.caption)


def test_app_generated_config_includes_brand_palette(app):
    # The brand palette reaches the iframe/PNG paths through build_options; the
    # generated-config toggle is the visible proof once switched on.
    _reveal_config(app)
    assert not app.exception
    assert DEFAULT_COLORS[0] in app.code[0].value


def _csv_bytes(num_numeric: int) -> bytes:
    """A CSV: one label column + ``num_numeric`` numeric columns, three rows."""
    header = ",".join(["label"] + [f"m{i}" for i in range(num_numeric)])
    rows = "\n".join(
        f"r{r}," + ",".join(str(r + i) for i in range(num_numeric)) for r in range(3)
    )
    return (header + "\n" + rows).encode()


def test_app_wide_csv_upload_swaps_pills_for_multiselect(app):
    # The Y-series picker uses compact pills for narrow data (<=5 numeric columns,
    # like every sample) but falls back to st.multiselect for a wide uploaded CSV
    # so it doesn't wrap the narrow sidebar. Seven numeric columns trips it.
    app.segmented_control[0].set_value("Upload CSV").run()  # Source
    app.file_uploader[0].set_value(("wide.csv", _csv_bytes(7), "text/csv")).run()
    assert not app.exception
    assert not app.pills  # the pills widget is gone
    assert len(app.multiselect) == 1
    assert list(app.multiselect[0].options) == [f"m{i}" for i in range(7)]


def test_app_narrow_csv_upload_keeps_pills(app):
    # A narrow upload (<=5 numeric columns) stays on pills, like the samples — so
    # the pills-based tests above keep exercising the common path.
    app.segmented_control[0].set_value("Upload CSV").run()  # Source
    app.file_uploader[0].set_value(("narrow.csv", _csv_bytes(2), "text/csv")).run()
    assert not app.exception
    assert len(app.pills) == 1
    assert not app.multiselect


@pytest.mark.parametrize(("num_numeric", "widget"), [(5, "pills"), (6, "multiselect")])
def test_app_pills_multiselect_boundary(app, num_numeric, widget):
    # Pin the MAX_PILL_OPTIONS (5) threshold at its edge: exactly 5 numeric columns
    # keeps pills, 6 switches to multiselect. The wide/narrow tests use 7 and 2,
    # far from the decision point, so an off-by-one would slip past them.
    app.segmented_control[0].set_value("Upload CSV").run()  # Source
    app.file_uploader[0].set_value(
        (f"n{num_numeric}.csv", _csv_bytes(num_numeric), "text/csv")
    ).run()
    assert not app.exception
    if widget == "pills":
        assert len(app.pills) == 1 and not app.multiselect
    else:
        assert len(app.multiselect) == 1 and not app.pills


def test_app_chart_type_selector_has_help(app):
    # The chart-type selector silently reshapes the X/Y controls, so it carries a
    # markdown help tooltip naming each type's data shape (mirrors the Mode help).
    help_text = app.selectbox[1].help  # selectbox [1] is Chart type
    assert help_text
    assert "pie" in help_text and "scatter" in help_text and "bubble" in help_text
    assert "radar" in help_text
    assert "heatmap" in help_text
    assert "treemap" in help_text
    assert "sankey" in help_text
    assert "boxplot" in help_text
    # Every cartesian type is named in the prose; loop so a future addition to
    # CARTESIAN_TYPES that's forgotten in the help text actually fails here.
    for chart_type in CARTESIAN_TYPES:
        assert chart_type in help_text


def test_app_kpi_row_summarizes_active_data(app):
    # The KPI row surfaces the active data at a glance. Derive the expected values
    # from the same sources the app uses, rather than hardcoding sample internals.
    from sample_data import SAMPLES

    default_df = next(iter(SAMPLES.values()))()  # the first dataset is the default
    numeric = default_df.select_dtypes("number").columns
    assert _metrics(app) == {
        "Rows": f"{len(default_df):,}",
        "Numeric columns": str(len(numeric)),
        "Series plotted": "1",  # the default selects numeric_cols[:1]
    }


def test_app_kpi_series_count_tracks_selection_and_empty_state(app):
    # "Series plotted" follows the Y selection and reads 0 — a useful empty state,
    # not a blank — once cleared, since the KPI row sits above the empty-y guard.
    app.pills[0].set_value(["revenue", "cost"]).run()
    assert not app.exception
    assert _metrics(app)["Series plotted"] == "2"
    app.pills[0].set_value([]).run()
    assert not app.exception
    assert _metrics(app)["Series plotted"] == "0"


def test_app_heatmap_kpi_shows_cells_not_series(app):
    # Heatmap is a single series, so the KPI swaps "Series plotted" (which would
    # misreport len(y_cols)) for "Cells" = rows × columns.
    from sample_data import SAMPLES

    app.selectbox[1].set_value("heatmap").run()  # Chart type -> heatmap
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    # Default dataset (6 rows); the default Y selection is one column -> 6 cells.
    default_df = next(iter(SAMPLES.values()))()
    assert metrics["Cells"] == f"{len(default_df) * 1:,}"


def test_app_treemap_kpi_shows_tiles(app):
    # Treemap is one series of tiles (like pie), so the KPI swaps "Series plotted"
    # (which would read a bare 1) for "Tiles" = the non-null values that become
    # rectangles — mirroring heatmap's "Cells".
    from sample_data import SAMPLES

    app.selectbox[1].set_value("treemap").run()  # Chart type -> treemap
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    # Default dataset; treemap's single-value control selects one column, so every
    # (non-null) row is one tile.
    default_df = next(iter(SAMPLES.values()))()
    assert metrics["Tiles"] == f"{len(default_df):,}"


def test_app_chart_type_badge_reflects_selection(app):
    # Chart type is a categorical badge by the chart (not a metric), and updates
    # when the selection changes. AppTest renders st.badge as markdown.
    def badge_texts(a):
        return [m.value for m in a.markdown if "-badge[" in m.value]

    assert any("Line chart" in b for b in badge_texts(app))
    app.selectbox[1].set_value("pie").run()  # Chart type -> pie
    assert not app.exception
    assert any("Pie chart" in b for b in badge_texts(app))
