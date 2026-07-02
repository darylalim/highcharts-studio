"""Smoke and behavior tests for the Highcharts builder and the Streamlit app.

Run with: ``uv run pytest``

Layers:

- ``build_options`` unit tests covering every supported chart type, the
  missing-data and scatter edge cases (NaN -> ``EnforcedNull`` for cartesian
  series, dropped points/slices elsewhere, and numeric vs non-numeric scatter
  x), the brand-palette (``DEFAULT_COLORS`` / ``colors`` override), and the
  validation guards (unsupported type, empty ``y_cols``, and the cartesian-only
  x-in-y rule).
- ``sample_data`` unit tests: every built-in dataset is plottable (fresh,
  non-empty, with a numeric column).
- Headless ``AppTest`` interaction tests that drive the full Streamlit app's
  control flow — switching chart type, title, series, and render mode — and
  tripping the x-in-y warning and the no-CSV-uploaded info guard, asserting on
  the generated Highcharts config (incl. the brand palette) and the guard
  messages.
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
# can't see into, but the "generated config" expander exposes the Highcharts JS
# literal via st.code — so we assert the controls actually reach the builder.
# Sidebar widgets are addressed by position: selectbox [0] Dataset, [1] Chart
# type, [2] X axis; segmented_control [0] Source, [1] Render mode; pills [0] the
# Y series. Everything here stays on the network-free interactive path (the
# Static PNG render mode would call the live export server).
# --------------------------------------------------------------------------- #
@pytest.fixture
def app():
    """A freshly loaded, run-once AppTest for the Streamlit app."""
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60).run()


def test_app_default_run_emits_highcharts_config(app):
    assert not app.exception
    assert "Highcharts" in app.code[0].value  # the generated config rendered


def test_app_switch_to_pie_regenerates_config(app):
    app.selectbox[1].set_value("pie").run()  # Chart type -> pie
    assert not app.exception
    assert "type: 'pie'" in app.code[0].value


def test_app_custom_title_flows_into_config(app):
    app.text_input(key="chart_title").set_value("My Title").run()
    assert not app.exception
    assert "My Title" in app.code[0].value


def test_app_multiple_series_selected(app):
    # The revenue-vs-cost sample has two numeric columns; select both via pills.
    app.pills[0].set_value(["revenue", "cost"]).run()
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


def test_app_generated_config_includes_brand_palette(app):
    # The brand palette reaches the iframe/PNG paths through build_options; the
    # generated-config expander is the visible proof in the default run.
    assert DEFAULT_COLORS[0] in app.code[0].value
