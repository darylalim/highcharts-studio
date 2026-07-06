"""Smoke and behavior tests for the Highcharts builder and the Streamlit app.

Run with: ``uv run pytest``

Layers:

- ``build_options`` unit tests covering every supported chart type, the
  missing-data and scatter/bubble edge cases (NaN -> ``EnforcedNull`` for
  cartesian and radar series, dropped points/slices elsewhere, numeric vs
  non-numeric x, and bubble's (x, y, size) triples whose series share one size
  column, its ``highcharts-more`` module resolution, and its dimension-naming
  tooltip), radar's polar-line shape (chart.type "line" + ``chart.polar``,
  sharing the ``highcharts-more`` module), heatmap's category × category value
  matrix (``[x, y, value]`` cells colored by a ``colorAxis``, empty cells kept as
  ``EnforcedNull``, resolving its own ``modules/heatmap.js``), treemap's
  value-sized tiles (``{name, value}`` leaves colored categorically via
  ``colorByPoint``, missing values dropped like pie, resolving its own
  ``modules/treemap.js``), the brand-palette
  (``DEFAULT_COLORS`` / ``colors`` override), and the validation guards
  (unsupported type, empty ``y_cols``, the category-x x-in-y rule widened to
  heatmap, and the bubble size-column requirement).
- light/dark theming: dark mode paints the chart background (light leaves it
  unset), the chart chrome (axes/text/gridlines, pie labels, and the tooltip)
  flips while the ``DEFAULT_COLORS`` palette stays shared across modes, and
  ``build_chart_html`` gives the iframe body a background that tracks the mode.
- ``sample_data`` unit tests: every built-in dataset is plottable (fresh,
  non-empty, with a numeric column).
- Headless ``AppTest`` interaction tests that drive the full Streamlit app's
  control flow — switching chart type (including bubble, which reveals a
  Size (Z) control, radar, heatmap, and treemap), title, and series, revealing
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
    """A label column plus a numeric column — valid input for every chart type."""
    return pd.DataFrame({"label": ["a", "b", "c"], "value": [1.0, 2.0, 3.0]})


def _size_for(chart_type: str) -> str | None:
    """The size column the SUPPORTED_TYPES-parametrized tests pass for the bubble
    case: bubble requires one (its marker-size dimension); other types ignore it,
    so it's None. The shared ``labeled_frame`` has "value" as its only numeric
    column, so it doubles as the size."""
    return "value" if chart_type == "bubble" else None


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
        labeled_frame, chart_type, "label", ["value"], size_col=_size_for(chart_type)
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
        labeled_frame, chart_type, "label", ["value"], size_col=_size_for(chart_type)
    ).to_js_literal()
    assert js and f"type: '{_hc_type(chart_type)}'" in js


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_default_title_per_type(labeled_frame, chart_type):
    opts = build_options(
        labeled_frame, chart_type, "label", ["value"], size_col=_size_for(chart_type)
    )
    assert opts["title"]["text"] == f"{chart_type.title()} chart"


def test_explicit_title_overrides_default(labeled_frame):
    opts = build_options(labeled_frame, "line", "label", ["value"], title="Custom")
    assert opts["title"]["text"] == "Custom"


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_default_palette_applied_per_type(labeled_frame, chart_type):
    # Every chart type carries the brand palette so all render modes share a look.
    opts = build_options(
        labeled_frame, chart_type, "label", ["value"], size_col=_size_for(chart_type)
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
    )
    assert opts["chart"]["backgroundColor"] == "#0f172a"


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_light_mode_leaves_chart_background_unset(labeled_frame, chart_type):
    # Light mode is a no-op: no backgroundColor is injected, so the output is
    # exactly what it was before dark mode existed.
    opts = build_options(
        labeled_frame, chart_type, "label", ["value"], size_col=_size_for(chart_type)
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
# generated-config reveal. Everything here stays on the network-free interactive
# path (the Static PNG mode would call the export server).
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
