"""Smoke and behavior tests for the Highcharts builder and the Streamlit app.

Run with: ``uv run pytest``

Layers:

- ``build_options`` unit tests covering every supported chart type, the
  missing-data and scatter edge cases (NaN -> ``EnforcedNull`` for cartesian
  series, dropped points/slices elsewhere, and numeric vs non-numeric scatter
  x), the brand-palette (``DEFAULT_COLORS`` / ``colors`` override), and the
  validation guards (unsupported type, empty ``y_cols``, and the cartesian-only
  x-in-y rule).
- light/dark theming: dark mode paints the chart background (light leaves it
  unset), the chart chrome (axes/text/gridlines, pie labels, and the tooltip)
  flips while the ``DEFAULT_COLORS`` palette stays shared across modes, and
  ``build_chart_html`` gives the iframe body a background that tracks the mode.
- ``sample_data`` unit tests: every built-in dataset is plottable (fresh,
  non-empty, with a numeric column).
- Headless ``AppTest`` interaction tests that drive the full Streamlit app's
  control flow — switching chart type, title, and series, revealing the
  generated Highcharts config behind its toggle, the KPI metric row, the
  wide-CSV multiselect fallback, and the render-mode selector's two modes
  (interactive iframe / static PNG), plus tripping the x-in-y warning and the
  no-CSV-uploaded info guard — asserting on the generated config (incl. the
  brand palette) and the guard messages.
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
    DEFAULT_COLORS,
    SUPPORTED_TYPES,
    build_chart_html,
    build_options,
)


@pytest.fixture
def labeled_frame() -> pd.DataFrame:
    """A label column plus a numeric column — valid input for every chart type."""
    return pd.DataFrame({"label": ["a", "b", "c"], "value": [1.0, 2.0, 3.0]})


# --------------------------------------------------------------------------- #
# Every supported type builds
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_supported_type_builds(labeled_frame, chart_type):
    opts = build_options(labeled_frame, chart_type, "label", ["value"])
    assert opts["chart"]["type"] == chart_type
    assert opts["series"]  # at least one series/data set was produced


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_default_title_per_type(labeled_frame, chart_type):
    opts = build_options(labeled_frame, chart_type, "label", ["value"])
    assert opts["title"]["text"] == f"{chart_type.title()} chart"


def test_explicit_title_overrides_default(labeled_frame):
    opts = build_options(labeled_frame, "line", "label", ["value"], title="Custom")
    assert opts["title"]["text"] == "Custom"


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_default_palette_applied_per_type(labeled_frame, chart_type):
    # Every chart type carries the brand palette so all render modes share a look.
    opts = build_options(labeled_frame, chart_type, "label", ["value"])
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
    opts = build_options(labeled_frame, chart_type, "label", ["value"], dark=True)
    assert opts["chart"]["backgroundColor"] == "#0f172a"


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_light_mode_leaves_chart_background_unset(labeled_frame, chart_type):
    # Light mode is a no-op: no backgroundColor is injected, so the output is
    # exactly what it was before dark mode existed.
    opts = build_options(labeled_frame, chart_type, "label", ["value"])
    assert "backgroundColor" not in opts["chart"]


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_dark_mode_keeps_the_shared_palette(labeled_frame, chart_type):
    opts = build_options(labeled_frame, chart_type, "label", ["value"], dark=True)
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
    opts = build_options(labeled_frame, chart_type, "label", ["value"], dark=True)
    assert opts["tooltip"]["backgroundColor"] == "#0f172a"
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
# Cartesian: line / spline / area / column / bar
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


@pytest.mark.parametrize("chart_type", CARTESIAN_TYPES)
def test_cartesian_missing_value_becomes_enforced_null(chart_type):
    df = pd.DataFrame({"x": ["a", "b", "c"], "y": [1.0, float("nan"), 3.0]})
    data = build_options(df, chart_type, "x", ["y"])["series"][0]["data"]
    assert data[0] == 1.0
    assert data[1] is EnforcedNull  # missing point, not Python None
    assert data[2] == 3.0


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


@pytest.mark.parametrize("chart_type", CARTESIAN_TYPES)
def test_cartesian_rejects_x_in_y(chart_type):
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    with pytest.raises(ValueError):
        build_options(df, chart_type, "y", ["y"])


def test_scatter_allows_x_in_y():
    # The x-in-y guard is cartesian-only; scatter happily pairs a column with
    # itself (a diagonal of points).
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


def test_app_default_run_emits_highcharts_config(app):
    app.toggle[0].set_value(True).run()  # reveal the generated-config panel
    assert not app.exception
    assert "Highcharts" in app.code[0].value  # the generated config rendered


def test_app_switch_to_pie_regenerates_config(app):
    app.selectbox[1].set_value("pie")  # Chart type -> pie
    app.toggle[0].set_value(True).run()  # reveal the generated-config panel
    assert not app.exception
    assert "type: 'pie'" in app.code[0].value


def test_app_custom_title_flows_into_config(app):
    app.text_input(key="chart_title").set_value("My Title")
    app.toggle[0].set_value(True).run()  # reveal the generated-config panel
    assert not app.exception
    assert "My Title" in app.code[0].value


def test_app_multiple_series_selected(app):
    # The revenue-vs-cost sample has two numeric columns; select both via pills.
    app.pills[0].set_value(["revenue", "cost"])
    app.toggle[0].set_value(True).run()  # reveal the generated-config panel
    assert not app.exception
    js = app.code[0].value
    assert "revenue" in js and "cost" in js


def test_app_x_equals_y_shows_guard_warning(app):
    # Force the cartesian "X can't also be a Y series" guard from the UI: set the
    # X axis to a numeric column and pick that same column as the Y series.
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
    app.toggle[0].set_value(True).run()  # reveal the generated-config panel
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


def test_app_chart_type_selector_has_help(app):
    # The chart-type selector silently reshapes the X/Y controls, so it carries a
    # markdown help tooltip naming each type's data shape (mirrors the Mode help).
    help_text = app.selectbox[1].help  # selectbox [1] is Chart type
    assert help_text
    assert "pie" in help_text and "scatter" in help_text


def test_app_kpi_row_summarizes_active_data(app):
    # The KPI row above the cards surfaces the active data + config at a glance.
    # Defaults: revenue-vs-cost sample (6 rows, 2 numeric cols), one series, line.
    assert {m.label: m.value for m in app.metric} == {
        "Rows": "6",
        "Numeric columns": "2",
        "Series plotted": "1",
        "Chart type": "Line",
    }


def test_app_kpi_series_count_tracks_selection_and_empty_state(app):
    # "Series plotted" follows the Y selection and reads 0 — a useful empty state,
    # not a blank — once cleared, since the KPI row sits above the empty-y guard.
    app.pills[0].set_value(["revenue", "cost"]).run()
    assert not app.exception
    assert {m.label: m.value for m in app.metric}["Series plotted"] == "2"
    app.pills[0].set_value([]).run()
    assert not app.exception
    assert {m.label: m.value for m in app.metric}["Series plotted"] == "0"
