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
  sharing bubble's and radar's ``highcharts-more``), waterfall's cumulative bridge
  (signed deltas floating at a running total, closed by an APPENDED ``isSum`` bar —
  so it is the one type drawing more marks than the frame has rows, and the one
  whose ``count_marks`` exceeds its drawable row count; the bar colors are semantic
  rather than identity-based, read from ``DEFAULT_COLORS`` by index so a custom
  ``colors`` palette cannot repaint a fall green, and the total carries its own
  per-point color, which takes it OFF that up/down scale — Highcharts would otherwise
  color the sum by its own sign, and "the end level is above zero" is not the claim
  "this step added"; a missing delta keeps its axis slot as an ``EnforcedNull``; the
  in-bar value labels are gated on step count; and it needs TWO dark-mode hooks — the
  bar borders and the connector lines between bars, neither of which is column/bar's
  white-ring case — while sharing that same ``highcharts-more``), sunburst's hierarchy
  of rings (the only type reading the frame as an ADJACENCY LIST — one row per node,
  naming its parent by LABEL — so its marks must be ASSEMBLED before anything can be
  drawn. Node ids are SYNTHESIZED, never the labels: two teams may legitimately both be
  called "Other", and label-as-id would hand Highcharts a duplicate id, which is not a
  silent mismatch but error #31 printed in a red band across the chart — so the twins stay
  two honest sectors, and the label-keyed shape's one real cost is paid only where it is
  genuinely unpayable, on a duplicate label that is USED as a parent. The tree's two kinds
  of fault are kept apart: MISSING DATA is dropped (a dangling parent, with its descendants
  — Highcharts would otherwise silently re-parent an orphan to the root; an unsizable leaf
  value, ``_sizable`` widening ``_plottable`` by one comparison because a NEGATIVE leaf is
  not merely undrawn but excluded from its parent's sum), while a CONTRADICTION RAISES (a
  cycle, an ambiguous parent) — through a message ``_sunburst_tree`` RETURNS rather than
  throws, which is what keeps ``count_marks`` total and the app's KPI row, which runs above
  its guards, from blowing the page up with a traceback. Internal nodes carry NO value, so
  Highcharts' sum is authoritative and a parent's arc always equals what is drawn under it;
  a root sector is APPENDED, making sunburst the second type whose mark count exceeds its row
  count; ring 1 is seeded per POINT from the palette, routing around ``levels[].colorByPoint``,
  which highcharts-core silently drops, and around the series-level ``colorByPoint``, which
  survives but would destroy the hue inheritance; and it needs ONE dark-mode hook, the white
  sector rings that pie, treemap and sankey each dissolve — resolving its own
  ``modules/sunburst.js`` and, unlike bubble/radar/boxplot/waterfall, no ``highcharts-more``),
  the brand-palette
  (``DEFAULT_COLORS`` / ``colors`` override), and the validation guards
  (unsupported type, empty ``y_cols``, the category-x x-in-y rule widened to
  heatmap, boxplot and waterfall, the bubble size-column requirement, sankey's
  required, distinct target column, and sunburst's required, distinct parent column).
- light/dark theming: dark mode paints the chart background (light leaves it
  unset), the chart chrome (axes/text/gridlines, pie labels, and the tooltip)
  flips while the ``DEFAULT_COLORS`` palette stays shared across modes,
  ``build_chart_html`` gives the iframe body a background that tracks the mode,
  and it pins the chart's ``color-scheme`` so Highcharts' own ``light-dark()``
  defaults resolve to the export server's values rather than the viewer's browser.
- a row-less frame (columns, no rows — a header-only CSV) draws an EMPTY chart
  rather than raising, swept over ``SUPPORTED_TYPES`` because the bug was one
  shared line: an empty ``.map()`` mask comes back non-boolean, and a DataFrame
  indexed by one is read as a list of COLUMN NAMES, so every type died with a bare
  ``KeyError``. ``count_marks`` had the same bug in each of its three masks, where
  it surfaces instead as ``int('')`` and as an Arrow ``&`` kernel error — and, for
  the non-label masks, only as a pandas deprecation, so that test promotes warnings
  to errors to see it at all.
- ``sample_data`` unit tests: every built-in dataset is plottable (fresh,
  non-empty, with a numeric column).
- Headless ``AppTest`` interaction tests that drive the full Streamlit app's
  control flow — switching chart type (including bubble, which reveals a
  Size (Z) control, radar, heatmap, treemap, sankey, which reveals a
  Target (to) control, sunburst, which reveals a Parent one, and boxplot and waterfall,
  which reveal a single-select Y
  and no extra control at all — waterfall also asserting that its Steps KPI counts
  the appended total, and sunburst that its Sectors KPI counts the appended root, and
  that a CYCLIC uploaded CSV — the one builder error a user can reach by uploading a
  file, since the interactive path does not catch — warns and stops rather than
  rendering a traceback), title, and series, revealing
  the generated Highcharts config
  behind its toggle, the KPI metric row, the wide-CSV multiselect fallback, and
  the render-mode selector's two modes (interactive iframe / static PNG), plus
  tripping the x-in-y warning and the no-CSV-uploaded info guard — asserting on
  the generated config (incl. the brand palette) and the guard messages.
"""

import math
import sys
import warnings
from datetime import date
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
    GAUGE_AGGREGATIONS,
    GAUGE_TYPES,
    NETWORKGRAPH_TYPES,
    NODE_LINK_TYPES,
    SUPPORTED_TYPES,
    _gauge_reading_label,
    _needle_radii,
    _pct,
    build_chart_html,
    build_options,
    count_marks,
    explain_gauge_error,
    explain_xrange_error,
    gauge_dial,
    make_chart,
)


@pytest.fixture
def labeled_frame() -> pd.DataFrame:
    """A label column plus a numeric column — valid input for every chart type.

    The second label column ("target") is there for sankey alone, whose links need a
    node column at each end, and the third ("parent") for sunburst alone, whose rows are
    an adjacency list. Every other type names the columns it reads, so the extras are
    inert (neither is numeric, so neither can perturb a y-column sweep).

    "parent" is a real 2-level tree — "a" is a top-level branch (its blank parent says so)
    and "b"/"c" hang off it — so the sweeps exercise sunburst's internal-node path as well
    as its leaves. Note the consequence for the value sweeps: "a" has children, so its
    value is never read at all (an internal node's arc is the sum of its children's).

    The fourth column ("end") is for xrange alone, whose bars need a coordinate at each end.
    It is the one extra that IS numeric, so — unlike "target"/"parent" — it is not inert:
    it is a second numeric column, and "value" is no longer the only one. Every sweep names
    the columns it reads, so nothing is perturbed, but a new test that reaches for "the
    numeric column" must now say which. Its values sit strictly above "value"'s, so for
    xrange every row is spannable (``value`` is the START and ``end`` the END).
    """
    return pd.DataFrame(
        {
            "label": ["a", "b", "c"],
            "target": ["x", "y", "z"],
            "parent": [None, "a", "a"],
            "value": [1.0, 2.0, 3.0],
            "end": [2.0, 4.0, 6.0],
        }
    )


def _size_for(chart_type: str) -> str | None:
    """The size column the SUPPORTED_TYPES-parametrized tests pass for the bubble
    case: bubble requires one (its marker-size dimension); other types ignore it,
    so it's None. The shared ``labeled_frame``'s "value" doubles as the size (it is not
    the only numeric column any more — "end" is one too — but it is the one every sweep
    plots)."""
    return "value" if chart_type == "bubble" else None


def _target_for(chart_type: str) -> str | None:
    """The target column those same sweeps pass for the node-link cases: sankey,
    dependencywheel and networkgraph all require one (the far end of every edge, reusing one
    ``target_col``); other
    types ignore it, so it's None. The
    ``_size_for`` idea, for the other types with a required companion column — the
    sweeps assert invariants that must hold for *every* type (it builds, it carries
    the palette, dark mode paints the background), so a type that needs an extra
    column adapts its input rather than dropping out. Networkgraph is built by the sweeps with
    the shared ``y_cols=["value"]``, which it simply IGNORES (it has no value channel); its own
    empty-``y_cols`` behaviour is pinned separately (``test_networkgraph_builds_with_empty_y_cols``)."""
    return "target" if chart_type in NODE_LINK_TYPES else None


def _parent_for(chart_type: str) -> str | None:
    """The parent column those same sweeps pass for the sunburst case: sunburst requires
    one (each node's place in the hierarchy); other types ignore it, so it's None. The
    third of the ``_size_for``/``_target_for`` family — see ``_target_for`` for why a type
    with a required companion column adapts its input rather than dropping out of the
    sweeps."""
    return "parent" if chart_type == "sunburst" else None


def _end_for(chart_type: str) -> str | None:
    """The end column those same sweeps pass for the xrange case: xrange requires one (the
    far end of every bar); other types ignore it, so it's None. The fourth of the
    ``_size_for``/``_target_for``/``_parent_for`` family — see ``_target_for``.

    Note what xrange does with the sweeps' ``y_cols=["value"]``: it reads it as the bar's
    START, not as a magnitude. So the pair is ("value", "end"), and the fixtures keep "end"
    strictly above "value" so the bars are drawable."""
    return "end" if chart_type == "xrange" else None


def _high_for(chart_type: str) -> str | None:
    """The high column those same sweeps pass for the columnrange case: columnrange requires
    one (each bar's top); other types ignore it, so it's None. The fifth of the
    ``_size_for``/``_target_for``/``_parent_for``/``_end_for`` family — see ``_target_for``.

    It reuses the fixtures' ``"end"`` column, the one extra that is NUMERIC, exactly as
    ``_end_for`` does — but reading it as a MAGNITUDE (the bar's high), not a coordinate. The
    pair is ("value", "end") as it is for xrange, and for the same reason the fixtures keep
    "end" strictly above "value": here that makes every range a clean ``low < high`` rather than
    an inverted one, so the sweeps exercise the ordinary drawable case."""
    return "end" if chart_type == "columnrange" else None


# Radar remains the ONE "meta" type: Highcharts has no radar series, so it renders as a polar
# *line* chart and its chart.type serializes as "line". Every other supported type's chart.type
# equals its own name — and the gauge FAMILY is why that stayed true. `solidgauge` was never
# given the friendlier name `gauge` that radar's precedent would have licensed, because `gauge`
# in Highcharts is a DIFFERENT chart, a needle on a dial. That name is now SPENT, on exactly the
# type it was being held for, so both gauges are called what Highcharts calls them and this map
# still has one entry.
_HC_TYPE = {"radar": "line"}


def _hc_type(chart_type: str) -> str:
    """The Highcharts ``chart.type`` a supported type renders as: identity for all but
    radar, which is a polar line."""
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
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
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
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
    ).to_js_literal()
    assert js and f"type: '{_hc_type(chart_type)}'" in js


@pytest.fixture
def non_finite_frame() -> pd.DataFrame:
    """``labeled_frame``'s shape, but the numeric column carries an infinity at each end
    and one drawable value. Every type reads x from "label" and y from "value", so the
    one frame exercises all of them (bubble takes "value" as its size too, sankey as its
    weight — see ``_size_for``/``_target_for``/``_parent_for``).

    For sunburst the tree is "a" over "b"/"c", so the frame reaches its branch three ways at
    once: "a" is INTERNAL, so its ``inf`` is never even read (a parent's arc is the sum of its
    children's); "b"'s ``-inf`` fails ``_sizable`` and drops that leaf; and "c" survives. No
    infinity can reach the JS by any of the three routes.

    For xrange "value" is each bar's START, so the two infinities fail ``_spannable`` and drop
    their rows while "c" (9 -> 10) survives and draws. "end" is kept FINITE here on purpose:
    it is the one channel this fixture cannot reach, since an infinite end would drop the only
    surviving row and leave an empty chart that passes the sweep trivially. It is covered
    directly instead — see ``test_xrange_drops_a_non_finite_start_or_end``."""
    return pd.DataFrame(
        {
            "label": ["a", "b", "c"],
            "target": ["x", "y", "z"],
            "parent": [None, "a", "a"],
            "value": [float("inf"), float("-inf"), 9.0],
            "end": [2.0, 4.0, 10.0],
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
    # sweeps SUPPORTED_TYPES so a newly added type is covered the day it is added — but only
    # for its VALUE channel (this fixture carries the infinities in the y/weight/size
    # column, always with a safe string x). The LABEL channel has its own sweep
    # (test_missing_or_non_finite_label_drops_the_row_in_every_type), and boxplot's
    # aggregation-overflow path — the one type that can manufacture a non-finite from
    # finite inputs — has its own test, since neither is reachable through this frame.
    from highcharts_builder import make_chart

    js = make_chart(
        non_finite_frame,
        chart_type,
        "label",
        ["value"],
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
    ).to_js_literal()
    assert js
    # `Infinity` is capitalized, so a lowercase "inf" can only be the broken token. None
    # of the column names, titles or type names above contains "inf"/"nan" either.
    for token in ("inf", "nan", "NaN"):
        assert token not in js, f"{chart_type} emitted a non-finite literal: {token}"


# Gauge is EXCLUDED, and vacuously passing here is exactly why it has to be. It has no label
# channel — `x_col` names nothing — so there is no policy for this sweep to test, and with a
# clean value column the assertion below ("no nan/inf token in the JS") would hold whatever
# gauge did with the labels. Worse than untested: it would READ as a pin on a policy gauge
# deliberately does not have, since a row filter over an AGGREGATE does not drop a mark, it
# silently changes a NUMBER. What gauge actually promises is the opposite, and it is pinned
# where it belongs: test_gauge_ignores_x_col_entirely.
@pytest.mark.parametrize(
    "chart_type", [t for t in SUPPORTED_TYPES if t not in GAUGE_TYPES]
)
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
            # sunburst's second label column: "a" is a top-level branch and "c" hangs off it,
            # so the undrawable middle row is the only one dropped.
            "parent": [None, "a", "a"],
            "value": [1.0, 2.0, 3.0],
            # xrange's second coordinate column, above "value" so every row is spannable —
            # leaving the LABEL the only reason a row can drop, which is what this sweep tests.
            "end": [2.0, 4.0, 6.0],
        }
    )
    inf_df = pd.DataFrame(
        {
            "label": [1.0, float("inf"), 3.0],
            "to": [9.0, 8.0, 7.0],
            # A NUMERIC parent column, matched against a numeric label column — so this row
            # also exercises `_node_key`: a bare str() would stringify the label 1.0 to "1"
            # (int64-backed) but the parent 1.0 to "1.0", dangle every row, and quietly empty
            # the chart. Here they must meet.
            "parent": [float("nan"), 1.0, 1.0],
            "value": [1.0, 2.0, 3.0],
            "end": [2.0, 4.0, 6.0],
        }
    )
    for df, token in ((nan_df, "nan"), (inf_df, "inf")):
        js = make_chart(
            df,
            chart_type,
            "label",
            ["value"],
            size_col=_size_for(chart_type),
            target_col="to" if chart_type in NODE_LINK_TYPES else None,
            parent_col="parent" if chart_type == "sunburst" else None,
            end_col=_end_for(chart_type),
            high_col=_high_for(chart_type),
        ).to_js_literal()
        assert js and token not in js.lower(), f"{chart_type} kept a '{token}' label"


@pytest.mark.parametrize("chart_type", SUPPORTED_TYPES)
def test_row_less_frame_draws_an_empty_chart_in_every_type(chart_type):
    # A frame with columns but NO ROWS is a legitimate input — a CSV with a header and no
    # data rows parses to exactly this — and it should draw an EMPTY chart, not raise.
    #
    # It used to raise, in all of them, from a single line: the shared `_label_ok` filter
    # `df[df[x_col].map(_label_ok)]`. `.map()` infers its result dtype from the values it
    # produced, and with no rows there are none, so it returns an empty *object* Series
    # instead of an empty *boolean* one — and a DataFrame indexed by a non-boolean Series is
    # not masked at all, it is read as a list of COLUMN NAMES. So the frame lost every
    # column and the next line to touch df[x_col] died with a bare `KeyError: 'label'`. The
    # `.astype(bool)` in that filter is what pins the dtype.
    #
    # Swept over SUPPORTED_TYPES because the filter is shared by all of them: one line, one
    # bug, EVERY type — the count is however many there are, which is exactly why this is a
    # sweep and not a list, so a newly added type is covered the day it is added. Both
    # scatter/bubble paths are reached: the object-dtype x below takes the label path (the
    # filtered one), and the numeric-x frame at the end takes the branch that skips it.
    from highcharts_builder import make_chart

    # "target"/"parent" (not "to") — the names `_target_for`/`_parent_for` hand the sankey and
    # sunburst cases, as in `labeled_frame`.
    empty = pd.DataFrame(
        {
            "label": pd.Series([], dtype=object),
            "target": pd.Series([], dtype=object),
            "parent": pd.Series([], dtype=object),
            "value": pd.Series([], dtype=float),
            # xrange's end column. A row-less coordinate column is the one case `_coordinates`
            # must NOT call a contradiction: nothing parses, but nothing is PRESENT either, so
            # it is missing data (an empty chart), not a column of the wrong kind (a raise).
            "end": pd.Series([], dtype=float),
        }
    )
    opts = build_options(
        empty,
        chart_type,
        "label",
        ["value"],
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
    )
    # An empty chart, not a raise. Gauge is the one type whose empty chart is not zero marks:
    # its marks are the selected COLUMNS, not the rows, so a header-only CSV still selects one
    # — and the ring is KEPT, as a null, exactly as an all-missing column is in a populated
    # frame. (Dropping it would renumber and recolour every other ring, and make the KPI count a
    # ring the chart never drew.) So the row-less case is not a special case for gauge at all:
    # it is the ordinary no-data reading, arrived at with no rows rather than with blank ones.
    expected = [EnforcedNull] if chart_type in GAUGE_TYPES else []
    assert opts["series"][0]["data"] == expected
    # And it must still SERIALIZE — an empty series is only useful if Highcharts gets it.
    js = make_chart(
        empty,
        chart_type,
        "label",
        ["value"],
        size_col=_size_for(chart_type),
        target_col=_target_for(chart_type),
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
    ).to_js_literal()
    assert js and f"type: '{_hc_type(chart_type)}'" in js


@pytest.mark.parametrize(
    "chart_type", ["treemap", "sankey", "dependencywheel", "networkgraph"]
)
def test_count_marks_casts_every_mask_not_just_the_label_one(chart_type):
    # The types that AND their masks together (`label_ok & value_ok`, plus sankey's/
    # networkgraph's `target_ok` — networkgraph ANDs `label_ok & target_ok` with no value mask,
    # since it is unweighted). On a row-less frame each `.map()` returns a non-boolean Series, and
    # once
    # the label mask alone is cast, `bool & str` still evaluates — so a missing cast on the
    # OTHER masks is invisible to an ordinary assertion. It is not harmless: pandas emits a
    # deprecation saying the operation will RAISE in pandas 4 and that the operand must be
    # cast explicitly. So promote warnings to errors — that is the only thing that can see it.
    #
    # The value/target columns are given a STRING dtype on purpose. A y column is numeric in
    # the app (the picker draws from select_dtypes("number")), and `bool & float64` neither
    # warns nor raises; only a non-numeric one — reachable through the pure builder API this
    # module is — puts the string mask on the right-hand side where the deprecation bites.
    from highcharts_builder import count_marks

    empty = pd.DataFrame(
        {
            "cat": pd.Series([], dtype="str"),
            "to": pd.Series([], dtype="str"),
            "v": pd.Series([], dtype="str"),
        }
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any pandas deprecation here fails the test
        assert count_marks(empty, chart_type, "cat", ["v"], target_col="to") == 0


def test_row_less_frame_with_a_numeric_x_also_draws_an_empty_chart():
    # The other side of the `x_is_label` branch: scatter/bubble with a NUMERIC x skip the
    # label filter entirely (x is a coordinate `_plottable` guards per point), so they reach
    # the row-less frame by a different route and must survive it too.
    numeric = pd.DataFrame(
        {"label": pd.Series([], dtype=float), "value": pd.Series([], dtype=float)}
    )
    for chart_type in ("scatter", "bubble"):
        opts = build_options(
            numeric,
            chart_type,
            "label",
            ["value"],
            size_col="value" if chart_type == "bubble" else None,
        )
        assert opts["series"][0]["data"] == []


@pytest.mark.parametrize(
    "chart_type",
    [
        "heatmap",
        "treemap",
        "funnel",
        "pyramid",
        "sankey",
        "dependencywheel",
        "boxplot",
        "waterfall",
        "sunburst",
        "xrange",
    ],
)
def test_count_marks_matches_the_built_series(chart_type):
    # The app's KPI (heatmap Cells / treemap Tiles / funnel|pyramid Stages / sankey Flows /
    # boxplot Boxes / waterfall Steps / sunburst Sectors) comes
    # from count_marks, which must equal the marks build_options actually draws — the whole
    # reason it lives in the builder, beside the drop rules. Cross-check the two on a frame
    # that exercises every drop: a NaN label (dropped in all six), a NaN value (drops a
    # tile/flow, kept as an EnforcedNull cell/box/bar), an inf value (same), and a NaN target
    # (drops a sankey link). If they ever diverge, the KPI is lying about the chart.
    # Waterfall and sunburst are the two types whose count EXCEEDS their surviving rows — each
    # appends a mark the frame never held (a Total bar, a root sector).
    #
    # Sunburst reads the same frame as a HIERARCHY, and the one column of parents makes it
    # exercise five drops at once: the NaN label drops row 2; "b"'s NaN value drops that LEAF;
    # "a" is thereby left childless, BECOMES a leaf, and is sized by its own 1.0; "d"'s `inf`
    # is harmlessly never read, because "e" keeps it INTERNAL (a parent's arc is the sum of its
    # children's); and the root is appended. 3 nodes + root = 4.
    from highcharts_builder import build_options, count_marks

    # Xrange reads the same frame as INTERVALS, "v" being each bar's START rather than a
    # magnitude, and it exercises three drops at once: the NaN label drops row 3, "b"'s NaN
    # start drops row 2, and "d"'s `inf` start drops row 4 — leaving "a" (1 -> 2) and "e"
    # (5 -> 6). Unlike waterfall and sunburst it appends nothing, so its count is exactly its
    # surviving rows: 2.
    nan, inf = float("nan"), float("inf")
    df = pd.DataFrame(
        {
            "cat": ["a", "b", nan, "d", "e"],
            "to": ["p", "q", "r", "s", nan],
            "parent": [nan, "a", nan, nan, "d"],
            "v": [1.0, nan, 3.0, inf, 5.0],
            "end": [2.0, 4.0, 6.0, 8.0, 6.0],
        }
    )
    built = build_options(
        df,
        chart_type,
        "cat",
        ["v"],
        target_col="to",
        parent_col="parent",
        end_col="end",
    )
    drawn = len(built["series"][0]["data"])  # the cells/tiles/links/boxes/bars/sectors
    assert (
        count_marks(
            df,
            chart_type,
            "cat",
            ["v"],
            target_col="to",
            parent_col="parent",
            end_col="end",
        )
        == drawn
    )
    # The two must also agree on a ROW-LESS frame (a header-only CSV), where the chart is
    # empty — so the KPI reads 0 rather than counting marks nobody drew. This is the case
    # that used to make build_options raise outright (see the row-less sweep above), so the
    # KPI half was never even reachable to be wrong.
    empty = df.iloc[:0]
    assert (
        build_options(
            empty,
            chart_type,
            "cat",
            ["v"],
            target_col="to",
            parent_col="parent",
            end_col="end",
        )["series"][0]["data"]
        == []
    )
    assert (
        count_marks(
            empty,
            chart_type,
            "cat",
            ["v"],
            target_col="to",
            parent_col="parent",
            end_col="end",
        )
        == 0
    )
    # And the expected value, spelled out, so the cross-check can't pass on a shared bug:
    assert (
        drawn
        == {
            "heatmap": 4,
            "treemap": 2,
            # Funnel/pyramid drop the NaN label (row 3) and the NaN/inf value (rows 2, 4)
            # like treemap, leaving "a" (1.0) and "e" (5.0): 2 stages, no appended mark.
            "funnel": 2,
            "pyramid": 2,
            "sankey": 1,
            # Dependencywheel shares sankey's rule and build exactly — same 4 rows dropped
            # (the NaN weight, NaN source, inf weight and NaN target), leaving one link.
            "dependencywheel": 1,
            "boxplot": 4,
            "waterfall": 5,
            "sunburst": 4,
            "xrange": 2,
        }[chart_type]
    )


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


@pytest.mark.parametrize("chart_type", ["pie", "treemap", "funnel", "pyramid"])
def test_single_value_types_drop_a_non_finite_row(chart_type):
    # The drop-the-row family drops an infinity exactly as it drops a NaN: a slice, tile or
    # funnel stage can no more be sized by infinity than by nothing.
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
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
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
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
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
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
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
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
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
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
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
        parent_col=_parent_for(chart_type),
        end_col=_end_for(chart_type),
        high_col=_high_for(chart_type),
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
    # The selector must be `.highcharts-root` (the <svg>), not `html`: Highcharts declares
    # `color-scheme: light dark` on `.highcharts-container` (between `html` and the <svg>),
    # and since `color-scheme` inherits, that shadows an `html` rule for the SVG subtree —
    # so the pin has to sit at or below the container to win.
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


@pytest.mark.parametrize(
    "chart_type", [t for t in SUPPORTED_TYPES if t not in NETWORKGRAPH_TYPES]
)
def test_rejects_empty_y_cols(chart_type):
    # Every type needs at least one y column — EXCEPT networkgraph, the one type with no value
    # channel (its marks are the edges between two node columns). It is excluded here and pinned
    # the other way by `test_networkgraph_builds_with_empty_y_cols`: the exclusion is the mirror
    # of the gauge family's exclusion from the label sweep — a positive assertion of the missing
    # channel, not an oversight.
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


# --------------------------------------------------------------------------- #
# Funnel / pyramid (part-of-whole stages — pie's single-value cousins)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("chart_type", ["funnel", "pyramid"])
def test_funnel_family_builds_leaves_and_skips_missing(chart_type):
    # Funnel/pyramid share pie's single-value shape (a label column + one value column)
    # AND pie's leaf key: FunnelSeries is FunnelOptions(PieOptions), so leaves are keyed
    # "y" (NOT treemap's "value"). Like pie, a NaN- or inf-valued row is DROPPED (a stage
    # can't be sized without a value) — not the category-x keep-a-slot EnforcedNull family.
    df = pd.DataFrame({"stage": ["A", "B", "C"], "v": [10.0, float("nan"), 30.0]})
    opts = build_options(df, chart_type, "stage", ["v"])
    # chart.type is the CONCRETE type name for both — pyramid is its own series type, not a
    # funnel with reversed=True, so nothing here says "funnel" for a pyramid.
    assert opts["chart"]["type"] == chart_type
    assert opts["series"][0]["name"] == "v"
    assert opts["series"][0]["data"] == [
        {"name": "A", "y": 10.0},
        {"name": "C", "y": 30.0},
    ]
    # Palette-hued per stage from the shared colors, NOT a colorAxis (like pie, unlike heatmap).
    assert opts["colors"] == list(DEFAULT_COLORS)
    assert "colorAxis" not in opts


@pytest.mark.parametrize("chart_type", ["funnel", "pyramid"])
def test_funnel_family_uses_only_first_y_col(chart_type):
    # Single-value like pie: only the first selected column sizes the stages.
    df = pd.DataFrame({"stage": ["A", "B"], "v": [1.0, 2.0], "v2": [9.0, 9.0]})
    opts = build_options(df, chart_type, "stage", ["v", "v2"])
    assert opts["series"][0]["name"] == "v"
    assert [pt["y"] for pt in opts["series"][0]["data"]] == [1.0, 2.0]


@pytest.mark.parametrize("chart_type", ["funnel", "pyramid"])
def test_funnel_family_draws_stages_in_row_order(chart_type):
    # A stage's row order IS load-bearing (unlike pie's cosmetic slice order), and Highcharts does
    # NOT auto-sort. The builder is deliberately permissive — it emits stages in the order the rows
    # arrive, re-sorting nothing — so an out-of-order input is kept as given (columnrange's
    # kept-inverted-range permissiveness, one family over). This pins that no sort creeps into the
    # emitted DATA ARRAY; which end of the shape row 0 lands on is Highcharts' call and differs by
    # type (a funnel draws row 0 at the top, a pyramid at the base), so it is not asserted here.
    df = pd.DataFrame(
        {"stage": ["A", "B", "C"], "v": [10.0, 90.0, 40.0]}
    )  # non-monotonic
    data = build_options(df, chart_type, "stage", ["v"])["series"][0]["data"]
    assert [pt["name"] for pt in data] == ["A", "B", "C"]
    assert [pt["y"] for pt in data] == [10.0, 90.0, 40.0]


@pytest.mark.parametrize("chart_type", ["funnel", "pyramid"])
def test_funnel_family_dark_mode_themes_labels_and_border(chart_type):
    # Pie's TWO dark-mode flips, not treemap's one — because a funnel's data labels sit OUTSIDE
    # the shape on the chart background (its default placement), so they take the light TEXT
    # color; and the segment borders default to the white background var, so they are dissolved
    # into the dark background (borderColor). Keyed by the concrete chart.type, so pyramid themes
    # through its own plotOptions key.
    df = pd.DataFrame({"stage": ["A", "B"], "v": [1.0, 2.0]})
    opts = build_options(df, chart_type, "stage", ["v"], dark=True)
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    po = opts["plotOptions"][chart_type]
    assert (
        po["dataLabels"]["color"] == "#e2e8f0"
    )  # light text, unlike treemap's "contrast"
    assert po["borderColor"] == "#0f172a"  # segment gaps match the dark background
    # No axes, so the axis-theming loop must simply skip it (not crash).
    assert "xAxis" not in opts


@pytest.mark.parametrize("chart_type", ["funnel", "pyramid"])
def test_funnel_family_serializes_and_pulls_in_the_funnel_module(chart_type):
    # End to end: the {name, y} leaf shape must serialize (values reach the JS) AND resolve
    # modules/funnel.js — shared by funnel and pyramid, and NOT highcharts-more (the plausible
    # guess the round-trip corrects, as it does for bubble/boxplot vs treemap/sunburst/xrange).
    from highcharts_builder import make_chart

    df = pd.DataFrame({"stage": ["A", "B", "C"], "v": [10.0, 20.0, 30.0]})
    chart = make_chart(df, chart_type, "stage", ["v"])
    js = chart.to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and f"type: '{chart_type}'" in js
    # The leaf VALUE must survive the Chart.from_options round-trip into the JS — the treemap
    # `value`-vs-`y` silent-drop trap, one type over. highcharts-core collapses each {name, y}
    # leaf into a `[name, value]` 2-array, so pin the name-to-value PAIR (a dropped value would
    # leave `['A']` with no number) rather than a bare "10", which could match elsewhere.
    flat = "".join(js.split())  # the pairs span newlines: ['A',\n10.0] -> ['A',10.0]
    assert "['A',10.0]" in flat
    assert "['B',20.0]" in flat
    assert "['C',30.0]" in flat
    tags = chart.get_script_tags(as_str=True)
    assert "modules/funnel.js" in tags
    assert "highcharts-more" not in tags  # funnel's own module, not bubble/radar's


@pytest.mark.parametrize("chart_type", ["funnel", "pyramid"])
def test_funnel_family_light_mode_shape(chart_type):
    # Pin the otherwise-unguarded funnel/pyramid choices — parametrized over BOTH, since they
    # share one branch and these strings must be byte-identical between them: the value+share
    # tooltip (headerFormat blanked; the percentage is a funnel point's share of the STAGE TOTAL —
    # pie semantics, inherited — labelled "of total" so it isn't misread as a conversion rate),
    # the outside-the-shape name+value data labels, and the ABSENCE of an explicit colorByPoint
    # key (funnel inherits colorByPoint: true from pie's JS default, and highcharts-core cannot
    # express the key at all — so the builder must set nothing, unlike treemap which sets it).
    df = pd.DataFrame({"stage": ["A", "B"], "v": [3.0, 1.0]})
    opts = build_options(df, chart_type, "stage", ["v"])
    assert opts["tooltip"]["headerFormat"] == ""
    assert opts["tooltip"]["pointFormat"] == (
        "{point.name}: <b>{point.y}</b> ({point.percentage:.1f}% of total)"
    )
    plot = opts["plotOptions"][chart_type]
    assert plot["dataLabels"]["enabled"] is True
    assert plot["dataLabels"]["format"] == "{point.name}: {point.y}"
    assert "colorByPoint" not in plot  # inherited from pie's default, never set here
    # Light mode injects no dark chrome onto the tooltip (a no-op, as elsewhere).
    assert "backgroundColor" not in opts["tooltip"]


def test_pyramid_is_its_own_series_type_not_a_reversed_funnel():
    # Pyramid is modeled as the real PyramidSeries (chart.type "pyramid"), which draws inverted
    # by default — NOT a funnel with reversed=True + a zeroed neck. So the emitted options carry
    # NO `reversed` key and the type is literally "pyramid", keeping this module's "every type
    # serializes as its own Highcharts name" rule intact (radar is the sole exception).
    df = pd.DataFrame({"tier": ["A", "B", "C"], "v": [1.0, 2.0, 3.0]})
    opts = build_options(df, "pyramid", "tier", ["v"])
    assert opts["chart"]["type"] == "pyramid"
    assert "reversed" not in opts["plotOptions"]["pyramid"]
    assert "neckWidth" not in opts["plotOptions"]["pyramid"]


@pytest.mark.parametrize("chart_type", ["pie", "treemap", "funnel", "pyramid"])
def test_single_value_numeric_labels_coerce_to_strings(chart_type):
    # The single-value point-name types (pie, treemap, funnel, pyramid) build leaves as
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
# Dependencywheel (a circular sankey: weighted links around a ring) — SHARES
# sankey's build branch, keyed by chart_type. So the {from, to, weight} links, the
# drop policy, the per-link weight labels and the node/link tooltips are the ones the
# sankey block above already pins; these tests pin only what is DISTINCT: the
# chart.type / plotOptions key the branch parametrizes, and the TWO modules the wheel
# resolves (modules/dependency-wheel PLUS modules/sankey) where sankey pulls one. In
# highcharts-core, DependencyWheelSeries is literally SankeySeries' parent class.
# --------------------------------------------------------------------------- #
def test_dependencywheel_builds_weighted_links_like_sankey():
    # The shared branch must emit chart.type 'dependencywheel' (not 'sankey') while
    # producing the identical {from, to, weight} links — a row missing any of the three is
    # dropped exactly as sankey's is (an invisible zero-width link otherwise). No colorAxis
    # and no axes: a wheel colors its ribbons categorically from the palette (like pie /
    # treemap / sankey) and, being a diagram, has no axes to draw.
    df = pd.DataFrame(
        {
            "src": ["Coal", "Gas", "Wind"],
            "dst": ["Power", "Power", "Power"],
            "w": [42.0, float("nan"), 26.0],
        }
    )
    opts = build_options(df, "dependencywheel", "src", ["w"], target_col="dst")
    assert opts["chart"]["type"] == "dependencywheel"
    assert opts["series"][0]["name"] == "w"
    assert _links(opts) == [
        {"from": "Coal", "to": "Power", "weight": 42.0},
        {"from": "Wind", "to": "Power", "weight": 26.0},
    ]
    # A wheel prints NO per-link weight label — the ONE place it diverges from sankey beyond the
    # type string, found by rendering: on the ring Highcharts stacks link labels in a clipped
    # column off the left. The node NAMES still render, via the series-level dataLabels.
    assert all("dataLabels" not in link for link in opts["series"][0]["data"])
    assert opts["plotOptions"]["dependencywheel"]["dataLabels"] == {"enabled": True}
    assert opts["colors"] == list(DEFAULT_COLORS)
    assert "colorAxis" not in opts
    assert "xAxis" not in opts and "yAxis" not in opts


def test_dependencywheel_plot_options_land_under_its_own_key():
    # The one place the shared branch diverges from sankey: `chart.type` and the
    # `plotOptions` key must key on 'dependencywheel', not 'sankey' — a copy-paste leaving
    # them under 'sankey' would emit a block Highcharts ignores. The node tooltip (throughput
    # of a hovered node) rides plotOptions[type].tooltip.nodeFormat, and — as with sankey — a
    # TOP-LEVEL tooltip.nodeFormat is silently dropped, so it must live here; only the emitted
    # JS proves it survived (verified on the round-trip that the wheel's nodeFormat does).
    from highcharts_builder import make_chart

    df = pd.DataFrame({"src": ["A"], "dst": ["B"], "w": [1.0]})
    opts = build_options(df, "dependencywheel", "src", ["w"], target_col="dst")
    assert "sankey" not in opts["plotOptions"]  # not left under the wrong key
    assert "nodeFormat" not in opts["tooltip"]  # would vanish if it were here
    assert (
        opts["plotOptions"]["dependencywheel"]["tooltip"]["nodeFormat"]
        == "{point.name}: <b>{point.sum}</b>"
    )
    js = make_chart(
        df, "dependencywheel", "src", ["w"], target_col="dst"
    ).to_js_literal()
    assert js and "nodeFormat" in js and "point.sum" in js


def test_dependencywheel_serializes_and_pulls_in_both_modules():
    # End to end, and the type's headline serialization fact: a dependencywheel resolves
    # modules/dependency-wheel.js AND modules/sankey.js — BOTH, from chart.type alone (the
    # wheel builds on sankey's diagram infrastructure) — and NOT highcharts-more (the
    # plausible guess the round-trip corrects, as it does for columnrange/funnel). The link
    # keys and the per-link weight label must reach the JS too, since highcharts-core silently
    # discards any key its typed point model doesn't recognize.
    from highcharts_builder import make_chart

    df = pd.DataFrame({"src": ["A", "B"], "dst": ["C", "C"], "w": [1.0, 2.0]})
    chart = make_chart(df, "dependencywheel", "src", ["w"], target_col="dst")
    js = chart.to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and "type: 'dependencywheel'" in js
    assert "from: 'A'" in js and "to: 'C'" in js and "weight: 1.0" in js
    # No per-link weight label on a wheel (they misplace on the ring), unlike sankey's JS.
    assert "format: '{point.weight}'" not in js
    tags = chart.get_script_tags(as_str=True)
    assert "modules/dependency-wheel.js" in tags
    assert "modules/sankey.js" in tags  # the wheel builds on sankey's module
    assert "highcharts-more" not in tags  # the round-trip corrects the plausible guess


def test_dependencywheel_html_loads_sankey_before_dependency_wheel():
    # THE interactive-mode regression pin. modules/dependency-wheel.js EXTENDS the sankey series,
    # so it must load AFTER modules/sankey.js — but highcharts-core's get_script_tags emits them
    # REVERSED (it walks the chart's plotOptions before its series, so the dependent module is
    # seen first). Loaded first, dependency-wheel.js throws "Cannot read properties of undefined
    # (reading 'prototype')" and Highcharts reports the series missing (error #17), leaving a BLANK
    # iframe while the export-server PNG renders fine — the two-render-modes-must-agree bug that
    # build_chart_html fixes via _order_script_tags. So pin the ORDER in the emitted HTML, not just
    # the presence the test above covers: sankey's tag must precede the wheel's. Verified by
    # rendering in a real browser (the console showed error #17 before the fix, nothing after).
    from highcharts_builder import build_chart_html

    df = pd.DataFrame({"src": ["A", "B"], "dst": ["C", "C"], "w": [1.0, 2.0]})
    html = build_chart_html(df, "dependencywheel", "src", ["w"], target_col="dst")
    assert "modules/sankey.js" in html and "modules/dependency-wheel.js" in html
    assert html.index("modules/sankey.js") < html.index("modules/dependency-wheel.js")


def test_order_script_tags_puts_a_prerequisite_before_its_dependent():
    # The pure reorder behind the fix above. Given the dependent's tag AHEAD of its prerequisite's
    # (get_script_tags' actual output for a dependencywheel), it moves the prerequisite in front;
    # it is a no-op when the pair is absent or already ordered, so it can't disturb a plain sankey
    # (no dependency-wheel tag) or any other type, and it is idempotent.
    from highcharts_builder import _order_script_tags

    reversed_tags = (
        '<script src="x/highcharts.js"></script>\n'
        '<script src="x/modules/dependency-wheel.js"></script>\n'
        '<script src="x/modules/sankey.js"></script>'
    )
    out = _order_script_tags(reversed_tags).split("\n")
    assert out[0].endswith('highcharts.js"></script>')  # untouched
    assert "modules/sankey.js" in out[1]  # prerequisite moved ahead of the dependent
    assert "modules/dependency-wheel.js" in out[2]

    # Idempotent on already-ordered input, and a no-op on a lone sankey tag (no dependent present).
    assert _order_script_tags("\n".join(out)) == "\n".join(out)
    lone_sankey = '<script src="x/modules/sankey.js"></script>'
    assert _order_script_tags(lone_sankey) == lone_sankey


def test_order_script_tags_raises_when_a_dependent_lacks_its_prerequisite():
    # A dependent module present WITHOUT its prerequisite can't be saved by reordering — the chart
    # pulled a module that extends one it did not, so the interactive iframe would blank. Raise
    # loudly instead of silently no-opping (which is how a renamed module or a drifted tag format
    # would otherwise re-introduce the very blank-iframe bug this helper exists to prevent).
    from highcharts_builder import _order_script_tags

    orphaned = (
        '<script src="x/highcharts.js"></script>\n'
        '<script src="x/modules/dependency-wheel.js"></script>'  # no modules/sankey.js
    )
    with pytest.raises(ValueError, match="prerequisite"):
        _order_script_tags(orphaned)


def test_dependencywheel_requires_a_target_column():
    # A wheel without its target column has only one end per link — mandatory, a ValueError,
    # exactly as sankey's is (both bind the shared NODE_LINK_TYPES guard).
    df = pd.DataFrame({"src": ["A"], "dst": ["B"], "w": [1.0]})
    with pytest.raises(ValueError):
        build_options(df, "dependencywheel", "src", ["w"])  # no target_col


def test_dependencywheel_rejects_source_as_target():
    # One column can't name both ends of a link — every row a self-loop. The shared
    # node-link guard, not the category-x x-in-y rule (target_col is never among y_cols).
    df = pd.DataFrame({"src": ["A"], "w": [1.0]})
    with pytest.raises(ValueError):
        build_options(df, "dependencywheel", "src", ["w"], target_col="src")


def test_dependencywheel_light_mode_shape():
    # Pin the light-mode choices nothing else guards: the link tooltip naming both ends and
    # the disabled legend (each node is labelled on the ring, so a legend would only repeat
    # them). Light mode injects no dark chrome, and the border hook must NOT fire (dark-only).
    df = pd.DataFrame({"src": ["A"], "dst": ["B"], "w": [1.0]})
    opts = build_options(df, "dependencywheel", "src", ["w"], target_col="dst")
    assert opts["legend"]["enabled"] is False
    assert opts["tooltip"]["headerFormat"] == ""
    assert opts["tooltip"]["pointFormat"] == "src → dst: <b>{point.weight}</b>"
    # The border hook is dark-only, so light mode leaves no borderColor. (Key-correctness — that
    # the block lands under 'dependencywheel', not a stale 'sankey' — is pinned explicitly by
    # test_dependencywheel_plot_options_land_under_its_own_key, so it is not re-asserted here.)
    assert "borderColor" not in opts["plotOptions"]["dependencywheel"]


def test_dependencywheel_dark_mode_dissolves_borders_under_its_own_key():
    # The border hook is keyed on the type, so in dark mode it must dissolve the border under
    # plotOptions.dependencywheel (not a stale 'sankey' key), exactly as sankey's does under
    # its own. The node/link labels ride Highcharts' `contrast` default (no color set), and
    # the tooltip box is themed for dark mode.
    df = pd.DataFrame({"src": ["A"], "dst": ["B"], "w": [1.0]})
    opts = build_options(
        df, "dependencywheel", "src", ["w"], target_col="dst", dark=True
    )
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    assert opts["plotOptions"]["dependencywheel"]["borderColor"] == "#0f172a"
    assert "sankey" not in opts["plotOptions"]
    assert "color" not in opts["plotOptions"]["dependencywheel"]["dataLabels"]
    assert opts["tooltip"]["backgroundColor"] == "#0f172a"


# --------------------------------------------------------------------------- #
# Networkgraph (a force-directed graph: rows are UNWEIGHTED edges) — sankey's
# cousin, and the MIRROR of the gauge family: it removes the VALUE channel
# (empty y_cols) as gauge removes the LABEL channel (None x_col).
# --------------------------------------------------------------------------- #
def test_networkgraph_builds_edges_and_skips_missing():
    # Like sankey, each row is one edge keyed {from, to} — but UNWEIGHTED: there is no
    # third value key, because a per-link weight is silently dropped from the emitted JS
    # anyway. A row missing EITHER node isn't an edge, so it's dropped (no EnforcedNull:
    # there's no aligned slot, exactly as sankey drops a link).
    df = pd.DataFrame({"src": ["Web", None, "API"], "dst": ["API", "Auth", None]})
    opts = build_options(df, "networkgraph", "src", [], target_col="dst")
    assert opts["chart"]["type"] == "networkgraph"
    # One edge-series; its name is the source→target relation (no y column to name it).
    assert opts["series"][0]["name"] == "src → dst"
    assert opts["series"][0]["data"] == [{"from": "Web", "to": "API"}]
    # Nodes are palette-colored (like sankey/pie), not by a colorAxis, and there are no axes.
    assert opts["colors"] == list(DEFAULT_COLORS)
    assert "colorAxis" not in opts
    assert "xAxis" not in opts and "yAxis" not in opts


def test_networkgraph_builds_with_empty_y_cols():
    # The positive half of test_rejects_empty_y_cols' networkgraph EXCLUSION: an empty y_cols
    # is networkgraph's normal state (it has no value channel), so it must BUILD rather than
    # raise — the mirror of a gauge building with a None x_col.
    df = pd.DataFrame({"src": ["A", "B"], "dst": ["B", "C"]})
    opts = build_options(df, "networkgraph", "src", [], target_col="dst")
    assert opts["series"][0]["data"] == [
        {"from": "A", "to": "B"},
        {"from": "B", "to": "C"},
    ]


def test_networkgraph_ignores_any_y_cols_it_is_given():
    # It has no value channel, so a y column passed through the pure API (the sweeps do this)
    # changes nothing — the edges are identical with y_cols=["v"] and with []. Proven by
    # equality, so the day networkgraph starts reading y_cols this test fails.
    df = pd.DataFrame({"src": ["A"], "dst": ["B"], "v": [99.0]})
    with_y = build_options(df, "networkgraph", "src", ["v"], target_col="dst")
    without_y = build_options(df, "networkgraph", "src", [], target_col="dst")
    assert with_y["series"][0]["data"] == without_y["series"][0]["data"]


def test_networkgraph_requires_a_target_column():
    # An edge needs two ends, so the target is mandatory (a ValueError, not a silent
    # fallback) — sankey's rule, and the message names the type.
    df = pd.DataFrame({"src": ["A"], "dst": ["B"]})
    with pytest.raises(ValueError, match="networkgraph"):
        build_options(df, "networkgraph", "src", [])  # no target_col


def test_networkgraph_rejects_source_as_target():
    # One column can't name both ends — every edge would be a self-loop. Networkgraph's OWN
    # guard, shared with sankey (a fact about the two node columns), not the x-in-y rule.
    df = pd.DataFrame({"src": ["A", "B"]})
    with pytest.raises(ValueError):
        build_options(df, "networkgraph", "src", [], target_col="src")


def test_networkgraph_serializes_and_pulls_in_only_the_networkgraph_module():
    # End to end: the edge shape must serialize AND resolve modules/networkgraph.js — and,
    # unlike bubble/radar/boxplot, NOT highcharts-more (verified against the round-trip, the
    # correction to the common lore that a networkgraph needs it). colorByPoint must appear
    # NOWHERE: it is silently dropped for a networkgraph (so setting it is a lie), and the
    # nodes carry no per-point color at all.
    from highcharts_builder import make_chart

    df = pd.DataFrame({"src": ["A", "B"], "dst": ["B", "C"]})
    chart = make_chart(df, "networkgraph", "src", [], target_col="dst")
    js = chart.to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and "type: 'networkgraph'" in js
    # highcharts-core serializes each {from, to} dict as a [from, to] ARRAY (Highcharts' default
    # link shape) — so the node names reach the JS as array elements, not `from:`/`to:` keys.
    assert "'A'" in js and "'B'" in js and "'C'" in js
    assert "colorByPoint" not in js
    tags = chart.get_script_tags(as_str=True)
    assert "modules/networkgraph.js" in tags
    assert "highcharts-more" not in tags  # a networkgraph does NOT need highcharts-more


def test_networkgraph_disables_the_simulation_so_both_render_modes_agree():
    # enableSimulation MUST be False, and pinned on the EMITTED JS (this repo's silent-drop
    # discipline). It is the one setting the whole type turns on: with it True the export
    # server rasterizes the graph as an unreadable central knot while the iframe animates it
    # loose, so the two render modes disagree — the class of bug _LIGHT_COLOR_SCHEME_CSS
    # exists to close. With it False Highcharts settles the layout synchronously and both
    # modes draw the same picture.
    from highcharts_builder import make_chart

    df = pd.DataFrame({"src": ["A"], "dst": ["B"]})
    opts = build_options(df, "networkgraph", "src", [], target_col="dst")
    layout = opts["plotOptions"]["networkgraph"]["layoutAlgorithm"]
    assert layout["enableSimulation"] is False
    # keys maps each serialized [from, to] array onto the edge's two ends.
    assert opts["plotOptions"]["networkgraph"]["keys"] == ["from", "to"]
    js = make_chart(df, "networkgraph", "src", [], target_col="dst").to_js_literal()
    assert js and "enableSimulation: false" in js


def test_networkgraph_labels_its_nodes_and_prints_nothing_per_edge():
    # Nodes are labelled by name (their only identity — no axis, no legend). Unlike sankey
    # there is NO per-edge label, because the type is unweighted: there is no value to print
    # in the mark. So the edges are bare {from, to} dicts with no dataLabels of their own.
    df = pd.DataFrame({"src": ["A", "B"], "dst": ["B", "C"]})
    opts = build_options(df, "networkgraph", "src", [], target_col="dst")
    assert opts["plotOptions"]["networkgraph"]["dataLabels"] == {"enabled": True}
    assert all("dataLabels" not in edge for edge in opts["series"][0]["data"])
    # Each label dict is copied off the module constant, so nothing can mutate it downstream.
    assert (
        opts["plotOptions"]["networkgraph"]["dataLabels"]
        is not build_options(df, "networkgraph", "src", [], target_col="dst")[
            "plotOptions"
        ]["networkgraph"]["dataLabels"]
    )


def test_networkgraph_light_mode_shape():
    # The light-mode choices nothing else guards: the disabled legend (nodes are labelled on the
    # chart), and — deliberately — NO custom tooltip at all. A networkgraph tooltip fires on a
    # NODE, whose point has no fromNode/toNode, so a "name the edge" pointFormat would render an
    # empty box on every node hover; and the node-specific nodeFormat that would fix it is silently
    # dropped (sankey's trap). Highcharts' own default prints the node name and is the only way to
    # get it, so the branch sets no tooltip — and in light mode (where _themed is a no-op) the
    # options carry none at all.
    df = pd.DataFrame({"src": ["A"], "dst": ["B"]})
    opts = build_options(df, "networkgraph", "src", [], target_col="dst")
    assert opts["legend"]["enabled"] is False
    assert (
        "tooltip" not in opts
    )  # no custom tooltip: Highcharts' default names the nodes
    # Light mode injects no dark chrome anywhere.
    assert "borderColor" not in opts["plotOptions"]["networkgraph"]


def test_networkgraph_dark_mode_themes_only_the_shared_chrome():
    # Networkgraph needs NO type-specific _themed hook (like boxplot, and for a kindred
    # reason): its node labels ride Highcharts' `contrast` color (white on dark, black on
    # light — verified by rendering), its nodes carry palette hues, and its links use a grey
    # legible on both backgrounds. So dark mode sets the shared chrome (background, tooltip)
    # and touches plotOptions.networkgraph not at all.
    df = pd.DataFrame({"src": ["A"], "dst": ["B"]})
    opts = build_options(df, "networkgraph", "src", [], target_col="dst", dark=True)
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    assert opts["tooltip"]["backgroundColor"] == "#0f172a"
    # No border/color flip and no dataLabels color — the plotOptions block is untouched by dark.
    assert "borderColor" not in opts["plotOptions"]["networkgraph"]
    assert "color" not in opts["plotOptions"]["networkgraph"]["dataLabels"]
    # No axes to theme; the axis loop must skip it, not crash.
    assert "xAxis" not in opts and "yAxis" not in opts


def test_networkgraph_numeric_node_labels_coerce_to_strings():
    # Both node columns are stringified — highcharts-core's point model rejects a non-string
    # node name — exactly as sankey's are. A user picking numeric ids gets named nodes, not a
    # blank chart.
    df = pd.DataFrame({"src": [1, 2], "dst": [10, 20]})
    opts = build_options(df, "networkgraph", "src", [], target_col="dst")
    assert opts["series"][0]["data"] == [
        {"from": "1", "to": "10"},
        {"from": "2", "to": "20"},
    ]


def test_networkgraph_count_marks_counts_drawable_edges():
    # Its marks are the edges: one per row with BOTH ends present, no value consulted (the
    # type is unweighted). The KPI's "Links" reads this. A row missing either node drops.
    df = pd.DataFrame({"src": ["A", None, "C", "D"], "dst": ["B", "Y", None, "E"]})
    assert count_marks(df, "networkgraph", "src", [], target_col="dst") == 2


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
# waterfall (signed deltas floating at a running total)
# --------------------------------------------------------------------------- #
def _bridge() -> pd.DataFrame:
    """Four signed deltas — the mixed signs are the point of the type."""
    return pd.DataFrame(
        {
            "step": ["Revenue", "COGS", "Opex", "Tax"],
            "delta": [120.0, -45.0, -18.0, -7.0],
        }
    )


def test_waterfall_builds_steps_and_appends_a_total():
    # The frame carries only the DELTAS; the closing bar is the builder's, not the data's.
    # So the axis gains a category and the series a point that no row produced — waterfall
    # is the one type whose mark count exceeds its row count.
    opts = build_options(_bridge(), "waterfall", "step", ["delta"])
    assert opts["chart"]["type"] == "waterfall"
    assert opts["xAxis"]["categories"] == ["Revenue", "COGS", "Opex", "Tax", "Total"]
    data = opts["series"][0]["data"]
    assert data[:4] == [120.0, -45.0, -18.0, -7.0]  # positional, matched to categories
    # isSum makes Highcharts total the preceding deltas itself, so the bar reaches down to
    # zero as a LEVEL rather than stacking as one more delta. That IS the bridge.
    assert data[4]["isSum"] is True
    assert opts["series"][0]["name"] == "delta"
    assert opts["xAxis"]["title"]["text"] == "step"  # every category-x type pins this
    assert opts["yAxis"]["title"]["text"] == "delta"
    assert opts["legend"]["enabled"] is False


def test_waterfall_colors_rises_falls_and_the_total_by_meaning():
    # The bars are colored by MEANING, not identity: green up, red down, brand-blue total.
    opts = build_options(_bridge(), "waterfall", "step", ["delta"])
    wf = opts["plotOptions"]["waterfall"]
    assert wf["upColor"] == DEFAULT_COLORS[1]  # green: a rise
    assert wf["color"] == DEFAULT_COLORS[3]  # red: a fall
    assert opts["series"][0]["data"][4]["color"] == DEFAULT_COLORS[0]  # blue: the total


def test_waterfall_total_is_taken_off_the_up_down_color_scale():
    # Left alone, Highcharts colors the sum by ITS OWN SIGN, exactly as it colors a delta: a
    # positive total takes upColor (green), a negative one takes color (red). Verified by
    # rendering it. But green does not mean the same thing on the two kinds of bar — on a
    # delta it says "this step ADDED", while on the total it would say only "the end level is
    # above zero", which a bridge that fell 420 -> 79 would also earn. So the total is taken
    # off the up/down scale and marked as the different KIND of bar it is: a LEVEL, not a
    # change. Pin the per-point color on the emitted JS — unlike boxplot's fillColor
    # (accepted, then silently dropped), a point color does survive.
    from highcharts_builder import make_chart

    js = make_chart(_bridge(), "waterfall", "step", ["delta"]).to_js_literal()
    assert js  # stubbed str | None
    compact = "".join(js.split())
    assert f"isSum:true,color:'{DEFAULT_COLORS[0]}'" in compact
    # The total's hue must be neither of the two the deltas use, or it rejoins the very scale
    # this takes it off. (_bridge() sums to +50, so without the override it would be green.)
    assert DEFAULT_COLORS[0] not in (DEFAULT_COLORS[1], DEFAULT_COLORS[3])


def test_waterfall_semantic_colors_ignore_a_custom_palette():
    # `colors` overrides the series palette, but must NOT repaint the bars: red-means-loss
    # is the chart's semantics, not a series' arbitrary identity, so a custom palette can't
    # turn a fall green. The _BOXPLOT_OUTLIER_COLOR rule — and it also means a caller's
    # SHORT palette (two entries here, where the hues index up to 3) can't IndexError.
    opts = build_options(
        _bridge(), "waterfall", "step", ["delta"], colors=["#000000", "#ffffff"]
    )
    assert opts["colors"] == ["#000000", "#ffffff"]  # carried, as heatmap carries it
    wf = opts["plotOptions"]["waterfall"]
    assert wf["upColor"] == DEFAULT_COLORS[1] and wf["color"] == DEFAULT_COLORS[3]
    assert opts["series"][0]["data"][-1]["color"] == DEFAULT_COLORS[0]


def test_waterfall_missing_delta_keeps_its_slot_as_enforced_null():
    # A missing/non-finite delta KEEPS its slot (the `_num` cartesian rule), rather than
    # dropping its row as pie and treemap do. Semantics, not just shape: a null delta means
    # "no change", so Highcharts draws no bar and carries the running total straight through
    # — true. Dropping the row would delete a step from the bridge without saying so.
    df = pd.DataFrame(
        {
            "step": ["a", "b", "c", "d"],
            "delta": [1.0, float("nan"), float("inf"), 4.0],
        }
    )
    opts = build_options(df, "waterfall", "step", ["delta"])
    data = opts["series"][0]["data"]
    assert data[1] is EnforcedNull and data[2] is EnforcedNull  # inf is missing too
    assert opts["xAxis"]["categories"] == [
        "a",
        "b",
        "c",
        "d",
        "Total",
    ]  # nothing shifted
    # And the null must REACH the JS — a Python None would be dropped and misalign the bars.
    from highcharts_builder import make_chart

    js = make_chart(df, "waterfall", "step", ["delta"]).to_js_literal()
    # not a bare "null", which other keys could satisfy
    assert js and "null]" in js  # stubbed str | None


def test_waterfall_with_no_drawable_steps_appends_no_total():
    # A lone "Total: 0" bar is not a chart — the restraint boxplot shows in omitting an
    # empty outlier series, and sankey/heatmap in gating their labels on count.
    from highcharts_builder import count_marks

    df = pd.DataFrame({"step": [float("nan")], "delta": [1.0]})
    opts = build_options(df, "waterfall", "step", ["delta"])
    assert opts["series"][0]["data"] == []
    assert opts["xAxis"]["categories"] == []
    # And the KPI must agree with the empty chart. This is the ONLY test that reaches
    # count_marks' zero-step branch: without it, `return steps + 1` (dropping the `if steps`
    # guard entirely) passes the whole suite while the app reports "Steps: 1" over a chart
    # with no bars at all.
    assert count_marks(df, "waterfall", "step", ["delta"]) == 0


def test_waterfall_labels_each_bar_with_its_delta():
    # The value is printed IN the bar, as pie/heatmap/treemap/sankey print theirs, so the
    # Static-PNG mode (which has no hover tooltip) still shows the numbers. This is where
    # waterfall parts from column/bar, which carry no labels: their bars stand ON the axis,
    # so a height is a value — while a waterfall's bar floats at the running total and
    # encodes its value as a LENGTH, which no axis can be read against.
    opts = build_options(_bridge(), "waterfall", "step", ["delta"])
    labels = opts["plotOptions"]["waterfall"]["dataLabels"]
    assert labels["enabled"] is True
    assert labels["format"] == "{point.y}"
    assert (
        labels["inside"] is True
    )  # on the bar, where "contrast" is computed vs the fill
    assert labels["color"] == "contrast"
    # The outline is what keeps "contrast" legible where a label straddles a bar's edge. It
    # comes from the shared _in_mark_labels helper (with heatmap's cells and treemap's
    # tiles), so pin it here too — otherwise dropping it from that helper breaks three types
    # and no waterfall test notices.
    assert labels["style"]["textOutline"] == "1px contrast"
    assert labels["color"] == "contrast"


def test_waterfall_many_steps_omit_the_value_labels():
    # Above the gate the labels overprint into noise (the heatmap/sankey rule). The count
    # includes the appended total, which is drawn and labelled like any other bar.
    from highcharts_builder import _WATERFALL_DATALABEL_MAX_STEPS

    n = _WATERFALL_DATALABEL_MAX_STEPS  # n steps + 1 total = one over the gate
    df = pd.DataFrame({"step": [str(i) for i in range(n)], "delta": [1.0] * n})
    opts = build_options(df, "waterfall", "step", ["delta"])
    assert len(opts["series"][0]["data"]) == n + 1
    assert "dataLabels" not in opts["plotOptions"]["waterfall"]
    # One fewer step and they come back, so the boundary is pinned, not just the far side.
    smaller = df.iloc[:-1]
    assert (
        "dataLabels"
        in build_options(smaller, "waterfall", "step", ["delta"])["plotOptions"][
            "waterfall"
        ]
    )


def test_waterfall_tooltip_names_the_category_not_the_point():
    # {point.name} would render BLANK: the points are positional, their names living in
    # xAxis.categories. {point.category} is what reads them back — bubble's non-numeric-x
    # tooltip resolves the same way, for the same reason.
    opts = build_options(_bridge(), "waterfall", "step", ["delta"])
    fmt = opts["tooltip"]["pointFormat"]
    assert "{point.category}" in fmt
    assert "{point.name}" not in fmt
    assert "{point.y}" in fmt  # on the appended bar this is the summed total
    # The empty header suppresses Highcharts' default header row, which would repeat the
    # category the pointFormat already names (treemap and sankey suppress theirs the same
    # way). Pinned, or dropping it silently restores the duplicate.
    assert opts["tooltip"]["headerFormat"] == ""


def test_waterfall_uses_only_first_y_col():
    df = _bridge()
    df["other"] = [9.0, 9.0, 9.0, 9.0]
    opts = build_options(df, "waterfall", "step", ["delta", "other"])
    assert len(opts["series"]) == 1
    assert opts["series"][0]["name"] == "delta"


def test_waterfall_rejects_x_in_y():
    # Its x_col is a category axis, so it joins X_IN_Y_GUARD_TYPES (with heatmap/boxplot).
    with pytest.raises(ValueError, match="cannot also be a y series"):
        build_options(_bridge(), "waterfall", "step", ["step"])


def test_waterfall_numeric_step_labels_coerce_to_strings():
    df = pd.DataFrame({"step": [1, 2], "delta": [1.0, -1.0]})
    opts = build_options(df, "waterfall", "step", ["delta"])
    assert opts["xAxis"]["categories"] == ["1", "2", "Total"]


def test_waterfall_serializes_and_pulls_in_the_more_module():
    # End to end: isSum must survive the point model (highcharts-core accepts plenty it then
    # silently drops — boxplot's fillColor, sankey's nodeFormat), and the module must resolve
    # to highcharts-more, which waterfall shares with bubble, radar and boxplot rather than
    # having a modules/*.js of its own.
    from highcharts_builder import make_chart

    chart = make_chart(_bridge(), "waterfall", "step", ["delta"])
    js = chart.to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and "type: 'waterfall'" in js
    compact = "".join(js.split())
    assert "isSum:true" in compact  # the sum point survived
    assert "upColor:'#16a34a'" in compact  # so did the semantic hues
    assert "inside:true" in compact  # and the in-bar labels
    tags = chart.get_script_tags(as_str=True)
    assert "highcharts-more" in tags  # bubble/radar/boxplot's module, shared
    assert "modules/" not in tags  # waterfall has no module of its own


def test_waterfall_light_mode_shape():
    # Mirrors the treemap/sankey/boxplot light-mode tests: pin the choices nothing else
    # guards, and prove the dark-only keys are absent (so the dark test below is meaningful).
    opts = build_options(_bridge(), "waterfall", "step", ["delta"])
    assert opts["legend"]["enabled"] is False
    wf = opts["plotOptions"]["waterfall"]
    assert set(wf) == {"upColor", "color", "dataLabels"}
    assert "borderColor" not in wf and "lineColor" not in wf


def test_waterfall_dark_mode_themes_the_bars_and_the_connectors():
    # TWO flips, and neither is column/bar's. Waterfall's bar border and its connector lines
    # BOTH default to a fixed #333333 (measured off the rendered PNG on either background),
    # not to the background variable that resolves to white for column/bar — so the bars are
    # never ringed white, and these flips are not that bug. The border, a crisp definition
    # line on the white shell, becomes a muddy grey ring one shade off the dark background,
    # and buys nothing (waterfall's bars never touch), so it is dissolved into the background
    # as pie/treemap/sankey dissolve their gaps. The CONNECTOR lines — what make a waterfall
    # read as a running total rather than a row of floating bars — survive on the dark
    # background only barely, so they are lifted to the axis color. That half is waterfall's
    # alone: it is the only line Highcharts draws BETWEEN marks.
    opts = build_options(_bridge(), "waterfall", "step", ["delta"], dark=True)
    wf = opts["plotOptions"]["waterfall"]
    assert wf["borderColor"] == "#0f172a"  # == _DARK_CHROME["bg"]
    assert wf["lineColor"] == "#475569"  # == _DARK_CHROME["axis"]
    # The bar hues are NOT flipped: like the shared series palette, they read on both
    # backgrounds, and their meaning is fixed.
    assert wf["upColor"] == DEFAULT_COLORS[1] and wf["color"] == DEFAULT_COLORS[3]
    assert opts["chart"]["backgroundColor"] == "#0f172a"


# --------------------------------------------------------------------------- #
# Sunburst — a hierarchy read from an adjacency list
# --------------------------------------------------------------------------- #
def _tree() -> pd.DataFrame:
    """Two branches over four leaves, three levels deep counting the synthesized root.

    "Other" appears TWICE, under two different parents — the case a label-keyed node
    identity would silently merge (and which Highcharts rejects outright, as error #31).
    Nothing NAMES "Other" as a parent, so it is not ambiguous, just repeated.
    """
    return pd.DataFrame(
        {
            "node": ["EMEA", "APAC", "UK", "Other", "Japan", "Other"],
            "parent": [None, None, "EMEA", "EMEA", "APAC", "APAC"],
            "value": [None, None, 500.0, 100.0, 380.0, 40.0],
        }
    )


def _sun(df=None, **kw):
    return build_options(
        df if df is not None else _tree(),
        "sunburst",
        "node",
        ["value"],
        parent_col="parent",
        **kw,
    )


def _points(opts) -> list[dict]:
    return opts["series"][0]["data"]


def test_sunburst_builds_nodes_and_appends_a_root():
    points = _points(_sun())
    assert len(points) == 7  # 6 rows + the appended root
    root = points[-1]  # APPENDED, so the real nodes keep their row positions
    assert root["id"] == "__root__" and root["name"] == "All"
    # The root carries NO value: it is internal by construction, so Highcharts sums the whole
    # tree into it and the centre reads a total the builder never computed.
    assert "value" not in root
    assert [p["name"] for p in points[:-1]] == [
        "EMEA",
        "APAC",
        "UK",
        "Other",
        "Japan",
        "Other",
    ]


def test_sunburst_ids_are_synthesized_never_the_labels():
    # THE identity decision. Highcharts links parent -> child by `id`, and a duplicate id is
    # not a silent mismatch but error #31 ("Non-unique point or node id"), printed in a red
    # band across the chart. Synthesizing ids from the row position makes that unreachable: a
    # CSV label lands only in `name`, so nothing in a hostile file can collide with anything.
    points = _points(_sun())
    ids = [p["id"] for p in points]
    assert len(ids) == len(set(ids))  # the invariant error #31 exists to enforce
    assert ids == ["n0", "n1", "n2", "n3", "n4", "n5", "__root__"]
    assert not any(p["id"] == p["name"] for p in points[:-1])


def test_sunburst_duplicate_labels_under_different_parents_stay_distinct_sectors():
    # The pay-off of synthesized ids, and the reason label-as-id was rejected. Two teams named
    # "Other" are two honest sectors worth 100 and 40 — NOT one merged sector worth 140 hanging
    # under whichever parent won. Identity is the ROW, exactly as it is for treemap.
    others = [p for p in _points(_sun()) if p["name"] == "Other"]
    assert len(others) == 2
    assert {p["id"] for p in others} == {"n3", "n5"}
    assert sorted(p["value"] for p in others) == [40.0, 100.0]  # not merged into 140
    assert {p["parent"] for p in others} == {"n0", "n1"}  # under EMEA and APAC


def test_sunburst_a_duplicate_label_used_as_a_parent_raises():
    # A duplicate label is only a CONTRADICTION once something points at it: `parent = "dup"`
    # then names no single node. The alternatives are both silent lies — merge the twins, or
    # pick one and graft a subtree onto the wrong branch — so it raises, sankey's rule.
    df = pd.DataFrame(
        {
            "node": ["dup", "dup", "child"],
            "parent": [None, None, "dup"],
            "value": [None, 1.0, 2.0],
        }
    )
    with pytest.raises(ValueError, match="must name exactly one"):
        _sun(df)


def test_sunburst_internal_nodes_carry_no_value_and_leaves_always_do():
    # The invariant. Highcharts resolves a node's size as its own value IF GIVEN, else the sum
    # of its children — so an explicit parent value OVERRIDES the sum, and a subtotal row would
    # draw a parent whose arc disagrees with the arcs inside it (verified by rendering: two
    # branches declaring value=1 drew as equal halves while holding 900 and 100). Omitting it
    # makes a parent's arc always equal what is actually drawn under it.
    for point in _points(_sun()):
        is_leaf = point["name"] in ("UK", "Other", "Japan")
        assert ("value" in point) is is_leaf, point


def test_sunburst_an_internal_nodes_stated_value_is_ignored():
    # ...and it is ignored even when the CSV states one, which is the case that matters: a
    # subtotal row is an extremely common export. The number is discarded, not honored.
    df = _tree()
    df.loc[0, "value"] = 999.0  # EMEA claims 999; its children hold 600
    emea = next(p for p in _points(_sun(df)) if p["name"] == "EMEA")
    assert "value" not in emea


def test_sunburst_ring_one_is_seeded_from_the_palette_and_descendants_inherit():
    # The canonical Highcharts recipe — levels[].colorByPoint — is accepted by
    # Chart.from_options and then SILENTLY DROPPED (the treemap "value not y" trap), and the
    # colorByPoint that does survive is the series-wide one, which would hand every point its
    # own hue and destroy the inheritance. So ring 1 is seeded per POINT and everything below
    # it carries no color at all, inheriting its branch's (verified by rendering).
    points = _points(_sun())
    seeded = {p["name"]: p["color"] for p in points if "color" in p}
    assert seeded["EMEA"] == DEFAULT_COLORS[0]
    assert seeded["APAC"] == DEFAULT_COLORS[1]
    for point in points:
        if point["name"] not in ("EMEA", "APAC", "All"):
            assert "color" not in point, (
                f"{point['name']} must inherit, not carry, a hue"
            )


def test_sunburst_ring_one_takes_a_custom_palette_and_a_short_one_cycles():
    # Unlike waterfall's semantic red-means-loss, a branch's hue is its arbitrary IDENTITY —
    # like a pie slice's — so a caller MAY repaint it. A one-color palette must cycle rather
    # than IndexError (the _BOXPLOT_OUTLIER_COLOR concern).
    points = _points(_sun(colors=["#111111"]))
    seeded = [p["color"] for p in points if p["name"] in ("EMEA", "APAC")]
    assert seeded == ["#111111", "#111111"]


def test_sunburst_root_color_is_off_the_categorical_scale():
    # Waterfall's Total argument, transposed. There the scale was up/down and blue sat off it;
    # here the scale is the WHOLE palette, which ring 1 CYCLES — so no palette entry is
    # guaranteed not to be some branch's hue, and the only way to say "this is not a category,
    # it is the whole" is a color from outside the palette. Read straight from the constant, so
    # a custom palette cannot repaint the root as one more branch.
    root = _points(_sun())[-1]
    assert root["color"] == "#94a3b8"
    assert root["color"] not in DEFAULT_COLORS
    # ...and a custom palette does NOT reach it, though it does reach ring 1 above.
    assert _points(_sun(colors=["#111111", "#222222"]))[-1]["color"] == "#94a3b8"


def test_sunburst_levels_add_an_alternating_color_variation_below_ring_one():
    # Ring 1 (level 2) gets no entry — it is seeded per point. Every ring below needs a
    # colorVariation or a branch's descendants, which inherit its hue, would be
    # indistinguishable. The SIGN alternates because the variation applies to the parent's
    # already-varied color: a fixed -0.5 walks a deep tree to black.
    levels = _sun()["plotOptions"]["sunburst"]["levels"]
    assert levels[0] == {"level": 1, "levelSize": {"unit": "percentage", "value": 15}}
    assert levels[1] == {
        "level": 3,
        "colorVariation": {"key": "brightness", "to": -0.5},
    }
    assert not any(entry["level"] == 2 for entry in levels)
    # A deeper tree keeps going, and flips the sign at each ring.
    deep = pd.DataFrame(
        {
            "node": ["a", "b", "c", "d"],
            "parent": [None, "a", "b", "c"],
            "value": [None, None, None, 1.0],
        }
    )
    deep_levels = _sun(deep)["plotOptions"]["sunburst"]["levels"]
    assert [entry["level"] for entry in deep_levels] == [1, 3, 4, 5]
    assert [entry["colorVariation"]["to"] for entry in deep_levels[1:]] == [
        -0.5,
        0.5,
        -0.5,
    ]


def test_sunburst_a_two_ring_tree_needs_no_color_variation():
    # Root + one ring: nothing to vary, so only the levelSize entry is emitted (the
    # dead-config restraint the heatmap/sankey label gates show).
    flat = pd.DataFrame(
        {"node": ["a", "b"], "parent": [None, None], "value": [1.0, 2.0]}
    )
    levels = _sun(flat)["plotOptions"]["sunburst"]["levels"]
    assert levels == [{"level": 1, "levelSize": {"unit": "percentage", "value": 15}}]


def test_sunburst_dangling_parent_drops_the_row_and_its_descendants():
    # A parent naming no node is MISSING DATA, so its row is dropped — treemap's rule. And the
    # drop must be TRANSITIVE: Highcharts does not leave an unmatched parent alone, it silently
    # RE-PARENTS the child to the root, which would promote an orphaned grandchild into ring 1
    # and lie about the data. Here "b" dangles and "c" hangs off "b", so both go — and "a",
    # left with no children and no value of its own, goes too.
    df = pd.DataFrame(
        {
            "node": ["a", "b", "c", "keep"],
            "parent": [None, "ATLANTIS", "b", None],
            "value": [None, 1.0, 2.0, 7.0],
        }
    )
    assert [p["name"] for p in _points(_sun(df))] == ["keep", "All"]


def test_sunburst_a_cycle_raises():
    # A cycle is not missing data, it is a CONTRADICTION — there is no right drawing of it —
    # so it raises rather than dropping, mirroring sankey's x_col == target_col guard. The
    # message names the loop so the user can find it.
    two = pd.DataFrame({"node": ["a", "b"], "parent": ["b", "a"], "value": [1.0, 2.0]})
    with pytest.raises(ValueError, match=r"'a' → 'b' → 'a' is a cycle"):
        _sun(two)
    # The degenerate one-node cycle: a node that is its own parent. Same guard, same message.
    self_parent = pd.DataFrame({"node": ["a"], "parent": ["a"], "value": [1.0]})
    with pytest.raises(ValueError, match=r"'a' → 'a' is a cycle"):
        _sun(self_parent)


def test_sunburst_a_forest_with_no_top_level_node_is_a_cycle():
    # Each node has exactly one parent, so the parent map is a FUNCTION: if no node is
    # top-level and every parent resolves, following parents from anywhere must revisit a node
    # within N steps. "No roots" therefore *implies* a cycle — it is not a separate case.
    df = pd.DataFrame(
        {"node": ["a", "b", "c"], "parent": ["c", "a", "b"], "value": [1.0, 2.0, 3.0]}
    )
    with pytest.raises(ValueError, match="is a cycle"):
        _sun(df)


def test_sunburst_a_dangling_row_does_not_hide_a_cycle():
    # Order-independence, stated as a test. No node in a cycle can ever be dangling (every
    # cycle node's parent is the next cycle node, which exists), so dropping a dangling row can
    # never break one — the walk raises regardless of which it meets first.
    df = pd.DataFrame(
        {
            "node": ["orphan", "a", "b"],
            "parent": ["ATLANTIS", "b", "a"],
            "value": [1.0, 2.0, 3.0],
        }
    )
    with pytest.raises(ValueError, match="is a cycle"):
        _sun(df)


def test_sunburst_a_long_cycle_and_a_deep_chain_survive_without_recursion():
    # Both are reachable from a plain CSV and both would blow a recursive walk's stack, so the
    # walk is iterative. The cycle raises; the chain builds.
    n = 5000
    cycle = pd.DataFrame(
        {
            "node": [str(i) for i in range(n)],
            "parent": [str((i - 1) % n) for i in range(n)],
            "value": [1.0] * n,
        }
    )
    with pytest.raises(ValueError, match="is a cycle"):
        _sun(cycle)
    chain = pd.DataFrame(
        {
            "node": [str(i) for i in range(n)],
            "parent": [None, *(str(i - 1) for i in range(1, n))],
            "value": [None] * (n - 1) + [1.0],  # only the deepest node is a leaf
        }
    )
    assert len(_points(_sun(chain))) == n + 1  # every node, plus the root


def test_sunburst_a_long_cycle_message_is_truncated():
    # A 10,000-node cycle must not print a 10,000-node message — but the loop must still
    # visibly CLOSE, so the final label is always kept.
    n = 50
    df = pd.DataFrame(
        {
            "node": [str(i) for i in range(n)],
            "parent": [str((i - 1) % n) for i in range(n)],
            "value": [1.0] * n,
        }
    )
    with pytest.raises(ValueError) as excinfo:
        _sun(df)
    message = str(excinfo.value)
    assert "..." in message and message.count("→") <= 8


def test_sunburst_a_missing_non_finite_or_negative_leaf_value_drops_the_row():
    # A leaf's value must be able to SIZE AN ARC. A negative one cannot: Highcharts draws no
    # sector for it AND excludes it from its parent's sum (verified by rendering — a -400 leaf
    # beside a 500 one drew nothing and left its parent sized 500, not 100), so keeping the row
    # would make count_marks report a mark the chart never draws. Zero is KEPT: it is a real
    # measurement, it draws a zero-width sector, and it corrupts no sum — pie's and treemap's
    # rule for their own zeros.
    df = pd.DataFrame(
        {
            "node": ["root", "gone_nan", "gone_inf", "gone_neg", "kept_zero", "kept"],
            "parent": [None, "root", "root", "root", "root", "root"],
            "value": [None, float("nan"), float("inf"), -400.0, 0.0, 500.0],
        }
    )
    names = [p["name"] for p in _points(_sun(df))]
    assert names == ["root", "kept_zero", "kept", "All"]


def test_sunburst_a_parent_left_childless_becomes_a_leaf():
    # Not a special case — the rule itself: keep(n) = its value can size an arc, OR something
    # under it survived. So a node whose only child was dropped BECOMES a leaf, and then its
    # own value is what sizes it. (And when it has none, it is dropped in turn.)
    df = pd.DataFrame(
        {
            "node": ["has_own", "doomed_child", "has_none", "doomed_child2"],
            "parent": [None, "has_own", None, "has_none"],
            "value": [42.0, float("nan"), None, float("nan")],
        }
    )
    points = _points(_sun(df))
    assert [p["name"] for p in points] == ["has_own", "All"]
    assert points[0]["value"] == 42.0  # promoted to a leaf, sized by its own value


def test_sunburst_a_blank_missing_or_whitespace_parent_is_a_top_level_branch():
    # The ONE place in the module where a missing label is a STATEMENT, not an error:
    # everywhere else `_label_ok` False means "drop the row", here it means "hang off the
    # root". A whitespace-only string is folded in — read as a label it would match no node,
    # dangle, and drop the row: the silently wrong answer where "top-level" is the right one.
    df = pd.DataFrame(
        {
            "node": ["a", "b", "c", "d"],
            "parent": [None, "", "   ", float("nan")],
            "value": [1.0, 2.0, 3.0, 4.0],
        }
    )
    points = _points(_sun(df))
    assert len(points) == 5  # all four, plus the root
    assert all(p["parent"] == "__root__" for p in points[:-1])
    # ...and all four are ring-1 branches, so all four are seeded from the palette.
    assert [p["color"] for p in points[:-1]] == list(DEFAULT_COLORS[:4])


def test_sunburst_a_numeric_node_column_matches_a_float_parent_column():
    # The `_node_key` trap, and the most canonical adjacency CSV there is. A blank parent cell
    # WIDENS that column to float64, so `node` comes in as int64 and `parent` as float64 —
    # and a bare str() would stringify the same node to "1" on one side and "1.0" on the
    # other. Every parent would dangle, every row would drop, and the chart would come out
    # SILENTLY EMPTY.
    df = pd.DataFrame(
        {"node": [1, 2, 3], "parent": [None, 1, 1], "value": [None, 10.0, 20.0]}
    )
    assert str(df["node"].dtype) == "int64" and str(df["parent"].dtype) == "float64"
    points = _points(_sun(df))
    assert [p["name"] for p in points] == ["1", "2", "3", "All"]
    assert points[1]["parent"] == points[0]["id"]  # "2" really did attach to "1"


def test_sunburst_a_node_labelled_like_the_root_does_not_collide():
    # Ids are synthesized, so CSV text never becomes one and a node literally named "__root__"
    # is just a node. A node named "All" is a cosmetic name clash on screen — exactly as a
    # waterfall step named "Total" is — not a broken tree.
    df = pd.DataFrame(
        {
            "node": ["__root__", "All"],
            "parent": [None, None],
            "value": [1.0, 2.0],
        }
    )
    points = _points(_sun(df))
    assert [p["id"] for p in points] == ["n0", "n1", "__root__"]
    assert points[0]["name"] == "__root__" and points[0]["id"] != "__root__"


def test_sunburst_with_no_drawable_nodes_appends_no_root():
    # A lone slate disc labelled "All" is not a chart — waterfall's no-lone-Total restraint,
    # and boxplot's in omitting an empty outlier series. Pins the `if points` guard.
    df = pd.DataFrame({"node": ["a"], "parent": [None], "value": [float("nan")]})
    assert _points(_sun(df)) == []
    from highcharts_builder import count_marks

    assert count_marks(df, "sunburst", "node", ["value"], parent_col="parent") == 0


def test_sunburst_labels_each_sector_with_its_name_only():
    # The one type that does NOT print its value in the mark, and the geometry is why: a sector
    # is a thin CURVED arc with the text bent along it, so there is room for one short string —
    # and the name is the only thing identifying a sector (a sunburst has neither axis nor
    # legend), while the value is already encoded as the ANGLE.
    labels = _sun()["plotOptions"]["sunburst"]["dataLabels"]
    assert labels["enabled"] is True
    assert labels["format"] == "{point.name}"
    assert labels["rotationMode"] == "circular"
    assert (
        labels["color"] == "contrast"
    )  # computed against the sector fill (treemap's rule)


def test_sunburst_many_sectors_omit_the_labels():
    # The heatmap-cell / sankey-link / waterfall-step gate. Unlike those, a sunburst's
    # dataLabels default to ON, so past the gate they must be turned off EXPLICITLY —
    # omitting the key would be a gate that did nothing.
    n = 70
    df = pd.DataFrame(
        {
            "node": [str(i) for i in range(n)],
            "parent": [None] * n,
            "value": [1.0] * n,
        }
    )
    assert _sun(df)["plotOptions"]["sunburst"]["dataLabels"] == {"enabled": False}
    # ...and just under the gate they are drawn (both sides of the boundary).
    n = 59  # 59 nodes + the root == 60, the limit
    under = pd.DataFrame(
        {
            "node": [str(i) for i in range(n)],
            "parent": [None] * n,
            "value": [1.0] * n,
        }
    )
    assert _sun(under)["plotOptions"]["sunburst"]["dataLabels"]["enabled"] is True


def test_sunburst_tooltip_names_the_point_not_the_category():
    # {point.name}, not waterfall's {point.category}: sunburst's points are NAMED dicts rather
    # than positional ones. On the appended root {point.value} is the grand total Highcharts
    # summed, which is exactly what it should read.
    tooltip = _sun()["tooltip"]
    assert tooltip["headerFormat"] == ""
    assert tooltip["pointFormat"] == "{point.name}: <b>{point.value}</b>"


def test_sunburst_uses_only_first_y_col():
    df = _tree()
    df["ignored"] = [9.0] * 6
    assert _sun(df)["series"][0]["name"] == "value"


def test_sunburst_requires_a_parent_column():
    with pytest.raises(ValueError, match="requires a parent column"):
        build_options(_tree(), "sunburst", "node", ["value"])


def test_sunburst_rejects_x_col_as_the_parent_column():
    # Every row would name itself as its own parent. The tree walk WOULD catch it, but with a
    # mystifying "'EMEA' → 'EMEA' is a cycle" when the real fault is that one column was picked
    # twice — sankey's source-is-target argument.
    with pytest.raises(ValueError, match="cannot also be the parent column"):
        build_options(_tree(), "sunburst", "node", ["value"], parent_col="node")


def test_sunburst_allows_x_in_y():
    # Deliberately NOT in X_IN_Y_GUARD_TYPES: its x_col is a node LABEL, not a category axis,
    # and its own collision is node-vs-parent (which parent_col guards). x-in-y merely names
    # every node by its own value — odd, well-defined, drawable. The scatter/sankey tolerance,
    # third instance.
    df = pd.DataFrame({"node": [1.0, 2.0], "parent": [None, 1.0]})
    points = _points(
        build_options(df, "sunburst", "node", ["node"], parent_col="parent")
    )
    assert [p["name"] for p in points] == ["1", "2", "All"]
    assert (
        points[1]["value"] == 2.0
    )  # the leaf is sized by the very column that names it


def test_sunburst_explain_tree_error_returns_the_message_build_options_raises():
    # The app renders this instead of letting the builder raise (the interactive path does not
    # catch), so the two MUST be the same string — the X_IN_Y_GUARD_TYPES named-once rule.
    from highcharts_builder import explain_tree_error

    cyclic = pd.DataFrame(
        {"node": ["a", "b"], "parent": ["b", "a"], "value": [1.0, 2.0]}
    )
    problem = explain_tree_error(cyclic, "node", "parent", "value")
    assert problem is not None
    with pytest.raises(ValueError) as excinfo:
        _sun(cyclic)
    assert str(excinfo.value) == problem
    # ...and None for a tree that is fine, which is what lets the app fall through.
    assert explain_tree_error(_tree(), "node", "parent", "value") is None


def test_sunburst_rejects_a_non_numeric_value_column():
    # `_sizable` is evaluated for EVERY node, internal ones included, so a text column raises
    # uniformly rather than raising or not depending on the tree's shape — boxplot's contract.
    df = pd.DataFrame({"node": ["a", "b"], "parent": [None, "a"], "value": ["x", "y"]})
    with pytest.raises(ValueError):
        _sun(df)


def test_sunburst_serializes_and_resolves_the_sunburst_module():
    # The only test that can see the traps: highcharts-core accepts several of these keys and
    # then silently drops them, so only the emitted JS proves they survived.
    from highcharts_builder import make_chart

    chart = make_chart(_tree(), "sunburst", "node", ["value"], parent_col="parent")
    js = chart.to_js_literal()
    assert js
    for token in ("type: 'sunburst'", "allowTraversingTree", "colorVariation", "id:"):
        assert token in js, f"{token} did not survive serialization"
    # colorByPoint must appear NOWHERE. In `levels` it is silently DROPPED (the canonical
    # Highcharts recipe, and useless to us); at series level it SURVIVES but is the wrong
    # option — it would hand every point its own hue and destroy the inheritance. Pinned like
    # sankey's nodeFormat and boxplot's fillColor. `allowDrillToNode` is the dropped alias.
    assert "colorByPoint" not in js and "allowDrillToNode" not in js
    # The module is resolved by highcharts-core itself, from the options shape — nothing in
    # this repo registers it, so only this can prove it. And sunburst needs no highcharts-more.
    tags = chart.get_script_tags(as_str=True)
    assert "modules/sunburst.js" in tags
    assert "highcharts-more" not in tags


def test_sunburst_light_mode_shape():
    # Pin the choices nothing else guards, and prove the dark-only key is absent (so the dark
    # test below is meaningful).
    opts = _sun()
    assert opts["legend"]["enabled"] is False
    sb = opts["plotOptions"]["sunburst"]
    assert set(sb) == {"allowTraversingTree", "cursor", "levels", "dataLabels"}
    assert "borderColor" not in sb


def test_sunburst_dark_mode_dissolves_the_sector_borders():
    # Sector borders default to the background variable, which the color-scheme pin holds at
    # WHITE in both themes — so in dark mode every sector is ringed white (verified by
    # rendering). Dissolve them into the dark background, as pie, treemap and sankey dissolve
    # their gaps. Nothing else flips: the labels ride `contrast` and the hues read on both.
    opts = _sun(dark=True)
    sb = opts["plotOptions"]["sunburst"]
    assert sb["borderColor"] == "#0f172a"  # == _DARK_CHROME["bg"]
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    points = _points(opts)
    assert points[0]["color"] == DEFAULT_COLORS[0]  # ring-1 hues unchanged
    assert points[-1]["color"] == "#94a3b8"  # ...and the root's


# --------------------------------------------------------------------------- #
# Xrange — a Gantt timeline: bars with EXTENT along x, on lanes down the y axis
# --------------------------------------------------------------------------- #
def _plan() -> pd.DataFrame:
    """Two lanes, one of them holding TWO bars (so the per-lane hue has something to prove),
    plus a milestone. Dates as ISO-8601 STRINGS — an object column, which is what read_csv
    hands back and what `_coordinates` must sniff."""
    return pd.DataFrame(
        {
            "lane": ["Design", "Build", "Build", "Launch"],
            "start": ["2026-01-05", "2026-02-01", "2026-04-01", "2026-06-01"],
            "end": ["2026-02-10", "2026-03-20", "2026-04-20", "2026-06-01"],
        }
    )


def _xr(df: pd.DataFrame | None = None, **kwargs) -> dict:
    return build_options(
        df if df is not None else _plan(),
        "xrange",
        "lane",
        ["start"],
        end_col="end",
        **kwargs,
    )


def _bars(opts: dict) -> list[dict]:
    return opts["series"][0]["data"]


def test_xrange_builds_one_bar_per_row_on_lanes_down_the_y_axis():
    opts = _xr()
    assert opts["chart"]["type"] == "xrange"
    # Lanes are the categories of the Y axis (x_col is NOT an x axis here), in
    # first-appearance order, deduplicated — "Build" holds two bars but is one lane.
    assert opts["yAxis"]["categories"] == ["Design", "Build", "Launch"]
    # A Gantt reads DOWN the page in plan order; Highcharts' own default runs bottom-up.
    assert opts["yAxis"]["reversed"] is True
    # Highcharts titles a category y-axis "Values" unless explicitly CLEARED (None does not
    # do it — verified by rendering); a lane is a name, not a value.
    assert opts["yAxis"]["title"] == {"text": ""}
    bars = _bars(opts)
    assert len(bars) == 4
    # `y` is a POSITION into `categories`, not a value — boxplot's positional trick.
    assert [b["y"] for b in bars] == [0, 1, 1, 2]
    assert [b["name"] for b in bars] == ["Design", "Build", "Build", "Launch"]


def test_xrange_iso_date_strings_become_a_datetime_axis_in_epoch_millis():
    # THE EPOCH PIN, and it guards a regression that is silent and catastrophic. Pandas 3
    # returns `datetime64[us]` from to_datetime (NOT the `[ns]` that the obvious
    # `.astype("int64") // 1_000_000` assumes), so that divisor renders 2026-01-05 as
    # 1970-01-16: every bar in the correct RELATIVE order at hopelessly wrong ABSOLUTE dates,
    # drawn confidently, with no error anywhere. `_epoch_millis` normalizes the unit BEFORE
    # taking the int64 view, which is why this number is exact.
    opts = _xr()
    assert opts["xAxis"]["type"] == "datetime"
    bars = _bars(opts)
    assert bars[0]["x"] == 1767571200000.0  # 2026-01-05T00:00:00Z, to the millisecond
    assert bars[0]["x2"] == 1770681600000.0  # 2026-02-10
    assert pd.to_datetime(bars[0]["x"], unit="ms").date() == date(2026, 1, 5)


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(lambda s: pd.Series(s, dtype=object), id="iso_strings"),
        pytest.param(lambda s: pd.to_datetime(pd.Series(s)), id="datetime64_us"),
        pytest.param(
            lambda s: pd.to_datetime(pd.Series(s)).astype("datetime64[s]"), id="dt64_s"
        ),
        pytest.param(
            lambda s: pd.to_datetime(pd.Series(s)).dt.tz_localize("America/New_York"),
            id="tz_aware",
        ),
    ],
)
def test_xrange_epoch_millis_are_resolution_independent(make):
    # The same instant must serialize to the same millis whatever RESOLUTION or timezone the
    # column arrives in — object strings, datetime64[us] (to_datetime's answer), datetime64[s]
    # (read_csv's), or a tz-aware column (an ISO CSV carrying an offset, which would raise
    # outright without the UTC conversion). A hardcoded divisor is right for exactly one of
    # these and wrong by 1e3 or 1e6 for the others.
    df = pd.DataFrame(
        {
            "lane": ["a"],
            "start": make(["2026-01-05"]),
            "end": make(["2026-02-10"]),
        }
    )
    bars = _bars(_xr(df))
    # tz-aware New York is UTC-5 in January, so its midnight is 05:00Z — the same INSTANT,
    # correctly shifted to UTC, not the same wall clock reinterpreted.
    tz_aware = isinstance(df["start"].dtype, pd.DatetimeTZDtype)
    offset = 5 * 3600 * 1000 if tz_aware else 0
    assert bars[0]["x"] == 1767571200000.0 + offset


def test_xrange_numbers_stay_numbers_and_get_no_datetime_axis():
    # THE EPOCH TRAP, mirrored — and the reason `_coordinates` is dtype-FIRST. Bare
    # `pd.to_datetime(12)` does not fail; it returns 1970-01-01T00:00:00.000000012. So a
    # "try dates, fall back to numbers" sniff would silently move a column of sprint numbers
    # to an instant at the epoch. A numeric dtype is never shown to a date parser at all.
    df = pd.DataFrame({"lane": ["a", "b"], "start": [12, 20], "end": [18, 24]})
    opts = _xr(df)
    assert "type" not in opts["xAxis"]  # a linear axis, not a datetime one
    bars = _bars(opts)
    assert [(b["x"], b["x2"]) for b in bars] == [(12.0, 18.0), (20.0, 24.0)]


@pytest.mark.parametrize(
    ("values", "kind"),
    [
        # Numeral STRINGS are numbers, not dates: ISO-8601 rejects "12", so no bespoke regex
        # is needed to keep them out of the date branch.
        (["12", "18"], "number"),
        (["2026-01-05", "2026-02-10"], "date"),
        # A DST-crossing column: `errors="coerce"` alone RAISES "Mixed timezones detected" on
        # this (verified), which would be a traceback in count_marks — hence `utc=True`.
        (["2026-03-06T12:00:00-05:00", "2026-03-10T12:00:00-04:00"], "date"),
    ],
)
def test_coordinates_sniffs_a_column_kind(values, kind):
    from highcharts_builder import _coordinates

    assert _coordinates(pd.Series(values))[1] == kind


@pytest.mark.parametrize(
    "values",
    [
        # THE LANDING-SAMPLE TRAP. Bare `pd.to_datetime(["Jan","Feb"])` SUCCEEDS, returning
        # YEAR 1 AD (verified) — and this is `_revenue_vs_cost`'s `month` column, the first
        # entry in SAMPLES and so the app's landing dataset. A permissive sniff would offer it
        # as a date axis on the page you see when you open the app. `format="ISO8601"` is what
        # rejects it.
        ["Jan", "Feb", "Mar"],
        [
            "00:00",
            "01:00",
        ],  # ...and these parse to TODAY'S DATE under the default parser
        ["Engineering", "Design"],
        ["13/01/2026", "14/01/2026"],  # a real date, but not ISO-8601
    ],
)
def test_coordinates_rejects_a_column_that_is_neither_dates_nor_numbers(values):
    from highcharts_builder import _COORD_NEITHER, _coordinates

    assert _coordinates(pd.Series(values))[1] == _COORD_NEITHER


@pytest.mark.parametrize(
    ("values", "kind"),
    [
        # A MIXED object column is decided by MAJORITY — a column is one kind or the other,
        # and a few stray cells of the other kind are typos, not a second axis. The losers
        # coerce to NaN and drop their rows as missing data.
        (["2026-01-05", "2026-02-01", "12"], "date"),  # 2 dates beat 1 number
        (["2026-01-05", "12", "13"], "number"),  # 2 numbers beat 1 date
        # A TIE goes to NUMBER (a strict `>`), and that is the safe way to break it: a date
        # read as a number leaves a visibly missing bar, while a number read as a date would
        # silently place it at the epoch — the failure this function's whole ordering exists
        # to prevent.
        (["2026-01-05", "12"], "number"),
    ],
)
def test_coordinates_breaks_a_mixed_column_by_majority_and_a_tie_toward_number(
    values, kind
):
    from highcharts_builder import _coordinates

    assert _coordinates(pd.Series(values))[1] == kind


@pytest.mark.parametrize(
    ("values", "kind"),
    [
        # Dtypes a real CSV or a hand-built frame can arrive as, none of which may raise or
        # mis-sniff. An all-missing column is "empty" — NOT the kind its dtype suggests, which
        # is the trap: an all-NaT column is still datetime64 and an all-NaN one is still
        # float64, so a dtype-only answer would have them claiming an axis they know nothing
        # about (see the empty-column test below).
        (pd.Series([12, 18], dtype="Int64"), "number"),  # pandas nullable
        (pd.Series(["2026-01-05"], dtype="string[pyarrow]"), "date"),  # arrow-backed
        (pd.Series([pd.NaT, pd.NaT], dtype="datetime64[ns]"), "empty"),
        (pd.Series([None, None], dtype=object), "empty"),
        (pd.Series([], dtype=float), "empty"),  # a row-less frame's column
    ],
)
def test_coordinates_survives_the_dtypes_a_real_frame_arrives_as(values, kind):
    from highcharts_builder import _coordinates

    assert _coordinates(values)[1] == kind


@pytest.mark.parametrize(
    "blank",
    [
        pytest.param(lambda n: [None] * n, id="all_none"),
        pytest.param(lambda n: [float("nan")] * n, id="all_nan_float64"),
        pytest.param(
            lambda n: pd.Series([pd.NaT] * n, dtype="datetime64[ns]"), id="all_nat"
        ),
    ],
)
def test_xrange_an_empty_coordinate_column_is_missing_data_not_a_contradiction(blank):
    # An unfilled column is MISSING DATA — every row drops, the chart comes out empty — and it
    # must not be mistaken for a KIND. The tempting shortcut folds "nothing present" into
    # `_COORD_NUMBER`, and it is tempting precisely because it looks true: a blank CSV column
    # arrives as all-NaN float64, so `is_numeric_dtype` says "number" with total confidence.
    # That phantom number then collides with a real DATE partner and raises the axis-mismatch
    # message — telling the user their empty End column "reads as numbers", which is both FALSE
    # and unactionable.
    #
    # And it is not a corner case: this is a Gantt template whose end dates nobody has filled in
    # yet, straight out of read_csv. The bug was also ASYMMETRIC — an empty column beside a
    # NUMERIC partner agreed by coincidence and worked — so only the date case, the type's
    # headline use, was broken.
    for start, end in (
        (["2026-01-05", "2026-02-01"], blank(2)),  # blank END beside a date start
        (blank(2), ["2026-01-05", "2026-02-01"]),  # ...and the mirror
        (blank(2), blank(2)),  # both
    ):
        df = pd.DataFrame({"lane": ["a", "b"], "start": start, "end": end})
        opts = _xr(df)
        assert _bars(opts) == []  # every row dropped, as missing data
        assert count_marks(df, "xrange", "lane", ["start"], end_col="end") == 0
        assert (
            explain_xrange_error(df, "lane", "start", "end") is None
        )  # NOT a contradiction


def test_xrange_an_empty_column_does_not_hide_a_real_axis_mismatch():
    # The other side of the fix: an empty column abstains from the vote, it does not veto it.
    # Two columns that genuinely disagree must still raise.
    df = pd.DataFrame({"lane": ["a"], "start": ["2026-01-05"], "end": [7]})
    with pytest.raises(ValueError, match="must be the same kind"):
        build_options(df, "xrange", "lane", ["start"], end_col="end")


def test_xrange_epoch_millis_span_dates_outside_the_nanosecond_range():
    # `datetime64[ns]` overflows outside 1677..2262, which is why `_epoch_millis` pins the
    # unit to [ms] rather than leaning on to_datetime's default: a medieval start date and a
    # far-future end date must both survive, not raise.
    df = pd.DataFrame({"lane": ["a"], "start": ["1400-01-01"], "end": ["2300-01-01"]})
    bars = _bars(_xr(df))
    assert len(bars) == 1
    assert bars[0]["x"] < 0 < bars[0]["x2"]  # before and after the epoch


def test_xrange_builds_under_warnings_as_errors():
    # Pins `format="ISO8601"` from the other side: the bare `pd.to_datetime` this replaced
    # emits a format-inference UserWarning on every object column, which under `-W error`
    # (or a stricter CI) would fail. The only way this assertion is observable.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert len(_bars(_xr())) == 4
        assert count_marks(_plan(), "xrange", "lane", ["start"], end_col="end") == 4


def test_xrange_keeps_a_zero_length_bar_as_a_milestone_and_floors_it():
    # A launch date / deadline / same-day task — one of the commonest Gantt rows. Highcharts
    # draws NOTHING for it unaided (verified by rendering: x == x2 left an empty lane), so
    # without a floor it would be a mark the KPI counts and the chart never draws. `_sizable`
    # keeps its zero for the same kind of reason; here the floor is what makes keeping it
    # honest, and it must survive serialization (this repo has been bitten three times by
    # options that validate and then silently vanish).
    opts = _xr()
    launch = _bars(opts)[-1]
    assert launch["name"] == "Launch" and launch["x"] == launch["x2"]
    assert opts["plotOptions"]["xrange"]["minPointLength"] == 3
    js = make_chart(_plan(), "xrange", "lane", ["start"], end_col="end").to_js_literal()
    assert js and "minPointLength" in js


def test_xrange_drops_a_backwards_bar():
    # An interval that ends before it begins. Left in, Highcharts draws a bar spanning the
    # ENTIRE axis (verified by rendering) — not a visible error but a confident, plausible lie
    # that reads as the longest task in the project. It is the xrange counterpart of
    # sunburst's silent re-parenting, and it DROPS rather than raises for `_sizable`'s reason:
    # there is a right drawing (nothing), unlike a cycle, where every alternative is a lie.
    df = pd.DataFrame(
        {
            "lane": ["ok", "backwards"],
            "start": ["2026-02-01", "2026-05-01"],
            "end": ["2026-03-01", "2026-01-01"],
        }
    )
    opts = _xr(df)
    assert [b["name"] for b in _bars(opts)] == ["ok"]
    # ...and the lane it would have occupied is gone from the axis entirely. A lane holds
    # 0..n bars, so unlike a boxplot group (which IS its mark, and survives as an
    # EnforcedNull box) there is nothing to null out: an empty labelled axis row is exactly
    # the phantom this drop exists to prevent.
    assert opts["yAxis"]["categories"] == ["ok"]
    assert count_marks(df, "xrange", "lane", ["start"], end_col="end") == 1


def test_xrange_drops_a_non_finite_start_or_end():
    # `end >= start` ALONE is not enough, and this is the hole it leaves: `10 > -inf` is True,
    # so a -inf start (reachable from a plain CSV via `1e400`) would sail through and put the
    # bare token `inf` in the emitted JS — the ReferenceError / HTTP-400 the whole non-finite
    # doctrine exists to prevent. Both ends must be `_plottable` BEFORE they are compared.
    # The END channel is the one `non_finite_frame` cannot reach (an infinite end would drop
    # its only surviving row), so it is covered here.
    inf = float("inf")
    df = pd.DataFrame(
        {
            "lane": ["neg_inf_start", "pos_inf_end", "nan_start", "ok"],
            "start": [-inf, 1.0, float("nan"), 5.0],
            "end": [10.0, inf, 4.0, 9.0],
        }
    )
    opts = _xr(df)
    assert [b["name"] for b in _bars(opts)] == ["ok"]
    js = make_chart(df, "xrange", "lane", ["start"], end_col="end").to_js_literal()
    assert js and "inf" not in js.lower()


def test_xrange_drops_an_unparseable_date_cell_but_keeps_the_column():
    # One typo must not condemn the column. An unparseable cell coerces to NaT -> NaN, which
    # is missing DATA and drops its row — while a column where NOTHING parses is a column of
    # the wrong KIND and is a contradiction (see the raise tests below). That is
    # `_sunburst_tree`'s split, applied to a coordinate column.
    df = pd.DataFrame(
        {
            "lane": ["ok", "typo"],
            "start": ["2026-01-05", "2026-13-45"],
            "end": ["2026-02-10", "2026-03-01"],
        }
    )
    opts = _xr(df)
    assert opts["xAxis"]["type"] == "datetime"  # still a date column
    assert [b["name"] for b in _bars(opts)] == ["ok"]


def test_spannable_decides_the_four_boundary_pairs():
    from highcharts_builder import _spannable

    assert _spannable(1.0, 2.0)  # a real bar
    assert _spannable(2.0, 2.0)  # a milestone: KEPT (floored to a sliver)
    assert not _spannable(2.0, 1.0)  # backwards: dropped
    assert not _spannable(float("-inf"), 10.0)  # the finiteness hole
    assert not _spannable(10.0, float("inf"))
    assert not _spannable(float("nan"), 1.0)


def test_xrange_colors_every_bar_in_a_lane_alike_and_never_uses_color_by_point():
    # A lane's hue is its arbitrary IDENTITY, like a pie slice's — the opposite of waterfall's
    # semantic red-means-loss — so it reads from the OVERRIDABLE palette. It must be seeded
    # per POINT, and here the trap is the mirror of sunburst's: where sunburst's
    # `levels[].colorByPoint` is silently DROPPED, xrange's series-level one SURVIVES — and is
    # the wrong option. It would hand every BAR its own hue, so Build's two phases would come
    # out two colors and the lane would stop reading as one thing.
    bars = _bars(_xr())
    design, build_a, build_b, launch = bars
    assert build_a["color"] == build_b["color"]  # one lane, one hue
    assert design["color"] == DEFAULT_COLORS[0]
    assert build_a["color"] == DEFAULT_COLORS[1]
    assert launch["color"] == DEFAULT_COLORS[2]
    js = make_chart(_plan(), "xrange", "lane", ["start"], end_col="end").to_js_literal()
    assert js and "colorByPoint" not in js


def test_xrange_takes_a_custom_palette_and_a_short_one_cycles():
    # A short custom palette must not IndexError (the `_BOXPLOT_OUTLIER_COLOR` concern) — three
    # lanes over a two-color palette wrap back to the first.
    bars = _bars(_xr(colors=["#111111", "#222222"]))
    assert [b["color"] for b in bars] == ["#111111", "#222222", "#222222", "#111111"]


def test_xrange_tooltip_names_the_point_and_formats_the_dates():
    # {point.name}, NOT waterfall's {point.category}. This is not a stylistic echo: it is
    # waterfall's FIX and xrange's BUG. {point.category} reads the X axis, and an xrange's
    # categories are on the Y, so it renders the raw x value — a tooltip reading
    # "1767571200000" (verified by rendering). And a datetime axis must FORMAT its endpoints,
    # or they print as raw epoch millis too.
    tip = _xr()["tooltip"]["pointFormat"]
    assert "{point.name}" in tip and "{point.category}" not in tip
    assert "{point.x:%Y-%m-%d}" in tip and "{point.x2:%Y-%m-%d}" in tip
    # A numeric axis has no dates to format, so it prints the bare coordinates.
    numeric = pd.DataFrame({"lane": ["a"], "start": [12], "end": [18]})
    assert (
        _xr(numeric)["tooltip"]["pointFormat"]
        == "<b>{point.name}</b><br/>{point.x} → {point.x2}"
    )


def test_xrange_carries_no_data_labels():
    # The one mark-bearing type that prints nothing in the mark, and needs no gate constant
    # either. The five that DO print a value in the mark do it because the value can be read
    # against no axis (an angle, an area, a link's width, a bar floating above an invisible
    # running total). An xrange bar's two ends BOTH land on a real, ticked x axis that renders
    # in the Static PNG too — column/bar's case. And there is no second identity to print: the
    # lane name IS the y-axis category (labelling the bar just repeats it — verified by
    # rendering).
    assert "dataLabels" not in _xr()["plotOptions"]["xrange"]


def test_xrange_requires_an_end_column():
    with pytest.raises(ValueError, match="requires an end column"):
        build_options(_plan(), "xrange", "lane", ["start"])


def test_xrange_rejects_the_start_column_as_the_end_column():
    # A bar's two ends, like sankey's source/target and sunburst's node/parent. It must be a
    # guard rather than a tolerated oddity because it fails SILENTLY: every bar would be
    # zero-length, so the chart would come back as a column of milestone slivers.
    with pytest.raises(ValueError, match="cannot also be the end column"):
        build_options(_plan(), "xrange", "lane", ["start"], end_col="start")


def test_xrange_allows_x_in_y():
    # x_col IS free to repeat a coordinate column: the lanes are then named by their own start
    # number — odd, well-defined, drawable. Scatter's x-in-y tolerance, and the reason xrange
    # stays OUT of X_IN_Y_GUARD_TYPES (its x_col names a lane on the Y axis, and end_col isn't
    # in y_cols at all, so that rule cannot even express xrange's real collision).
    df = pd.DataFrame({"start": [1.0, 2.0], "end": [5.0, 6.0]})
    opts = build_options(df, "xrange", "start", ["start"], end_col="end")
    assert opts["yAxis"]["categories"] == ["1", "2"]  # _node_key: "1", not "1.0"


@pytest.mark.parametrize(
    ("start", "end", "match"),
    [
        ("lane", "end", "neither dates nor numbers"),  # a column of task names
        ("start", "lane", "neither dates nor numbers"),
    ],
)
def test_xrange_a_non_coordinate_column_raises(start, end, match):
    with pytest.raises(ValueError, match=match):
        build_options(_plan(), "xrange", "lane", [start], end_col=end)


def test_xrange_a_date_start_beside_a_numeric_end_raises():
    # Both ends of a bar sit on ONE axis, so they must be the same kind. A contradiction with
    # no right drawing — a returned message, raised here.
    df = _plan().assign(sprint=[1, 2, 3, 4])
    with pytest.raises(ValueError, match="must be the same kind"):
        build_options(df, "xrange", "lane", ["start"], end_col="sprint")


@pytest.mark.parametrize("end", ["lane", "sprint"])
def test_xrange_explain_returns_the_message_build_options_raises(end):
    # The `explain_tree_error` contract: the builder owns the coordinate relationship, so it
    # owns the diagnosis, and the app's warning cannot drift from the exception it stands in
    # for. Needed because the interactive path does NOT catch builder errors — and picking a
    # text column for Start, or a date Start beside a numeric End, is reachable through the
    # app's own pickers.
    from highcharts_builder import explain_xrange_error

    df = _plan().assign(sprint=[1, 2, 3, 4])
    problem = explain_xrange_error(df, "lane", "start", end)
    assert problem
    with pytest.raises(ValueError) as excinfo:
        build_options(df, "xrange", "lane", ["start"], end_col=end)
    assert str(excinfo.value) == problem
    # count_marks must stay TOTAL over the same contradiction: it runs ABOVE the app's guards,
    # so a raise here would blow the page up with a traceback before the warning that explains
    # it could render.
    assert count_marks(df, "xrange", "lane", ["start"], end_col=end) == 0


def test_xrange_explain_is_none_when_the_columns_are_fine():
    from highcharts_builder import explain_xrange_error

    assert explain_xrange_error(_plan(), "lane", "start", "end") is None


def test_a_non_coordinate_column_is_unreachable_from_the_app_pickers():
    # Pins the scoping claim the builder's docstrings and CLAUDE.md now make: of the TWO
    # contradictions `explain_xrange_error` reports, only the date-vs-number mismatch is
    # reachable through the app. The other — a column that is neither dates nor numbers — is
    # kept out of the Start/End pickers by `coordinate_columns`, so it is reachable only
    # through the pure builder API.
    #
    # This is a documentation invariant with teeth: if `coordinate_columns` ever started
    # admitting a text column, the app would grow a traceback path AND three prose claims would
    # silently become false at once. Nothing else in the suite would notice.
    import itertools

    from highcharts_builder import coordinate_columns, explain_xrange_error

    offerable = coordinate_columns(_plan())
    assert "lane" not in offerable  # the text column the builder would refuse
    for start, end in itertools.product(offerable, repeat=2):
        if start == end:
            continue  # the Start == End collision, guarded separately
        problem = explain_xrange_error(_plan(), "lane", start, end)
        # Whatever the pickers CAN produce is either drawable or a same-kind mismatch —
        # never the "neither dates nor numbers" message.
        assert problem is None or "must be the same kind" in problem


def test_xrange_count_marks_agrees_with_the_chart_on_the_raw_frame():
    # THE NO-DRIFT PIN, and the subtlest bug in the type. A row's survival LOOKS per-row, so
    # xrange looks like it belongs on count_marks' shared-predicate mask path with
    # treemap/sankey. It does not. The AXIS KIND is a COLUMN-level fact that every row's
    # start/end is read THROUGH — and the two callers do not hold the same column:
    # build_options reaches its branch on the `_label_ok`-FILTERED frame, while count_marks
    # and explain_xrange_error run on the RAW one.
    #
    # This frame is built to expose exactly that. The ONLY garbage cell ("oops") sits on the
    # row whose LANE is missing — so it is dropped for its label before the sniff ever sees
    # it. On the filtered frame the start column is 2 clean dates; on the raw frame it is 2
    # dates and one piece of junk. A raw-frame sniff still calls it a date column (2 date hits
    # beats 0 numeric hits), so the counts happen to agree — but `explain_xrange_error` would
    # be deciding on different evidence than the chart. `_xrange_bars` re-applies `_label_ok`
    # itself and sniffs the SURVIVORS only, which is what makes the two frames byte-identical.
    df = pd.DataFrame(
        {
            "lane": ["a", "b", None],
            "start": ["2026-01-01", "2026-02-01", "oops"],
            "end": ["2026-01-15", "2026-02-15", "2026-03-01"],
        }
    )
    built = _bars(_xr(df))
    assert len(built) == 2
    assert count_marks(df, "xrange", "lane", ["start"], end_col="end") == len(built)
    # And the guard must PASS on this frame, not report a contradiction the builder won't raise.
    from highcharts_builder import explain_xrange_error

    assert explain_xrange_error(df, "lane", "start", "end") is None


def test_xrange_uses_only_first_y_col():
    opts = build_options(_plan(), "xrange", "lane", ["start", "end"], end_col="end")
    assert len(_bars(opts)) == 4


def test_coordinate_columns_offers_numbers_and_dates_but_not_text():
    # Sourced from `_coordinates` itself, so the app's Start/End pickers cannot offer a column
    # the builder would refuse — the can't-drift rule applied to which options appear in a
    # widget. It is what lets the app widen those controls past select_dtypes("number")
    # (invisible to a date column, which is object dtype) without reintroducing the hazard
    # that filter exists to prevent.
    from highcharts_builder import coordinate_columns

    df = pd.DataFrame(
        {
            "lane": ["a", "b"],  # text: not a coordinate
            "month": ["Jan", "Feb"],  # the landing-sample trap: NOT a date
            "start": ["2026-01-05", "2026-02-10"],  # ISO strings: a date
            "parsed": pd.to_datetime(
                ["2026-01-05", "2026-02-10"]
            ),  # datetime64: a date
            "sprint": [12, 18],  # a number
        }
    )
    assert coordinate_columns(df) == ["start", "parsed", "sprint"]
    # A superset of the numeric columns, which is the whole point.
    assert set(df.select_dtypes("number")) <= set(coordinate_columns(df))


def test_xrange_serializes_and_resolves_the_xrange_module():
    chart = make_chart(_plan(), "xrange", "lane", ["start"], end_col="end")
    js = chart.to_js_literal()
    assert js
    # x2 is the whole type — a mark with EXTENT — and unlike sankey's nodeFormat, boxplot's
    # fillColor and sunburst's levels[].colorByPoint, it DOES survive. Only the emitted JS can
    # show that, which is why it is pinned here rather than on the options dict.
    for token in ("type: 'xrange'", "x2:", "reversed", "minPointLength", "pointWidth"):
        assert token in js, f"{token} did not survive serialization"
    assert "type: 'datetime'" in js
    # The module is resolved by highcharts-core itself, from the options shape — nothing in
    # this repo registers it. And xrange needs no highcharts-more (unlike bubble, radar,
    # boxplot and waterfall).
    tags = chart.get_script_tags(as_str=True)
    assert "modules/xrange.js" in tags
    assert "highcharts-more" not in tags


def test_xrange_light_mode_shape():
    # Pin the choices nothing else guards, and prove the dark-only key is absent (so the dark
    # test below is meaningful).
    opts = _xr()
    assert opts["legend"]["enabled"] is False
    xr = opts["plotOptions"]["xrange"]
    assert set(xr) == {"pointWidth", "minPointLength"}
    assert "borderColor" not in xr


def test_xrange_dark_mode_dissolves_the_bar_borders():
    # Xrange joins column/bar here and NOT waterfall — the other bar-shaped type, which needs
    # the opposite treatment. That was MEASURED, not inferred from the shared bar base class:
    # waterfall is the standing proof the inference is unsound, its border being a fixed
    # #333333. Pixel-scanning a dark-mode xrange PNG off the export server puts its default
    # border at pure #ffffff — the background variable, exactly column/bar's case — so every
    # bar is ringed white until it is dissolved into the dark background.
    opts = _xr(dark=True)
    assert (
        opts["plotOptions"]["xrange"]["borderColor"] == "#0f172a"
    )  # _DARK_CHROME["bg"]
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    # The lane hues are unchanged: like the shared palette, they read on both backgrounds.
    assert _bars(opts)[0]["color"] == DEFAULT_COLORS[0]


def test_release_plan_sample_builds_an_xrange_chart():
    from sample_data import _release_plan

    df = _release_plan()
    opts = build_options(df, "xrange", "workstream", ["start"], end_col="end")
    assert opts["xAxis"]["type"] == "datetime"
    # Backend and Frontend each run twice, with a gap — so the sample proves the per-lane hue.
    assert opts["yAxis"]["categories"] == [
        "Discovery",
        "Design",
        "Backend",
        "Frontend",
        "QA",
        "Launch",
    ]
    bars = _bars(opts)
    assert len(bars) == 8  # every row draws, the milestone included
    backend = [b["color"] for b in bars if b["name"] == "Backend"]
    assert len(backend) == 2 and len(set(backend)) == 1
    assert count_marks(df, "xrange", "workstream", ["start"], end_col="end") == 8


# --------------------------------------------------------------------------- #
# Columnrange — floating bars spanning [low, high] per category
# --------------------------------------------------------------------------- #
def _range_df() -> pd.DataFrame:
    """Four categories, each a low/high pair. Apr is INVERTED (high < low) so the keep-and-span
    policy has something to prove; the rest are ordinary low < high ranges."""
    return pd.DataFrame(
        {
            "month": ["Jan", "Feb", "Mar", "Apr"],
            "low": [-2.0, 1.0, 4.0, 8.0],
            "high": [
                8.0,
                12.0,
                18.0,
                -3.0,
            ],  # Apr: high < low — kept, spans [min, high]
        }
    )


def _cr(df: pd.DataFrame | None = None, **kwargs) -> dict:
    return build_options(
        df if df is not None else _range_df(),
        "columnrange",
        "month",
        ["low"],
        high_col="high",
        **kwargs,
    )


def _ranges(opts: dict) -> list:
    return opts["series"][0]["data"]


def test_columnrange_builds_one_bar_per_category_as_low_high_pairs():
    opts = _cr()
    assert opts["chart"]["type"] == "columnrange"
    # x_col is a genuine category X axis (the bars stand ON it, drawn vertically) — column/bar's
    # shape, NOT xrange's, whose lanes are on the Y axis.
    assert opts["xAxis"]["categories"] == ["Jan", "Feb", "Mar", "Apr"]
    # Each point is a `[low, high]` 2-ARRAY matched to categories BY POSITION — the boxplot
    # positional trick, one type over. A numeric-first 2-array is read unambiguously as
    # [low, high] (verified against the round-trip in the serialization test below), so it does
    # NOT collapse the way a `{name, low}` dict would.
    assert _ranges(opts) == [[-2.0, 8.0], [1.0, 12.0], [4.0, 18.0], [8.0, -3.0]]
    # One series, and its legend is off: a single-hue series legends as one useless bullet, and
    # the categories are on the X axis already (xrange's, treemap's, boxplot's reasoning).
    assert len(opts["series"]) == 1
    assert opts["legend"]["enabled"] is False


def test_columnrange_keeps_a_missing_or_non_finite_end_as_a_null_slot():
    # The category-x keep-the-slot family (column/bar/waterfall), applied to a PAIR: a bar needs
    # BOTH ends, so if either is missing (NaN) or non-finite (inf) the whole slot becomes a bare
    # EnforcedNull — a kept category tick with no bar — never a half-drawn range. A bare null, not
    # `{"low": ..., "high": EnforcedNull}`: highcharts-core drops a null out of a point dict, so a
    # partial dict would draw an arbitrary bar. And no bare `inf` reaches the JS (the `_plottable`
    # rule the whole module shares).
    df = pd.DataFrame(
        {
            "month": ["Jan", "Feb", "Mar", "Apr"],
            "low": [-2.0, float("nan"), 4.0, float("inf")],
            "high": [8.0, 12.0, float("nan"), 20.0],
        }
    )
    opts = _cr(df)
    assert _ranges(opts) == [[-2.0, 8.0], EnforcedNull, EnforcedNull, EnforcedNull]
    # The category slots are all KEPT — a null bar still holds its tick (unlike a dropped row).
    assert opts["xAxis"]["categories"] == ["Jan", "Feb", "Mar", "Apr"]
    js = make_chart(
        df, "columnrange", "month", ["low"], high_col="high"
    ).to_js_literal()
    assert js
    for token in ("inf", "nan", "NaN"):
        assert token not in js, f"columnrange emitted a non-finite literal: {token}"


def test_columnrange_keeps_an_inverted_range_spanning_both_values():
    # The vote the user made, and the mirror of xrange's backwards bar. xrange DROPS a bar that
    # ends before it starts, because Highcharts draws it spanning the WHOLE axis — a confident,
    # plausible lie. A columnrange bar is bounded by its two values, so an inverted low/high
    # (Apr's 8 → -3) draws the SAME honest bar as -3 → 8 (verified by rendering), spanning
    # [min, max]. So it is KEPT, order preserved, not dropped and not silently normalized.
    apr = _ranges(_cr())[3]
    assert apr == [8.0, -3.0]  # kept as-is, not swapped, not dropped
    # count_marks counts it, exactly as the chart draws it — all four categories survive.
    assert count_marks(_range_df(), "columnrange", "month", ["low"]) == 4


def test_columnrange_colors_every_bar_one_hue_and_never_uses_color_by_point():
    # A columnrange is ONE measurement across the axis, so every bar takes the single series hue
    # (colors[0]); `colorByPoint` stays OFF (its Highcharts default) — a per-bar hue would assert
    # a categorical identity the categories don't have (the opposite call from pie/treemap/xrange,
    # whose slices/lanes ARE separate identities). So the data carry NO per-point color, and
    # `colorByPoint` appears NOWHERE in the emitted JS.
    opts = _cr()
    assert all(not isinstance(pt, dict) or "color" not in pt for pt in _ranges(opts))
    # The palette is carried and OVERRIDABLE, so a custom palette repaints the bars.
    assert opts["colors"] == list(DEFAULT_COLORS)
    assert _cr(colors=["#abcabc"])["colors"] == ["#abcabc"]
    js = make_chart(
        _range_df(), "columnrange", "month", ["low"], high_col="high"
    ).to_js_literal()
    assert js and "colorByPoint" not in js


def test_columnrange_tooltip_names_the_category_and_the_range():
    # {point.category}, NOT xrange's {point.name}: a columnrange's categories are on the X axis
    # (its bars stand ON it), so {point.category} reads the RIGHT axis — waterfall's fix, not
    # xrange's bug. {point.low}/{point.high} are the two ends; a bare {point.y} would print null.
    tip = _cr()["tooltip"]["pointFormat"]
    assert "{point.category}" in tip
    assert "{point.low}" in tip and "{point.high}" in tip
    assert "{point.name}" not in tip and "{point.y}" not in tip


def test_columnrange_requires_a_high_column():
    with pytest.raises(ValueError, match="requires a high column"):
        build_options(_range_df(), "columnrange", "month", ["low"])


def test_columnrange_rejects_the_low_column_as_the_high_column():
    # A bar's two ends, like xrange's start/end. It must be a guard rather than a tolerated
    # oddity because it fails SILENTLY: every bar would span zero height, a row of hairlines.
    with pytest.raises(ValueError, match="cannot also be the high column"):
        build_options(_range_df(), "columnrange", "month", ["low"], high_col="low")


def test_columnrange_rejects_x_as_a_y_series():
    # columnrange IS in X_IN_Y_GUARD_TYPES (unlike xrange): its x_col is a real category X axis,
    # so x_col == low is the classic x-in-y collision the rule was written for. (x_col == high is
    # not expressible there — high_col isn't in y_cols — but it is a magnitude picked from
    # numeric_cols beside a category x, a scatter-style tolerance, so it needs no guard.)
    with pytest.raises(ValueError, match="cannot also be a y series"):
        build_options(_range_df(), "columnrange", "low", ["low"], high_col="high")


def test_columnrange_uses_only_first_y_col():
    # low = y_cols[0]; any further y columns are ignored (high comes from high_col, not y_cols[1]).
    opts = build_options(
        _range_df(), "columnrange", "month", ["low", "high"], high_col="high"
    )
    assert len(_ranges(opts)) == 4


def test_columnrange_count_marks_counts_drawable_categories():
    # Waterfall's rule without the appended total: one bar per drawable LABEL, the value columns
    # NOT consulted (a missing/inverted range keeps its slot as a null bar and still counts). A
    # row whose LABEL is missing names no category and drops; a row whose VALUE is missing keeps
    # its slot. So the KPI's "Ranges" counts by label, and equals the built data length.
    df = pd.DataFrame(
        {
            "month": ["Jan", None, "Mar"],
            "low": [
                1.0,
                2.0,
                float("nan"),
            ],  # Mar's low is missing -> null slot, still counted
            "high": [5.0, 6.0, 7.0],
        }
    )
    built = _ranges(_cr(df))
    assert built == [
        [1.0, 5.0],
        EnforcedNull,
    ]  # None-label row dropped; Mar kept as a null slot
    assert count_marks(df, "columnrange", "month", ["low"]) == 2 == len(built)


def test_columnrange_serializes_and_resolves_highcharts_more():
    # End to end: the [low, high] pairs must survive `to_js_literal` (NOT collapse like a boxplot
    # dict would) AND resolve `highcharts-more` — from `chart.type` ALONE, like bubble/boxplot/
    # waterfall, and (correcting the plausible guess) NOT a phantom `modules/columnrange.js`. Only
    # the round-trip can show which module a type pulls in; this repo registers none of them.
    chart = make_chart(_range_df(), "columnrange", "month", ["low"], high_col="high")
    js = chart.to_js_literal()
    assert js and "type: 'columnrange'" in js
    # The low/high values reach the JS as array elements (the pair did not collapse to [x, y]).
    for token in ("-2", "8", "12", "18"):
        assert token in js
    tags = chart.get_script_tags(as_str=True)
    assert "highcharts-more" in tags
    assert (
        "modules/columnrange" not in tags
    )  # no such module — it lives in highcharts-more


def test_columnrange_light_mode_shape():
    # Pin the choices nothing else guards, and prove the dark-only key is absent (so the dark
    # test below is meaningful). columnrange emits NO plotOptions at all in light mode — which is
    # also how it "carries no data labels": there is no plotOptions.columnrange to hold any.
    opts = _cr()
    assert opts["legend"]["enabled"] is False
    assert "plotOptions" not in opts  # no dataLabels, no light-mode border


def test_columnrange_dark_mode_dissolves_the_bar_borders():
    # columnrange joins column/bar/xrange here and NOT waterfall — MEASURED, not inferred from
    # the shared bar base class (waterfall is the standing proof that inference is unsound, its
    # border being a fixed #333333). A columnrange bar's default border is the background
    # variable, pure white, which the color-scheme pin keeps white in dark mode, ringing every
    # bar until it is dissolved into the dark background.
    opts = _cr(dark=True)
    assert (
        opts["plotOptions"]["columnrange"]["borderColor"] == "#0f172a"
    )  # _DARK_CHROME bg
    assert opts["chart"]["backgroundColor"] == "#0f172a"
    # The single hue is unchanged: like the shared palette, it reads on both backgrounds.
    assert _ranges(opts)[0] == [-2.0, 8.0]


def test_temperature_range_sample_builds_a_columnrange_chart():
    from sample_data import _temperature_range

    df = _temperature_range()
    opts = build_options(
        df, "columnrange", "month", ["record_low"], high_col="record_high"
    )
    assert opts["chart"]["type"] == "columnrange"
    ranges = _ranges(opts)
    assert len(ranges) == 12  # one bar per month
    # Every low sits below its high — a clean demo range, no inverted or missing slots.
    assert all(low < high for low, high in ranges)
    assert count_marks(df, "columnrange", "month", ["record_low"]) == 12


# --------------------------------------------------------------------------- #
# Gauge — concentric rings, each one COLUMN reduced to one number
# --------------------------------------------------------------------------- #
@pytest.fixture
def bookings_frame() -> pd.DataFrame:
    """Four regions, eight weeks — the shape a gauge reads: comparable measures on one scale.

    ``emea`` has a reporting gap (the drop happens INSIDE the aggregate) and ``partner_deals``
    is entirely unreported, which is the type's headline trap: pandas sums it to ``0.0``.
    """
    blank = float("nan")
    return pd.DataFrame(
        {
            "week": ["W01", "W02", "W03", "W04", "W05", "W06", "W07", "W08"],
            "north": [42, 51, 47, 58, 61, 55, 63, 59],  # sum 436, mean 54.5, max 63
            "south": [38, 35, 44, 41, 39, 46, 43, 48],  # sum 334
            "emea": [22, 27, 25, blank, blank, 31, 34, 36],  # sum 175, over SIX weeks
            "partner_deals": [blank] * 8,  # nothing reported
        }
    )


def _gauge(df, y_cols, **kwargs) -> dict:
    return build_options(df, "solidgauge", None, list(y_cols), **kwargs)


def _rings(opts: dict) -> list[dict]:
    return opts["series"]


def _reading(ring: dict):
    """The one number a ring draws — or EnforcedNull when its column held no data."""
    (point,) = ring["data"]
    return point if point is EnforcedNull else point["y"]


def test_gauge_draws_one_ring_per_column_reduced_to_one_number(bookings_frame):
    opts = _gauge(bookings_frame, ["north", "south", "emea"], agg="sum")
    rings = _rings(opts)
    assert [r["name"] for r in rings] == ["north", "south", "emea"]
    assert [_reading(r) for r in rings] == [436.0, 334.0, 175.0]
    # emea's 175 is over SIX weeks, not eight: the gap drops INSIDE the aggregate.
    assert opts["chart"]["type"] == "solidgauge"


@pytest.mark.parametrize(
    ("agg", "expected"),
    [
        ("sum", 436.0),
        ("mean", 54.5),
        ("median", 56.5),
        ("min", 42.0),
        ("max", 63.0),
        ("last", 59.0),
    ],
)
def test_gauge_every_aggregation_reduces_its_column(bookings_frame, agg, expected):
    # All six, so a new reducer cannot be added without a reading to prove it.
    assert GAUGE_AGGREGATIONS == ("sum", "mean", "median", "min", "max", "last")
    (ring,) = _rings(_gauge(bookings_frame, ["north"], agg=agg))
    assert _reading(ring) == expected


@pytest.mark.parametrize("agg", GAUGE_AGGREGATIONS)
def test_gauge_an_empty_column_is_no_data_not_a_zero_total(bookings_frame, agg):
    # THE TYPE'S HEADLINE TRAP, swept over every reduction because only ONE of them lies —
    # which makes it worse, not better: the bug would live in `sum` alone and look like a
    # rounding quirk in the other five.
    assert (
        bookings_frame["partner_deals"].sum() == 0.0
    )  # <- pandas' answer: the IDENTITY
    assert pd.Series([], dtype="float64").sum() == 0.0  # <- and for an empty column too
    # A gauge that believed pandas would draw an emphatic, entirely fictional ZERO ring at the
    # dial's floor — a confident CLAIM ("we booked nothing") where the truth is "nobody
    # reported". The empty test runs ABOVE the reducer, so it is unrepresentable, not
    # special-cased.
    (ring,) = _rings(_gauge(bookings_frame, ["partner_deals"], agg=agg))
    assert _reading(ring) is EnforcedNull


def test_gauge_an_empty_ring_is_kept_not_dropped(bookings_frame):
    # boxplot's all-missing-group rule — and here it is geometrically FORCED. The radii are a
    # function of the SELECTION, so dropping a ring would resize and recolour every ring below
    # it, and the KPI ("Series plotted") would count a ring the chart never drew. Keeping it is
    # what makes marks == series == len(y_cols) an invariant, which is why gauge needs no
    # MARK_METRICS entry and no count_marks rule.
    cols = ["north", "south", "emea", "partner_deals"]
    rings = _rings(_gauge(bookings_frame, cols, agg="sum"))
    assert len(rings) == len(cols)
    assert [r["name"] for r in rings] == cols
    assert _reading(rings[3]) is EnforcedNull
    # The null ring is a BARE EnforcedNull, not {"y": EnforcedNull, ...}: highcharts-core drops
    # a null `y` out of a point dict entirely, leaving a point with no value at all.
    assert rings[3]["data"] == [EnforcedNull]
    js = make_chart(bookings_frame, "solidgauge", None, cols).to_js_literal()
    assert js and "data:[[null]]" in "".join(js.split())


def test_gauge_the_empty_ring_is_still_named_in_the_legend(bookings_frame):
    # A null point draws no arc AND no data label, so the legend is the ONLY thing that names
    # it. That is why gauge is the one type whose legend is not redundant.
    opts = _gauge(bookings_frame, ["north", "partner_deals"])
    assert opts["legend"]["enabled"] is True
    assert all(r["showInLegend"] is True for r in _rings(opts))


def test_gauge_drops_non_finite_observations_before_reducing():
    # An inf cannot be summed with anything (it poisons the total), and it cannot be
    # SERIALIZED: `to_js_literal` emits the bare token `inf`, which is not valid JS.
    df = pd.DataFrame({"v": [10.0, float("inf"), 20.0, float("nan")]})
    (ring,) = _rings(_gauge(df, ["v"], agg="sum"))
    assert _reading(ring) == 30.0  # the two finite ones


def test_gauge_a_reduction_that_overflows_becomes_a_null_ring():
    # Gauge is the SECOND type (after boxplot) that does ARITHMETIC on the values, so it can
    # manufacture a non-finite reading out of finite inputs — boxplot's overflow lesson, one
    # type over. 1e308 parses out of a plain CSV.
    df = pd.DataFrame({"v": [1e308, 1e308]})
    with (
        warnings.catch_warnings()
    ):  # numpy warns on the overflow; that IS the point here
        warnings.simplefilter("ignore", RuntimeWarning)
        assert df["v"].sum() == float("inf")  # finite inputs, non-finite output
    (ring,) = _rings(_gauge(df, ["v"], agg="sum"))
    assert _reading(ring) is EnforcedNull
    js = make_chart(df, "solidgauge", None, ["v"], agg="sum").to_js_literal()
    assert js and "inf" not in js.lower()


def test_gauge_last_reads_the_last_KNOWN_reading():
    # `_finite_values` runs first, so `last` is the last reading that EXISTS, not the last cell
    # (which may be blank — and `float(nan)` would null the whole ring).
    df = pd.DataFrame({"v": [5.0, 7.0, float("nan")]})
    (ring,) = _rings(_gauge(df, ["v"], agg="last"))
    assert _reading(ring) == 7.0


def test_gauge_rejects_a_non_numeric_column_and_an_unknown_aggregation():
    df = pd.DataFrame({"v": ["x", "y"]})
    with pytest.raises(ValueError):
        _gauge(df, ["v"])  # `_finite_values` casts first, as float() does elsewhere
    with pytest.raises(ValueError, match="aggregation"):
        _gauge(pd.DataFrame({"v": [1.0]}), ["v"], agg="mode")


# --- the dial ------------------------------------------------------------------------ #
def test_gauge_dial_is_derived_from_the_readings_not_the_raw_column(bookings_frame):
    # THE OTHER HEADLINE. Under `sum` a reading EXCEEDS every observation in its own column
    # (436 vs a max cell of 63), so a dial derived from the raw column would end at 100 and pin
    # every ring past the end of its own scale — "everyone smashed target", drawn confidently.
    # Reducing FIRST, with the very reduction the rings draw, makes that unrepresentable.
    cols = ["north", "south", "emea"]
    assert bookings_frame[cols].max().max() == 63  # the raw column's ceiling
    opts = _gauge(bookings_frame, cols, agg="sum")
    assert (opts["yAxis"]["min"], opts["yAxis"]["max"]) == (0.0, 500.0)  # 436 -> 500
    # And every reading fits inside its own dial, under EVERY reduction.
    for agg in GAUGE_AGGREGATIONS:
        low, high = gauge_dial(bookings_frame, cols, agg)
        readings = [
            _reading(r)
            for r in _rings(_gauge(bookings_frame, cols, agg=agg))
            if _reading(r) is not EnforcedNull
        ]
        assert all(low <= v <= high for v in readings), agg


@pytest.mark.parametrize(
    ("value", "ceiling"),
    [(436.0, 500.0), (79.0, 100.0), (9.0, 10.0), (0.83, 1.0), (100.0, 100.0)],
)
def test_gauge_dial_rounds_the_ceiling_outward(value, ceiling):
    # A dial ending exactly at the largest reading draws that ring 100% full whatever it holds.
    # "436 of 500" is the only reading a gauge gives, so the 500 has to come from somewhere.
    _low, high = gauge_dial(pd.DataFrame({"v": [value]}), ["v"], "sum")
    assert high == ceiling


def test_gauge_dial_survives_overflow_and_underflow():
    # The two ways the nice-ceiling arithmetic breaks on real input. `2.0 * 1e308` is `inf`,
    # which would put the bare token `inf` in the emitted JS; `10.0 ** -324` is `0.0`, which
    # would leave the dial with no extent at all. In both cases the reading is finite and
    # positive, so it is its own ceiling.
    _low, high = gauge_dial(pd.DataFrame({"v": [1.5e308]}), ["v"], "sum")
    assert math.isfinite(high)
    js = make_chart(
        pd.DataFrame({"v": [1.5e308]}), "solidgauge", None, ["v"]
    ).to_js_literal()
    assert js and "inf" not in js.lower()
    _low, tiny = gauge_dial(pd.DataFrame({"v": [5e-324]}), ["v"], "sum")
    assert tiny > 0


def test_gauge_dial_floors_at_zero_and_an_all_negative_one_sweeps_from_zero():
    # A gauge is read FROM ZERO: an arc's LENGTH is its magnitude. Left unset, Highcharts sweeps
    # each arc from the axis MINIMUM, which INVERTS an all-negative dial — on a -200..0 dial the
    # -40 would draw a LONGER arc than the -155, so the SMALLEST loss would look like the
    # biggest. `threshold` is what stops that.
    df = pd.DataFrame({"a": [-155.0], "b": [-40.0]})
    opts = _gauge(df, ["a", "b"], agg="sum")
    assert (opts["yAxis"]["min"], opts["yAxis"]["max"]) == (-200.0, 0.0)
    assert all(r["threshold"] == 0.0 for r in _rings(opts))
    # A positive frame's dial floors at zero rather than at its smallest reading.
    up = _gauge(pd.DataFrame({"v": [40.0]}), ["v"])
    assert up["yAxis"]["min"] == 0.0


def test_gauge_dial_of_an_empty_or_all_missing_selection_is_still_drawable():
    # gauge_dial is TOTAL — it runs above the app's empty-Y guard, like count_marks — and it
    # must never return a degenerate 0..0, which Highcharts would divide by.
    df = pd.DataFrame({"v": [float("nan")]})
    assert gauge_dial(df, [], "sum") == (0.0, 100.0)
    assert gauge_dial(df, ["v"], "sum") == (0.0, 100.0)
    assert gauge_dial(pd.DataFrame({"v": [0.0]}), ["v"], "sum") == (0.0, 100.0)


def test_gauge_dial_override_replaces_the_derived_one(bookings_frame):
    opts = _gauge(bookings_frame, ["north"], agg="sum", dial=(0.0, 1000.0))
    assert (opts["yAxis"]["min"], opts["yAxis"]["max"]) == (0.0, 1000.0)


@pytest.mark.parametrize("bad", [(5.0, 5.0), (100.0, 50.0), (0.0, float("inf"))])
def test_gauge_rejects_a_dial_with_no_span(bookings_frame, bad):
    with pytest.raises(ValueError) as excinfo:
        _gauge(bookings_frame, ["north"], dial=bad)
    # The app's warning IS the exception's message — they cannot drift apart.
    assert explain_gauge_error(bad) == str(excinfo.value)
    assert explain_gauge_error(None) is None  # "derive it" is not an error
    assert explain_gauge_error((0.0, 10.0)) is None


# --- the two silent-drop traps, pinned on the EMITTED JS ------------------------------ #
def test_gauge_arc_colour_rides_the_point_and_the_radius_rides_the_series(
    bookings_frame,
):
    # THE NASTIEST THING ABOUT THIS TYPE: two adjacent properties on OPPOSITE levels, each
    # silently wrong on the other's.
    cols = ["north", "south", "emea"]
    opts = _gauge(bookings_frame, cols)
    rings = _rings(opts)
    # The RADIUS must be on the SERIES. A point-level one is accepted by Chart.from_options and
    # then silently dropped — and it is the canonical Highcharts activity-gauge recipe.
    assert all("radius" in r and "innerRadius" in r for r in rings)
    js = make_chart(bookings_frame, "solidgauge", None, cols).to_js_literal()
    assert js
    flat = "".join(js.split())
    assert "radius:'100.0%'" in flat  # survived to the JS
    # The COLOUR must be on the POINT. Highcharts' solidgauge defaults `colorByPoint: true` and
    # highcharts-core models no `color_by_point` at all, so the default CANNOT be turned off:
    # every series' single point is index 0 of its own colorCounter, so a series-level `color`
    # serializes perfectly and every ring still resolves to colors[0] — three hues in the JS,
    # three identical blue arcs on screen, beside pane tracks showing the three TRUE hues.
    for ring, hue in zip(rings, DEFAULT_COLORS, strict=False):
        assert ring["data"][0]["color"] == hue  # the ARC
        # And the same hue AGAIN, on the marker, for the LEGEND swatch — the same drop wearing a
        # third hat. A series-level `color` serializes perfectly and Highcharts renders the
        # legend bullet grey anyway (verified by rendering; removing the series `color` changed
        # nothing at all, so it does no work here). The legend is the only thing that names an
        # EMPTY ring, and a grey bullet cannot be matched back to a band. A solid gauge draws no
        # markers on an arc, so this is inert everywhere else.
        assert ring["marker"] == {"fillColor": hue, "symbol": "circle"}
        assert (
            "color" not in ring
        )  # it would be an option that looks load-bearing and isn't
    for hue in DEFAULT_COLORS[:3]:
        assert f"color:'{hue}'" in flat
    # And `colorByPoint` must appear NOWHERE: it cannot be emitted, and the one that would
    # survive is the wrong one anyway.
    assert "colorByPoint" not in js


def test_gauge_takes_a_custom_palette_and_a_short_one_cycles(bookings_frame):
    # A ring's hue is its arbitrary IDENTITY (a pie slice's rule, not waterfall's semantic
    # red-means-loss), so it reads from the OVERRIDABLE palette — and a short one must WRAP
    # rather than IndexError.
    rings = _rings(
        _gauge(
            bookings_frame, ["north", "south", "emea"], colors=["#111111", "#222222"]
        )
    )
    assert [r["data"][0]["color"] for r in rings] == ["#111111", "#222222", "#111111"]


def test_gauge_pane_pulls_in_highcharts_more_without_which_the_chart_is_blank(
    bookings_frame,
):
    # The pane is LOAD-BEARING, not decoration. `get_script_tags` emits highcharts-more ONLY
    # when the options tree carries a `pane` key — not for the series type, not for
    # plotOptions.solidgauge, not for a series radius — and a solid gauge WITHOUT
    # highcharts-more draws an EMPTY SVG in the browser: zero series paths, no error band, no
    # Python-side error. The export server rasterizes it regardless, so dropping the pane would
    # make the two render modes silently DISAGREE.
    chart = make_chart(bookings_frame, "solidgauge", None, ["north"])
    tags = " ".join(chart.get_script_tags())
    assert "highcharts-more.js" in tags
    assert "modules/solid-gauge.js" in tags
    js = chart.to_js_literal()
    assert js and "pane" in js


def test_gauge_pane_tracks_mirror_the_ring_radii(bookings_frame):
    cols = ["north", "south", "emea"]
    opts = _gauge(bookings_frame, cols)
    tracks = opts["pane"]["background"]
    rings = _rings(opts)
    assert len(tracks) == len(rings)
    for track, ring in zip(tracks, rings, strict=True):
        assert track["outerRadius"] == ring["radius"]
        assert track["innerRadius"] == ring["innerRadius"]


@pytest.mark.parametrize("count", [1, 2, 5, 12, 40])
def test_gauge_ring_radii_nest_without_ever_inverting(count):
    # Two caps, each stopping the band degenerating at one END of the range.
    # MANY rings: a fixed 3% gap exceeds the band past ~21 of them, at which point inner > outer
    # and Highcharts draws garbage — and a wide CSV with 40 numeric columns is one click away.
    # The geometry DEGRADES (thin rings) rather than breaking; capping the RINGS instead would
    # mean dropping a column the user asked for.
    df = pd.DataFrame({f"c{i}": [float(i + 1)] for i in range(count)})
    rings = _rings(_gauge(df, list(df.columns)))
    assert len(rings) == count
    radii = [(float(r["radius"][:-1]), float(r["innerRadius"][:-1])) for r in rings]
    for outer, inner in radii:
        assert outer > inner  # never inverted
        # FEW rings: with the whole radius to divide, ONE column would draw an arc 61% thick — a
        # fat disc with a pinhole, which reads as a pie with a bite out of it, not a gauge.
        # A ring has to look like a ring.
        assert outer - inner <= 30.0
    for (_o1, inner), (outer, _i2) in zip(radii, radii[1:], strict=False):
        assert inner >= outer  # each ring sits strictly inside the one before it


def test_gauge_ticks_are_silenced_by_width_not_by_tick_positions(bookings_frame):
    # The obvious `tickPositions: []` is PRUNED before it is emitted (an empty list), and the
    # tick dashes then stay visible ON the tracks even with the labels switched off.
    axis = _gauge(bookings_frame, ["north"])["yAxis"]
    assert axis["tickWidth"] == 0 and axis["minorTickWidth"] == 0
    assert "tickPositions" not in axis
    assert axis["labels"] == {"enabled": False}


def test_gauge_labels_stack_in_the_hub_in_each_rings_own_hue(bookings_frame):
    cols = ["north", "south", "emea"]
    opts = _gauge(bookings_frame, cols)
    labels = [r["dataLabels"] for r in _rings(opts)]
    # One line per ring, centred about the middle one.
    assert [lbl["y"] for lbl in labels] == [-17, 0, 17]
    assert [lbl["style"]["color"] for lbl in labels] == list(DEFAULT_COLORS[:3])
    shared = opts["plotOptions"]["solidgauge"]["dataLabels"]
    assert shared["enabled"] is True
    # `allowOverlap` is load-bearing: Highcharts otherwise HIDES a colliding label by rendering
    # the <text> and turning it INVISIBLE — the element stays in the DOM, so every assertion
    # about it still passes while a ring's value is simply absent from the chart.
    assert shared["allowOverlap"] is True
    # `useHTML` is pinned False: the export server silently drops HTML labels, so the iframe and
    # the PNG would disagree.
    assert shared["useHTML"] is False


def test_gauge_many_rings_disable_the_labels_EXPLICITLY():
    # Gated on ring count, like heatmap's cells and waterfall's steps — but with a twist none of
    # them has: a gauge's dataLabels default to ON, so merely OMITTING the key (heatmap's style)
    # would be a gate that did nothing at all, and twenty labels would pile up at one offset.
    df = pd.DataFrame({f"c{i}": [float(i + 1)] for i in range(6)})
    opts = _gauge(df, list(df.columns))
    assert opts["plotOptions"]["solidgauge"]["dataLabels"] == {"enabled": False}
    assert all("dataLabels" not in r for r in _rings(opts))
    js = make_chart(df, "solidgauge", None, list(df.columns)).to_js_literal()
    assert js and "enabled:false" in "".join(js.split())


def test_gauge_tooltip_names_the_series_not_the_point_or_the_category(bookings_frame):
    # A third answer for a third reason: waterfall needs {point.category} (its points are
    # positional), sunburst and xrange need {point.name} (their categories are on the wrong
    # axis) — and a gauge ring holds exactly ONE point, so the mark's identity is not on the
    # point at all. It IS the series. The tooltip is PER RING now (the reading is baked in
    # Python and differs per ring), so it lives on the series, not chart-wide.
    (ring,) = _rings(_gauge(bookings_frame, ["north"]))
    assert "{series.name}" in ring["tooltip"]["pointFormat"]


def test_gauge_subtitle_states_the_aggregation_and_the_dial(bookings_frame):
    # The scale is INVISIBLE on the chart (a 360° gauge has nowhere to put an axis) and the
    # Static PNG has no tooltip, so without this a downloaded gauge cannot be decoded at all:
    # "436" means nothing until you know it is a sum of eight weeks against a 500 target.
    opts = _gauge(bookings_frame, ["north"], agg="sum")
    assert opts["subtitle"]["text"] == "sum · dial 0 – 500"


# --- no label channel ----------------------------------------------------------------- #
def test_gauge_ignores_x_col_entirely(bookings_frame):
    # Gauge is the first type with NO LABEL CHANNEL, and this is the pin that makes the
    # `_label_ok` exception more than a formality. Naming a column changes NOTHING...
    without = make_chart(bookings_frame, "solidgauge", None, ["north"]).to_js_literal()
    with_x = make_chart(bookings_frame, "solidgauge", "week", ["north"]).to_js_literal()
    assert without == with_x
    # ...and — the load-bearing half — a frame whose label column is ENTIRELY undrawable still
    # aggregates every row. If the shared `_label_ok` filter reached this branch it would drop
    # all eight rows and the ring would come back null; if it dropped only some, the total would
    # come back SMALLER, drawn confidently, with nothing on the page saying so. A row filter over
    # an AGGREGATE does not drop a mark — it silently changes a NUMBER.
    unlabelled = bookings_frame.assign(week=[float("nan")] * 8)
    (ring,) = _rings(_gauge(unlabelled, ["north"], agg="sum"))
    assert _reading(ring) == 436.0  # every row still counted


def test_every_other_type_requires_an_x_col(bookings_frame):
    # The column role stops being universal, so the signature has to admit it — and a pure-API
    # caller who omits x_col for a pie deserves a message, not a KeyError out of pandas.
    with pytest.raises(ValueError, match="x column"):
        build_options(bookings_frame, "line", None, ["north"])


def test_count_marks_has_no_rule_for_gauge(bookings_frame):
    # Its marks ARE its series, so `len(y_cols)` is an invariant and "Series plotted" is already
    # literally the ring count. A rule here would be the can't-drift rule run backwards: a second
    # computation of a fact that cannot differ from the first.
    with pytest.raises(ValueError, match="no rule"):
        count_marks(bookings_frame, "solidgauge", None, ["north"])


def test_gauge_light_mode_shape_and_dark_mode_themes_the_tracks(bookings_frame):
    cols = ["north", "south"]
    light = _gauge(bookings_frame, cols, dark=False)
    # There is no `borderColor` anywhere, and there CANNOT be: SolidGaugeSeries models no border
    # at any level, so one would be silently dropped (boxplot's fillColor, exactly).
    assert "borderColor" not in light["plotOptions"]["solidgauge"]
    assert set(light["plotOptions"]["solidgauge"]) == {
        "rounded",
        "linecap",
        "stickyTracking",
        "dataLabels",
    }
    assert all(t["backgroundColor"] == "#f1f5f9" for t in light["pane"]["background"])

    dark = _gauge(bookings_frame, cols, dark=True)
    # The ONE hook this type can have, and the first to reach a TOP-LEVEL key rather than
    # plotOptions: the tracks. Left unset they take a Highcharts default that
    # _LIGHT_COLOR_SCHEME_CSS pins to its LIGHT resolution in BOTH themes, so every dial would
    # sit on a pale rail against the dark shell.
    assert all(t["backgroundColor"] == "#334155" for t in dark["pane"]["background"])
    # The ring hues are untouched (the palette is theme-shared), and so are the hub labels,
    # which carry them.
    assert [r["data"][0]["color"] for r in _rings(dark)] == list(DEFAULT_COLORS[:2])
    assert dark["subtitle"]["style"]["color"]  # the subtitle follows the chrome


def test_weekly_bookings_sample_builds_a_gauge():
    from sample_data import SAMPLES

    df = SAMPLES["Weekly bookings by region (solidgauge)"]()
    cols = ["north", "south", "emea", "partner_deals"]
    opts = _gauge(df, cols, agg="sum")
    rings = _rings(opts)
    assert len(rings) == 4
    assert _reading(rings[0]) == 436.0
    assert _reading(rings[3]) is EnforcedNull  # the trap, reachable from the app
    assert opts["yAxis"]["max"] == 500.0


# --------------------------------------------------------------------------- #
# Needle gauge — the family's second half: the same readings, pointed at a DRAWN scale
#
# Everything ABOVE the mark (the reduction, the empty-column trap, the readings-derived dial,
# the six aggregations, the non-finite policy) is shared with solidgauge and is already pinned
# there — `_dial_from_readings` and `_gauge_value` are the same functions. These tests pin only
# what is genuinely the needle's, and almost every one of them is a MEASUREMENT: the properties
# below fail DIFFERENTLY here than they do on the ring, and copying the sibling's answers on
# faith would have shipped four separate silent bugs.
# --------------------------------------------------------------------------- #
def _needle(df, y_cols, **kwargs) -> dict:
    return build_options(df, "gauge", None, list(y_cols), **kwargs)


def _needles(opts: dict) -> list[dict]:
    return opts["series"]


def _needle_reading(needle: dict):
    """The one number a needle points at — or EnforcedNull when its column held no data."""
    (point,) = needle["data"]
    return point


def test_needle_draws_one_needle_per_column_reduced_to_one_number(bookings_frame):
    opts = _needle(bookings_frame, ["north", "south", "emea"], agg="sum")
    needles = _needles(opts)
    assert [n["name"] for n in needles] == ["north", "south", "emea"]
    assert [_needle_reading(n) for n in needles] == [436.0, 334.0, 175.0]
    # marks == series == len(y_cols): the invariant the whole family rests on, and the reason
    # neither gauge needs a `count_marks` rule or a MARK_METRICS entry.
    assert opts["chart"]["type"] == "gauge"


def test_needle_the_empty_column_is_a_null_not_a_confident_zero(bookings_frame):
    # The family's headline trap, and it bites HARDER on a needle than on a ring: pandas sums an
    # all-NaN column to 0.0 (the additive identity), and a needle swung to the floor of the dial
    # is INDISTINGUISHABLE from a real reading of zero — an arc at least draws nothing.
    assert pd.Series([float("nan")] * 8).sum() == 0.0  # the reason this test exists
    (needle,) = _needles(_needle(bookings_frame, ["partner_deals"], agg="sum"))
    assert _needle_reading(needle) is EnforcedNull
    # ...and it is KEPT, not dropped, so the needle count still equals the column count. The
    # legend is then the ONLY thing naming it: a null point draws no needle AND no label.
    assert needle["showInLegend"] is True
    assert needle["name"] == "partner_deals"


def test_needle_a_null_point_needs_no_ternary_unlike_the_ring(bookings_frame):
    # The ring must branch on emptiness because a LIVE ring carries `color` on the POINT (its arc
    # reads the point, not the series) while a null point must not — highcharts-core drops a null
    # `y` out of a point dict entirely, leaving a point with no value at all. A needle's colour is
    # on its DIAL, so the point is just the number and both cases are the same expression.
    live, empty = _needles(
        _needle(bookings_frame, ["north", "partner_deals"], agg="sum")
    )
    assert live["data"] == [436.0]  # a bare number, NOT {"y": ..., "color": ...}
    assert empty["data"] == [EnforcedNull]
    js = make_chart(
        bookings_frame, "gauge", None, ["north", "partner_deals"]
    ).to_js_literal()  # stubbed str | None; `js and` guards the None case
    assert js and "data:[[null]]" in "".join(js.split())  # a real null point survives


@pytest.mark.parametrize("count", [1, 2, 3, 5, 12, 40])
def test_needle_lengths_stagger_and_never_reach_the_pivot(count):
    # The fix for a corruption, not a decoration. Two columns with EQUAL readings put two needles
    # at the SAME angle, and Highcharts draws the later series ON TOP — at one length the second
    # needle covers the first COMPLETELY, so N series draw fewer than N needles while the legend
    # and the labels both go on naming N. `marks == series` becomes a lie ON SCREEN, in the one
    # place a reader would never think to check. Staggering exposes each needle's TIP.
    lengths = _needle_radii(count)
    assert len(lengths) == count
    assert lengths == sorted(
        lengths, reverse=True
    )  # y_cols[0] is the headline: longest
    assert (
        len(set(lengths)) == count
    )  # every needle a DIFFERENT length, or the fix is not one
    # Degrades rather than breaks, exactly like `_gauge_rings`: at 40 columns the needles bunch
    # up, but all 40 are there and none has walked back into the pivot (or past it, to a negative
    # radius Highcharts draws as garbage). Capping the COUNT instead would drop a column the user
    # asked for.
    assert all(0 < length <= 100 for length in lengths)


def test_needle_the_staggered_lengths_actually_REACH_the_emitted_needles(
    bookings_frame,
):
    # The gap a mutation test found: `_needle_radii` was pinned in ISOLATION, and the only
    # options-level radius assertion was the count==1 case — where the stagger is vacuous by
    # construction. So replacing `_pct(length)` with `_pct(_NEEDLE_LONGEST_PCT)` in the branch —
    # which restores the exact bug the helper exists to prevent, every needle the same length,
    # two equal readings drawing as one — left the whole suite GREEN.
    #
    # A helper is not a behaviour until something calls it. This asserts the call.
    cols = ["north", "south", "emea"]
    opts = _needle(bookings_frame, cols)
    radii = [n["dial"]["radius"] for n in _needles(opts)]
    assert radii == [_pct(length) for length in _needle_radii(len(cols))]
    assert len(set(radii)) == len(cols)  # DISTINCT: the point of the whole exercise
    # And on the emitted JS, since a dial's geometry is exactly the sort of thing this library
    # accepts and then drops (the `pane.size` family).
    js = make_chart(bookings_frame, "gauge", None, cols).to_js_literal()
    flat = "".join(js.split()) if js else ""
    assert js and all(f"radius:'{r}'" in flat.replace('"', "'") for r in radii)


def test_needle_one_column_takes_the_full_length(bookings_frame):
    # The n=1 boundary: there is nothing to stagger against, and a lone needle stunted to the
    # shortest length would look like a bug.
    (needle,) = _needles(_needle(bookings_frame, ["north"]))
    assert needle["dial"]["radius"] == "88.0%"


def test_needle_every_dial_carries_topwidth_or_the_chart_cannot_be_built(
    bookings_frame,
):
    # THE family's one shared trap, and the nastiest thing about this type. `plot_options/gauge.py`
    # and the series' own DialOptions both validate `top_width` WITHOUT `allow_empty=True`, so any
    # dial dict omitting `topWidth` raises EmptyValueError — out of a validator that names neither
    # the key, nor `dial`, nor the series. And it fires at `Chart.from_options`, one layer BELOW
    # `build_options`: an options-dict assertion would pass while the chart cannot be built at all,
    # and the app's interactive path (which does not catch builder errors) would show a bare
    # traceback. Hence: this test drives `make_chart`, not `build_options`.
    opts = _needle(bookings_frame, ["north", "south"])
    assert all(n["dial"]["topWidth"] == 1 for n in _needles(opts))
    # There is NO `plotOptions.gauge.dial`, and that absence is pinned rather than merely true.
    # It was carried at first, on the reasoning that `topWidth` is demanded at "both levels" —
    # which is false: every needle carries its own complete dial (it must, for its hue and its
    # length), so a plotOptions dial defaults nothing and does no work. Deleting it changes not one
    # byte of the emitted JS. An option that LOOKS load-bearing and isn't is the exact defect this
    # module tests other libraries for, and one of ours would be worse — it came with a comment
    # swearing it was needed.
    assert "dial" not in opts["plotOptions"]["gauge"]
    js = make_chart(
        bookings_frame, "gauge", None, ["north", "south"]
    ).to_js_literal()  # stubbed str | None; `js and` guards the None case
    # One per needle, and only per needle — the trap is guarded where it actually bites.
    assert js and "".join(js.split()).count("topWidth:1") == 2


def test_needle_hue_rides_the_dial_and_the_legend_but_never_the_point(bookings_frame):
    # TWO levels, and NOT two of the ring's three — there is no overlap at all. On a solid gauge a
    # series-level `color` serializes perfectly and reaches NOTHING (the arc reads the POINT,
    # because `colorByPoint: true` is a default highcharts-core cannot express turning off; the
    # legend bullet draws grey and needs a `marker.fillColor`). On a needle, `color` reaches ONLY
    # the legend — the needle itself is BLACK unless `dial.backgroundColor` says otherwise.
    # Verified by rendering `color` alone: three perfectly coloured legend swatches above three
    # black needles. Same property, opposite failure.
    cols = ["north", "south", "emea"]
    opts = _needle(bookings_frame, cols)
    hues = list(DEFAULT_COLORS[:3])
    assert [n["dial"]["backgroundColor"] for n in _needles(opts)] == hues  # the NEEDLE
    assert [n["color"] for n in _needles(opts)] == hues  # the LEGEND swatch
    # The point carries the number and nothing else — no `color` to be read (the ring's level),
    # and no `marker`, which is the ring's legend hack and does no work at all here.
    assert all(not isinstance(n["data"][0], dict) for n in _needles(opts))
    assert all("marker" not in n for n in _needles(opts))
    js = make_chart(bookings_frame, "gauge", None, cols).to_js_literal()
    assert js and (
        "colorByPoint" not in js
    )  # solidgauge's un-turn-off-able default is not this type's


def test_needle_asks_for_the_legend_explicitly_because_a_gauge_series_defaults_to_hiding_it(
    bookings_frame,
):
    # A gauge series defaults to `showInLegend: false`, unlike almost every other type — so
    # `legend.enabled` alone renders NO legend at all (verified by rendering: it was simply
    # absent). It has to be asked for twice. And it matters more here than anywhere: a needle
    # carries no name on the chart, so past the label gate — and for an empty column, whose null
    # point draws neither needle nor label — the legend is the ONLY thing that says which is which.
    opts = _needle(bookings_frame, ["north", "south"])
    assert opts["legend"]["enabled"] is True
    assert all(n["showInLegend"] is True for n in _needles(opts))


def test_needle_pivot_is_one_neutral_colour_not_one_per_series(bookings_frame):
    # N needles pivot at the SAME POINT, so N hued pivots draw N discs on top of each other and
    # the reader sees whichever series happened to be drawn last — a hub wearing one arbitrary
    # column's identity. It is not a mark and has no identity, so it takes the module's existing
    # off-palette slate (sunburst's root colour), which reads on both backgrounds and needs no
    # dark flip. Left unset it defaults to BLACK, invisible on the dark shell.
    opts = _needle(bookings_frame, ["north", "south", "emea"])
    assert opts["plotOptions"]["gauge"]["pivot"]["backgroundColor"] == "#94a3b8"
    assert all("pivot" not in n for n in _needles(opts))  # never per series


def test_needle_resolves_highcharts_more_from_the_chart_type_alone(bookings_frame):
    # The family's sharpest INVERSION, and the reason solidgauge's pane comment must not be
    # copied here. A solid gauge resolves highcharts-more ONLY from its `pane` — drop that key and
    # the browser draws an empty SVG while the export server renders perfectly. A needle resolves
    # it from `chart.type`, so its pane is geometry and nothing hangs on it.
    chart = make_chart(bookings_frame, "gauge", None, ["north"])
    assert "highcharts-more" in chart.get_required_modules()
    # ...and it does so with the pane taken away entirely — which is what "from the type alone"
    # means, and the only way to show it.
    from highcharts_core.chart import Chart

    paneless = build_options(bookings_frame, "gauge", None, ["north"])
    paneless.pop("pane")
    assert "highcharts-more" in Chart.from_options(paneless).get_required_modules()


def test_needle_pane_is_an_arc_not_a_disc(bookings_frame):
    # A pane background defaults to a CIRCLE, so an arc gauge left to itself draws a full disc
    # behind its semicircle — and `_themed` would then flip a whole dark disc in. `shape` has to
    # be said out loud. (`size` is NOT set, and must not be: highcharts-core's Pane.size setter
    # validates a percentage string and then never assigns it — see the next test.)
    opts = _needle(bookings_frame, ["north"])
    (face,) = opts["pane"]["background"]
    assert face["shape"] == "arc"
    assert (opts["pane"]["startAngle"], opts["pane"]["endAngle"]) == (-90, 90)


def test_needle_pane_says_what_the_dial_is_and_nothing_about_where_to_put_it(
    bookings_frame,
):
    # NEITHER key, and that is a conclusion rather than an omission — which is why it is pinned.
    #
    # `size` is a SILENT DROP, found by reading the library: `options/pane.py`'s setter runs
    # `validators.string(value)`, checks the result for '%', and then falls off the end WITHOUT
    # EVER ASSIGNING `self._size` — only the numeric `except` branch writes it. So the `size: "85%"`
    # every Highcharts gauge demo sets is accepted and discarded. (`inner_size`, ten lines above
    # it, assigns in both branches: one copy-paste slip, not a policy.)
    #
    # And without `size`, `center` cannot be made safe: Highcharts reserves no room for the tick
    # labels outside the pane, and the pane's radius scales with the plot box. At 58% the topmost
    # label printed through the subtitle; at 65% it was clean at 300px and 800px and CLIPPED CLEAN
    # OFF THE CANVAS at 420 — a failure that is not even monotonic in the height, which is the tell
    # that it is not a number to be tuned. Highcharts' own default is correct at every height the
    # app offers, because it is the one placement that knows what the labels need.
    #
    # This test exists so nobody "helpfully" re-adds either one.
    opts = _needle(bookings_frame, ["north"])
    assert "size" not in opts["pane"]
    assert "center" not in opts["pane"]
    assert set(opts["pane"]) == {"startAngle", "endAngle", "background"}
    js = make_chart(bookings_frame, "gauge", None, ["north"]).to_js_literal()
    flat = "".join(js.split()) if js else ""
    assert js and "size:" not in flat and "center:" not in flat


def test_needle_draws_the_axis_it_points_at(bookings_frame):
    # The type's whole reason to exist, and the one thing a solid gauge cannot have: a 360° ring
    # has nowhere to put an axis, so it prints its dial in a subtitle. A needle's reading IS an
    # angle against a drawn scale, so the ticks are the chart.
    opts = _needle(bookings_frame, ["north"], agg="sum")
    assert (opts["yAxis"]["min"], opts["yAxis"]["max"]) == (
        0.0,
        500.0,
    )  # 436 -> a 0..500 dial
    assert (
        opts["yAxis"]["tickWidth"] == 2
    )  # DRAWN — the solid gauge silences its ticks to 0
    # `gridLineWidth` is pinned to 0 rather than left to Highcharts, because `_themed` writes a
    # gridLineColor onto every axis it finds — so a nonzero default would draw concentric
    # gridlines across the face that ONLY dark-mode readers would ever see.
    assert opts["yAxis"]["gridLineWidth"] == 0
    assert opts["yAxis"]["title"] == {"text": ""}  # or Highcharts titles it "Values"


def test_needle_subtitle_states_only_the_aggregation(bookings_frame):
    # The solid gauge's subtitle carries `agg` AND the dial, because neither is on the chart. The
    # needle draws its dial, so repeating it here would be the one thing worse than not saying it:
    # two homes for one number, free to disagree. The `agg` stays, because no axis will ever say
    # that 436 is a sum of eight weeks rather than one week's reading.
    opts = _needle(bookings_frame, ["north"], agg="mean")
    assert opts["subtitle"]["text"] == "mean"
    assert "dial" not in opts["subtitle"]["text"]


@pytest.mark.parametrize("count", [1, 3, 8])
def test_needle_prints_nothing_in_the_mark_and_says_so_EXPLICITLY(count):
    # The sibling MUST print its readings in the hub — a 360° ring has nowhere to put an axis, so
    # the value can be read against nothing, and it pays for that with a gate, a measured leading
    # and a per-series offset. A needle points AT an axis that renders in the Static PNG too, and
    # its identity is in the legend it carries anyway. So it prints NOTHING in the mark and needs
    # no gate constant either: xrange's rule, reached from xrange's premise.
    #
    # DISABLED EXPLICITLY, which is the whole reason the key is here: a gauge's dataLabels default
    # to ON (unlike heatmap's and column's), so merely omitting it would print Highcharts' own
    # boxed label — N of them stacked at ONE anchor, since Highcharts renders every gauge series'
    # label at the same point. Swept over the count so no gate can creep back in unnoticed.
    wide = pd.DataFrame({f"c{i}": [float(i + 1)] for i in range(count)})
    opts = _needle(wide, list(wide.columns))
    assert opts["plotOptions"]["gauge"]["dataLabels"] == {"enabled": False}
    assert all("dataLabels" not in n for n in _needles(opts))
    assert (
        len(_needles(opts)) == count
    )  # ...and every column the user asked for is still drawn


def test_needle_off_the_dial_swings_past_the_scale_instead_of_lying_on_it(
    bookings_frame,
):
    # The one way this type could still draw a confident, plausible, WRONG chart, and it is
    # reachable in one keystroke: `gauge_dial` guarantees every reading sits inside the scale it
    # DERIVES, but the app's two Dial inputs accept any two numbers. Zoom the scale to 0..50 on a
    # column that sums to 436 and — left to Highcharts — the needle pegs EXACTLY ON the final tick,
    # pixel-identical to a true reading of 50 (verified by rendering). Nothing on the chart
    # contradicts it, and the Static PNG has no tooltip.
    #
    # It is also the ONE place the two gauges would disagree: a solid gauge in the same state fills
    # its arc and PRINTS "north: 436" in the hub, so its reader is told. A needle prints nothing in
    # the mark. The family must not be honest in one branch and mute in the other.
    opts = _needle(bookings_frame, ["north"], agg="sum", dial=(0.0, 50.0))
    assert (
        _needle_reading(_needles(opts)[0]) == 436.0
    )  # the TRUE value still reaches the chart
    assert opts["yAxis"]["max"] == 50.0  # ...on a dial that cannot show it
    assert (
        opts["plotOptions"]["gauge"]["overshoot"] == 5
    )  # ...so the needle swings PAST the end
    js = make_chart(
        bookings_frame, "gauge", None, ["north"], agg="sum", dial=(0.0, 50.0)
    ).to_js_literal()
    assert js and "overshoot:5" in "".join(js.split())  # and it survives the round-trip


def test_needle_face_carries_no_grid_not_even_the_minor_one(bookings_frame):
    # The MINOR gridline is the load-bearing half, which is exactly backwards from what you would
    # guess. `_themed` writes a `gridLineColor` onto every axis it finds, so the MAJOR width must
    # be pinned or dark-mode readers get concentric gridlines nobody asked for. But NOTHING themes
    # the minor one, and Highcharts defaults it to 1px of `#f2f2f2` — invisible on the light dial
    # face, and a BLAZING WHITE STARBURST across the dark one. Verified by rendering, on a chart
    # whose every unit test passed: the options were right and the picture was not.
    opts = _needle(bookings_frame, ["north"], dark=True)
    assert opts["yAxis"]["gridLineWidth"] == 0
    assert opts["yAxis"]["minorGridLineWidth"] == 0
    assert opts["yAxis"]["minorTickWidth"] == 0


@pytest.mark.parametrize("chart_type", GAUGE_TYPES)
def test_gauge_family_formats_a_reading_honestly_at_every_magnitude(chart_type):
    # The reading is the ONE flaw an options-dict assertion used to be unable to see: a bare
    # `{point.y}` prints the raw double, so a `mean` renders `66.44444444444444` off the side of
    # the chart. `.1f` trimmed that but rounded a real 0.008 reading to "0.0" — the family's own
    # confident zero, the exact lie `_gauge_value` fusses to keep an empty column from telling.
    # No FIXED-decimal Highcharts format is honest at both ends (Highcharts has no `g`), so the
    # reading is now formatted in PYTHON (`_gauge_reading_label`) and BAKED into each series' own
    # format string — which is what finally puts the NUMBER, not just the format string, under
    # test. Swept over the FAMILY because both types share `_gauge_value` and one reduction: they
    # must format one number one way, or a reader comparing them gets whichever branch they opened.
    smear = pd.DataFrame({"m": [1.0] * 8 + [2.0]})  # mean 1.111..., a repeating decimal
    (series,) = build_options(smear, chart_type, None, ["m"], agg="mean")["series"]
    assert (
        series["tooltip"]["pointFormat"] == "{series.name}: <b>1.1</b>"
    )  # smear trimmed
    assert "{point.y}" not in series["tooltip"]["pointFormat"]  # the raw double is gone

    tiny = pd.DataFrame(
        {"t": [0.008, 0.008]}
    )  # a real reading `.1f` would flatten to "0.0"
    (series,) = build_options(tiny, chart_type, None, ["t"], agg="mean")["series"]
    assert (
        series["tooltip"]["pointFormat"] == "{series.name}: <b>0.008</b>"
    )  # preserved

    # ...and the IN-MARK hub label, which is where the solidgauge smear was actually SEEN (the
    # needle prints nothing in the mark). The same baked reading, so the two cannot disagree.
    if chart_type == "solidgauge":
        (ring,) = build_options(smear, chart_type, None, ["m"], agg="mean")["series"]
        assert ring["dataLabels"]["format"] == "{series.name}: 1.1"

    # And on the emitted JS, because a format string is only a string until Highcharts reads it:
    # the baked reading must survive the round-trip and no `{point.y}` token may reappear.
    js = make_chart(tiny, chart_type, None, ["t"], agg="mean").to_js_literal()
    flat = "".join(js.split()) if js else ""
    assert js and "0.008" in flat and "{point.y}" not in flat


def test_gauge_reading_label_is_honest_and_length_bounded_at_every_magnitude():
    # The helper tested in isolation (like `_needle_radii`), because it is the one thing an
    # options-dict assertion structurally cannot see the OUTPUT of: only the format string.
    # Big numbers keep one decimal and a separator; small ones keep ~3 significant figures rather
    # than rounding to a confident zero; a null reading prints nothing.
    assert _gauge_reading_label(436.0) == "436"  # no trailing zero on an integer total
    assert _gauge_reading_label(66.44444444444444) == "66.4"  # the mean smear, trimmed
    assert _gauge_reading_label(1234567.0) == "1,234,567"  # separators, not scientific
    assert _gauge_reading_label(0.008) == "0.008"  # NOT "0.0" — the whole fix
    assert _gauge_reading_label(0.0) == "0"
    assert _gauge_reading_label(-155.0) == "-155"
    # A non-finite float has no reading to print — guarded so it can't leak "nan"/"inf" into a
    # label (belt-and-suspenders: `_gauge_value` already returns EnforcedNull for these).
    assert _gauge_reading_label(float("nan")) == ""
    assert _gauge_reading_label(float("inf")) == ""
    assert (
        _gauge_reading_label("absent") == ""
    )  # EnforcedNull stands in for a non-float

    # The label must stay SHORT even for a magnitude a dial cannot show — a 1e308 cell parses out
    # of a plain CSV (the module guards it elsewhere), and a fixed-decimal format would expand it
    # to a 300-digit string dumped into the emitted JS. Scientific keeps it legible and bounded.
    assert _gauge_reading_label(1e308) == "1e+308"
    for value in (1e308, 5e-324, 9e-5, 1.5e15, 1e-4, 9.99e14):
        assert len(_gauge_reading_label(value)) < 20


def test_needle_tooltip_names_the_series_not_the_point(bookings_frame):
    # A gauge series holds exactly ONE point, so the mark's identity is not on the point at all.
    # It IS the series. (`{point.name}` renders blank; `{point.category}` reads an axis that has
    # no categories.) The tooltip is PER NEEDLE (the reading is baked in Python) and is the only
    # place the exact reading survives, now that nothing is printed in the mark — the one thing
    # interactive mode has that the Static PNG does not, a real cost of axis-instead-of-labels.
    (needle,) = _needles(_needle(bookings_frame, ["north"], agg="sum"))
    assert needle["tooltip"]["pointFormat"] == "{series.name}: <b>436</b>"
    # ...and there is no chart-wide tooltip pointFormat left to drift from the per-series one.
    assert "pointFormat" not in _needle(bookings_frame, ["north"]).get("tooltip", {})


def test_needle_takes_a_custom_palette_and_a_short_one_cycles(bookings_frame):
    short = ["#111111", "#222222"]
    opts = _needle(bookings_frame, ["north", "south", "emea"], colors=short)
    # WRAPS rather than IndexErrors — a needle's hue is its arbitrary IDENTITY, so it rides the
    # overridable palette (waterfall's semantic red-means-loss is the opposite case).
    assert [n["dial"]["backgroundColor"] for n in _needles(opts)] == [*short, "#111111"]


def test_needle_no_plot_bands_because_the_data_never_said_low_was_bad(bookings_frame):
    # The red/amber/green zones a speedometer is popularly drawn with are a JUDGMENT, and the user
    # declared no target — they picked columns and a reduction. Solidgauge's argument against
    # `yAxis.stops`, unchanged. (It would also be a poor band: `thickness`, `innerRadius` and
    # `outerRadius` are all accepted by Chart.from_options and silently dropped.)
    opts = _needle(bookings_frame, ["north"])
    assert "plotBands" not in opts["yAxis"]
    assert "stops" not in opts["yAxis"]


def test_needle_ignores_x_col_entirely(bookings_frame):
    # The gauge family's defining pin, and the load-bearing half is the second one: this branch
    # sits ABOVE the shared `_label_ok` filter, and a row filter over an AGGREGATE does not drop a
    # mark — it silently changes a NUMBER.
    without = make_chart(bookings_frame, "gauge", None, ["north"]).to_js_literal()
    with_x = make_chart(bookings_frame, "gauge", "week", ["north"]).to_js_literal()
    assert without == with_x
    unlabelled = bookings_frame.assign(week=[float("nan")] * 8)
    (needle,) = _needles(_needle(unlabelled, ["north"], agg="sum"))
    assert _needle_reading(needle) == 436.0  # every row still counted


def test_needle_light_mode_shape_and_dark_mode_themes_the_dial_face(bookings_frame):
    light = _needle(bookings_frame, ["north", "south"], dark=False)
    assert all(f["backgroundColor"] == "#f1f5f9" for f in light["pane"]["background"])

    dark = _needle(bookings_frame, ["north", "south"], dark=True)
    # The family's ONE hook, widened from solidgauge's: the dial FACE. Left unset it takes a
    # Highcharts default that _LIGHT_COLOR_SCHEME_CSS pins to its LIGHT resolution in BOTH themes,
    # so the dial would sit on a glaring white rail against the dark shell (verified by rendering:
    # a white arc, unmissable). It is the only hook this type NEEDS — its axis is a real yAxis
    # dict, so `_themed`'s generic axis loop has already coloured the labels, ticks and line.
    assert all(f["backgroundColor"] == "#334155" for f in dark["pane"]["background"])
    assert dark["yAxis"]["labels"]["style"][
        "color"
    ]  # ...themed for free, unlike the ring's
    assert dark["yAxis"]["tickColor"]
    # The needle hues are untouched (the palette is theme-shared), and so is the slate pivot.
    assert [n["dial"]["backgroundColor"] for n in _needles(dark)] == list(
        DEFAULT_COLORS[:2]
    )
    assert dark["plotOptions"]["gauge"]["pivot"]["backgroundColor"] == "#94a3b8"


def test_needle_and_ring_cannot_disagree_about_the_readings_or_the_dial(bookings_frame):
    # The family invariant, stated as a test: the two types share `_gauge_value` and `gauge_dial`,
    # so given one frame, one selection and one reduction they MUST reduce to the same numbers and
    # scale them against the same dial. Only the mark differs. This is what `_dial_from_readings`
    # makes structural (a function that cannot see a raw column cannot derive a dial from one) —
    # and this test is what would catch the two branches drifting apart if anyone ever inlined it.
    cols = ["north", "south", "emea", "partner_deals"]
    for agg in GAUGE_AGGREGATIONS:
        ring = _gauge(bookings_frame, cols, agg=agg)
        needle = _needle(bookings_frame, cols, agg=agg)
        assert [_reading(r) for r in _rings(ring)] == [
            _needle_reading(n) for n in _needles(needle)
        ]
        assert (ring["yAxis"]["min"], ring["yAxis"]["max"]) == (
            needle["yAxis"]["min"],
            needle["yAxis"]["max"],
        )


def test_server_utilization_sample_builds_a_needle_gauge():
    from sample_data import SAMPLES

    df = SAMPLES["Server utilization (gauge)"]()
    cols = ["cpu_pct", "memory_pct", "disk_pct", "swap_pct"]
    opts = _needle(df, cols, agg="mean")
    needles = _needles(opts)
    assert len(needles) == 4
    # A mean of percentages lands the derived dial on the scale the reader already has in mind.
    assert opts["yAxis"]["max"] == 100.0
    assert (
        _needle_reading(needles[3]) is EnforcedNull
    )  # the trap, reachable from the app
    # ...and the three live readings SPREAD, which is what a needle gauge is for.
    live = [_needle_reading(n) for n in needles[:3]]
    assert max(live) - min(live) > 15


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


def test_conversion_funnel_sample_builds_a_funnel_chart():
    # Ties the new funnel sample to its intended type end to end: a stage label (X) plus one
    # visitor-count value column (Y) produce one {name, y} band per stage, in row order, and the
    # sample's values strictly DECREASE — the narrowing a funnel is meant to show.
    from sample_data import _conversion_funnel

    df = _conversion_funnel()
    opts = build_options(df, "funnel", "stage", ["visitors"])
    assert opts["chart"]["type"] == "funnel"
    assert opts["series"][0]["name"] == "visitors"
    data = opts["series"][0]["data"]
    assert len(data) == len(df)
    assert data[0]["name"] == "Visitors"
    assert "y" in data[0]  # pie's key, not treemap's "value"
    values = [pt["y"] for pt in data]
    assert values == sorted(values, reverse=True)  # a clean narrowing funnel


def test_loyalty_pyramid_sample_builds_a_pyramid_chart():
    # The mirror of the funnel sample: a tier label (X) plus one people-count column (Y). Like the
    # funnel it leads with its LARGEST stage and DECREASES, but a pyramid draws the first row at
    # the base (verified by rendering), so the broad Audience base is row 0 and it narrows up to
    # the Advocates apex. Same data SHAPE as the funnel sample, drawn as pyramid's own series type.
    from sample_data import _loyalty_pyramid

    df = _loyalty_pyramid()
    opts = build_options(df, "pyramid", "tier", ["people"])
    assert opts["chart"]["type"] == "pyramid"
    assert opts["series"][0]["name"] == "people"
    data = opts["series"][0]["data"]
    assert len(data) == len(df)
    assert data[0]["name"] == "Audience"  # the broad base, drawn at the bottom
    values = [pt["y"] for pt in data]
    assert values == sorted(
        values, reverse=True
    )  # largest-first, narrowing to the apex


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


def test_regional_migration_sample_builds_a_dependencywheel_chart():
    # Ties the new dependencywheel sample to its type end to end: two node columns plus a
    # numeric weight produce one link per row. It is the MIRROR of the sankey energy sample —
    # where that is a layered flow (its source and target sets barely overlap), here EVERY
    # region is BOTH an origin and a destination: the symmetric, cyclic matrix a wheel is
    # built for, and a straight sankey would draw as a tangle of back-crossing links.
    from sample_data import _regional_migration

    df = _regional_migration()
    opts = build_options(
        df, "dependencywheel", "origin", ["people"], target_col="destination"
    )
    assert opts["chart"]["type"] == "dependencywheel"
    assert opts["series"][0]["name"] == "people"
    links = _links(opts)
    assert len(links) == len(df)  # every row is a drawable link
    assert links[0] == {"from": "North", "to": "South", "weight": 1200.0}
    origins = {link["from"] for link in links}
    destinations = {link["to"] for link in links}
    # The wheel's defining shape: every region is BOTH an origin and a destination.
    assert origins == destinations == {"North", "South", "East", "West", "Central"}


def test_service_dependencies_sample_builds_a_networkgraph_chart():
    # Ties the new networkgraph sample to its intended type end to end: two node columns and
    # NO value column produce one unweighted edge per row. Like the sankey sample (and unlike
    # the value-per-row types) its source values REPEAT and several nodes are BOTH a source
    # and a target — that connectivity is what makes it a graph rather than a star. It also
    # carries a CYCLE (Catalog ⇄ Search) that a sunburst's tree could never hold.
    from sample_data import _service_dependencies

    df = _service_dependencies()
    opts = build_options(df, "networkgraph", "service", [], target_col="depends_on")
    assert opts["chart"]["type"] == "networkgraph"
    edges = opts["series"][0]["data"]
    assert len(edges) == len(df)  # one edge per row, none dropped
    assert edges[0] == {"from": "Web", "to": "API Gateway"}
    sources = {e["from"] for e in edges}
    targets = {e["to"] for e in edges}
    # Shared nodes make it a connected network (an API Gateway hub, an Auth reached by several).
    assert {"API Gateway", "Orders", "Auth", "Catalog"} <= sources & targets
    # The Catalog ⇄ Search cycle: each names the other as a target.
    assert {"from": "Catalog", "to": "Search"} in edges
    assert {"from": "Search", "to": "Catalog"} in edges
    # The sample carries a numeric column (so it stays plottable by other types and clears the
    # app's no-numeric-columns gate — the _release_plan/headcount precedent), but networkgraph
    # IGNORES it: the edges name only the two label columns, no weight in sight.
    from pandas.api.types import is_numeric_dtype

    assert is_numeric_dtype(df["calls_per_min"])
    assert all(set(e) == {"from", "to"} for e in edges)


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


def test_profit_bridge_sample_builds_a_waterfall_chart():
    # Ties the new waterfall sample to its intended type end to end. It is the only sample
    # whose numeric column holds signed DELTAS rather than levels — they mean nothing
    # individually, only cumulatively — so it is also the only one where the built chart has
    # MORE marks than the frame has rows: the builder appends the closing total.
    from sample_data import _profit_bridge

    df = _profit_bridge()
    opts = build_options(df, "waterfall", "step", ["delta"])
    assert opts["chart"]["type"] == "waterfall"
    assert opts["series"][0]["name"] == "delta"
    data = opts["series"][0]["data"]
    assert len(data) == len(df) + 1 == 7  # 6 deltas + the appended total
    assert data[:6] == [420.0, -155.0, -120.0, -64.0, 38.0, -40.0]
    assert data[6]["isSum"] is True
    assert opts["xAxis"]["categories"][-1] == "Total"
    # Mixed signs are the point of the type: a same-signed column would just be a column
    # chart drawn oddly. "Other income" is the one mid-sequence RISE, which is what proves
    # the up/down coloring keys off each value's sign rather than off its position.
    assert min(df["delta"]) < 0 < max(df["delta"])
    assert df.loc[df["step"] == "Other income", "delta"].item() == 38.0
    # The deltas bridge gross revenue to net profit — the total Highcharts will compute.
    assert df["delta"].sum() == 79.0


def test_org_headcount_sample_builds_a_sunburst_chart():
    # Ties the sunburst sample to its intended type end to end. It is the only sample whose
    # rows are a HIERARCHY (sankey's _energy_flow is the near miss — its rows are edges of a
    # GRAPH, and Electricity is both a source and a target, which no tree can be), and the only
    # one whose value column is deliberately BLANK on some rows: there a blank means "ask my
    # children", not "missing".
    from sample_data import _org_headcount

    df = _org_headcount()
    opts = build_options(df, "sunburst", "team", ["headcount"], parent_col="reports_to")
    assert opts["chart"]["type"] == "sunburst"
    data = opts["series"][0]["data"]
    assert len(data) == len(df) + 1 == 16  # 15 nodes + the appended root
    assert data[-1]["name"] == "All"

    # The five internal nodes state no headcount and carry none: Engineering's 80 is nowhere in
    # this frame — it is 80 BECAUSE its teams are, and the chart is what does that addition.
    internal = {"Engineering", "Sales", "Marketing", "Platform", "Product"}
    for point in data[:-1]:
        assert ("value" in point) is (point["name"] not in internal), point
    assert df["headcount"].isna().sum() == 5

    # The two "Other" teams: the exact case a label-keyed node identity would silently merge
    # into one 9-person sector. They stay two honest leaves under two different divisions.
    others = [p for p in data if p["name"] == "Other"]
    assert len(others) == 2
    assert sorted(p["value"] for p in others) == [4.0, 5.0]
    assert others[0]["parent"] != others[1]["parent"]

    # Three CSV levels + the synthesized root = four rings, which is what makes the colour
    # inheritance and the ALTERNATING sign of the colorVariation visible at all.
    levels = opts["plotOptions"]["sunburst"]["levels"]
    assert [entry["level"] for entry in levels] == [1, 3, 4]
    # The branch sums Highcharts will compute (the numbers the chart shows but the frame never
    # states), and the grand total the centre reads.
    assert df["headcount"].sum() == 143.0


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
# generated-config reveal. Those indices hold for every type, because the three
# type-specific extra controls are created *after* the X selectbox: bubble's
# "Size (Z)", sankey's "Target (to)" and sunburst's "Parent". All three are addressed by
# LABEL rather than index, since they shift the widgets that follow them. The Upload CSV
# path shifts them again — it has no Dataset selectbox — so a test on that path addresses
# "Chart type" by label too. Everything here stays on
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


@pytest.mark.parametrize("chart_type", ["funnel", "pyramid"])
def test_app_switch_to_funnel_family_regenerates_config(app, chart_type):
    # Funnel/pyramid are single-value like pie/treemap, so switching swaps the Y pills for a
    # single-select Y (an extra selectbox, exactly as pie does) and drives the config through the
    # funnel branch, adding NO extra control before Chart type (so the index-[1] addressing other
    # app tests rely on still holds). `type: '<chart_type>'` proves that branch produced it — and
    # that a pyramid emits its OWN type name, not a funnel. Network-free.
    app.selectbox[1].set_value(chart_type).run()  # Chart type -> funnel / pyramid
    assert not app.exception
    _reveal_config(app)
    assert not app.exception
    assert f"type: '{chart_type}'" in app.code[0].value


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


def test_app_switch_to_dependencywheel_shows_target_control_and_regenerates_config(app):
    # Dependencywheel is sankey's circular twin, so switching to it reveals the SAME
    # "Target (to)" selectbox and single-select "Flow value (weight)" Y (the node-link controls,
    # keyed on NODE_LINK_TYPES) and drives the config through the shared target_col plumbing —
    # but the emitted `type: 'dependencywheel'` proves the WHEEL branch, not sankey's, produced
    # it. The source==target guard and the keyless Target's survival are shared code paths,
    # already pinned on sankey. Network-free.
    assert not any(
        sb.label == "Target (to)" for sb in app.selectbox
    )  # absent by default
    app.selectbox[1].set_value("dependencywheel").run()  # Chart type -> dependencywheel
    assert not app.exception
    assert any(sb.label == "Target (to)" for sb in app.selectbox)  # now present
    assert any(sb.label == "Flow value (weight)" for sb in app.selectbox)
    assert not app.pills  # single-select Y (the weight), not the multi-select pills
    _reveal_config(app)
    assert not app.exception
    assert "type: 'dependencywheel'" in app.code[0].value


def test_app_dependencywheel_kpi_shows_flows(app):
    # A dependencywheel is one series of links like sankey, so the KPI swaps "Series plotted"
    # (which would read a bare 1) for "Flows" — sharing sankey's label because it counts the
    # same {from, to, weight} links. The default dataset has no missing values, so every row
    # becomes a flow.
    from sample_data import SAMPLES

    app.selectbox[1].set_value("dependencywheel").run()  # Chart type -> dependencywheel
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    default_df = next(iter(SAMPLES.values()))()
    assert metrics["Flows"] == f"{len(default_df):,}"


def test_app_switch_to_networkgraph_shows_target_hides_y_and_regenerates_config(app):
    # Networkgraph is the SUBTRACTIVE mirror of gauge: gauge removes the X selectbox, and
    # networkgraph removes the Y control entirely (it has no value channel). So after switching
    # it shows a "Target (to)" selectbox (reused from sankey) and NO Y widget at all — neither
    # the multi-select pills nor a single-select Y selectbox. The only selectboxes left are
    # Dataset, Chart type, Source (from) and Target (to). The config still generates without a Y,
    # which is the whole point: an empty y_cols is valid input here. Network-free.
    assert app.pills  # the default `line` type shows multi-select Y pills...
    app.selectbox[1].set_value("networkgraph").run()  # Chart type -> networkgraph
    assert not app.exception
    assert not app.pills  # ...which are gone, and NOT replaced by a Y selectbox
    labels = {sb.label for sb in app.selectbox}
    assert labels == {"Dataset", "Chart type", "Source (from)", "Target (to)"}
    _reveal_config(app)
    assert not app.exception
    assert "type: 'networkgraph'" in app.code[0].value


def test_app_networkgraph_source_equals_target_shows_guard_warning(app):
    # Networkgraph shares sankey's source-vs-target guard: one column can't be both ends of an
    # edge. The default Source is the first column, so pointing Target at it collides.
    app.selectbox[1].set_value("networkgraph").run()  # Chart type -> networkgraph
    target = next(sb for sb in app.selectbox if sb.label == "Target (to)")
    target.set_value("month").run()  # == the default Source column
    assert not app.exception
    assert app.warning
    assert "Source and Target must be different" in app.warning[0].value


_EDGE_LIST_CSV = (
    b"source,target\nWeb,API Gateway\nAPI Gateway,Auth\nAPI Gateway,Orders\n"
)


def test_app_networkgraph_plots_a_csv_with_no_numeric_columns_at_all(app):
    # THE GATE, networkgraph's half of it — the xrange test's mirror. The canonical networkgraph
    # input is a pure edge list: two TEXT columns and not one number. `select_dtypes("number")`
    # finds nothing, so the no-numeric-columns gate would refuse the single most natural input for
    # this type — exactly as it once refused the Gantt CSV for xrange. networkgraph is now exempt
    # (it reads its two columns as node labels), so the file plots.
    app.segmented_control[0].set_value("Upload CSV").run()  # Source
    app.file_uploader[0].set_value(("edges.csv", _EDGE_LIST_CSV, "text/csv")).run()
    chart_type = next(sb for sb in app.selectbox if sb.label == "Chart type")
    chart_type.set_value("networkgraph").run()
    assert not app.exception
    assert not app.error  # NOT "this dataset has no numeric columns to plot"
    metrics = _metrics(app)
    assert metrics["Numeric columns"] == "0"  # ...and yet
    assert metrics["Links"] == "3"  # ...it plots every edge

    # The gate stays honest in the other direction: the same file on a type that really does need
    # a number must still be refused.
    chart_type = next(sb for sb in app.selectbox if sb.label == "Chart type")
    chart_type.set_value("line").run()
    assert app.error
    assert "no numeric columns" in app.error[0].value


def test_app_networkgraph_kpi_shows_links(app):
    # Networkgraph is one series of edges, so — like sankey — the KPI swaps "Series plotted"
    # (which would read a bare 1) for "Links" = the rows that become edges. The default dataset
    # has no missing node cells, so every row is an edge. This also proves the empty-Y guard
    # exempts networkgraph: the KPI (and the chart) render with no Y selected.
    from sample_data import SAMPLES

    app.selectbox[1].set_value("networkgraph").run()  # Chart type -> networkgraph
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    default_df = next(iter(SAMPLES.values()))()
    assert metrics["Links"] == f"{len(default_df):,}"


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
    assert not any(sb.label.startswith("Parent") for sb in app.selectbox)
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


def test_app_switch_to_waterfall_shows_single_select_y_and_regenerates_config(app):
    # Waterfall reads its Y as one column of signed deltas, so — like pie/treemap/sankey/
    # boxplot — it swaps the multi-select Y pills for a single selectbox. It needs no EXTRA
    # column selector (unlike bubble's Size and sankey's Target), so the widget indices are
    # unchanged. Network-free.
    app.selectbox[1].set_value("waterfall").run()  # Chart type -> waterfall
    assert not app.exception
    assert not app.pills  # single-select Y, so the pills are gone
    assert any(sb.label == "Step values (signed delta)" for sb in app.selectbox)
    assert not any(sb.label == "Size (Z)" for sb in app.selectbox)  # no extra selector
    assert not any(sb.label == "Target (to)" for sb in app.selectbox)
    assert not any(sb.label.startswith("Parent") for sb in app.selectbox)
    _reveal_config(app)
    assert not app.exception
    js = app.code[0].value
    assert "type: 'waterfall'" in js
    assert "isSum: true" in js  # the appended total reached the chart


def test_app_waterfall_kpi_shows_steps_including_the_appended_total(app):
    # Waterfall is one series of bars, so the KPI swaps "Series plotted" (which would read a
    # bare 1) for "Steps" — mirroring heatmap's "Cells", treemap's "Tiles", sankey's "Flows"
    # and boxplot's "Boxes". It is the one KPI that EXCEEDS the row count, because the
    # appended total is a bar the chart really draws; sourcing it from count_marks is what
    # keeps that true rather than merely asserted here.
    from highcharts_builder import count_marks
    from sample_data import SAMPLES

    app.selectbox[1].set_value("waterfall").run()  # Chart type -> waterfall
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    default_df = next(iter(SAMPLES.values()))()
    x_col = default_df.columns[0]  # the app's default X is the first column
    y_col = default_df.select_dtypes("number").columns[0]  # and Y the first numeric one
    expected = count_marks(default_df, "waterfall", x_col, [y_col])
    assert metrics["Steps"] == f"{expected:,}"
    assert expected == len(default_df) + 1  # every row a step, plus the total


def _pick_sunburst_sample(app):
    """Select the sunburst sample dataset and switch the chart type to sunburst.

    The DEFAULT dataset (monthly revenue vs cost) is not a hierarchy — its Parent column
    would default to `revenue`, whose numbers name no node — so every row dangles and the
    chart is legitimately empty. The KPI test needs a real tree to count.
    """
    from sample_data import SAMPLES

    label = next(key for key in SAMPLES if "(sunburst)" in key)
    app.selectbox[0].set_value(label).run()  # Dataset
    app.selectbox[1].set_value("sunburst").run()  # Chart type
    return SAMPLES[label]()


def test_app_switch_to_sunburst_shows_parent_control_and_regenerates_config(app):
    # Sunburst is the third type with a required extra column (after bubble's Size and
    # sankey's Target): it reveals a "Parent" selectbox no other type shows, and drives the
    # config through the parent_col plumbing. Addressed by LABEL, not index — like sankey's
    # Target it sits between the X and the single-select Y widgets, so the positional indices
    # past [2] shift. Network-free.
    assert not any(sb.label.startswith("Parent") for sb in app.selectbox)  # absent
    _pick_sunburst_sample(app)
    assert not app.exception
    parent = [sb for sb in app.selectbox if sb.label.startswith("Parent")]
    assert len(parent) == 1  # now present
    # Single-select Y (the leaf values), like pie/treemap/sankey/boxplot/waterfall.
    assert any(sb.label == "Leaf values" for sb in app.selectbox)
    assert not app.pills
    _reveal_config(app)
    assert not app.exception
    js = app.code[0].value
    assert "type: 'sunburst'" in js
    assert "allowTraversingTree: true" in js  # the drill-in survived to the chart


def test_app_sunburst_parent_survives_a_node_change(app):
    # The keyless-widget trap the Parent selectbox's constant `index` guards against, exactly
    # as sankey's Target does. These widgets carry no key, so Streamlit folds `index` into
    # their identity: a default derived from x_col (the tempting "the column after Node")
    # would re-mint the widget whenever Node changed, silently discarding the user's Parent.
    # A dynamic index makes this fail — nothing else in the suite would notice.
    _pick_sunburst_sample(app)  # columns: team, reports_to, headcount
    parent = next(sb for sb in app.selectbox if sb.label.startswith("Parent"))
    parent.set_value("headcount").run()  # the third column, not the default
    assert not app.exception
    app.selectbox[2].set_value("reports_to").run()  # Node: team -> reports_to
    assert not app.exception
    parent = next(sb for sb in app.selectbox if sb.label.startswith("Parent"))
    assert parent.value == "headcount"  # not reset to the default


def test_app_sunburst_node_equals_parent_shows_guard_warning(app):
    # Sunburst's own collision, sankey's one relation over: a node and its parent. Not the
    # x-in-y rule (the Parent column is never among the Y series). Every node would be its own
    # parent — a self-cycle in every row.
    _pick_sunburst_sample(app)
    parent = next(sb for sb in app.selectbox if sb.label.startswith("Parent"))
    parent.set_value("team").run()  # == the default Node column
    assert not app.exception  # the guard fires; it does NOT blow up the page
    assert app.warning
    assert "Node and Parent must be different" in app.warning[0].value
    # The KPI row runs ABOVE that guard, so it still renders — and it must render the SAME way
    # a cyclic CSV does (below), because they are the same contradiction. This is the assertion
    # that keeps the KPI from growing a special case: count_marks is total, so it reports the
    # true count of the chart about to be replaced by the warning. A `chart_type == "sunburst"
    # and x_col == parent_col` escape hatch here would read "Series plotted 1" instead, making
    # two identical situations display differently and breaking MARK_METRICS' one-branch
    # property. Nothing else in the suite would notice.
    metrics = _metrics(app)
    assert metrics["Sectors"] == "0"
    assert "Series plotted" not in metrics


def test_app_sunburst_a_contradictory_tree_reads_zero_sectors(app):
    # The other half of the pair above, on the other contradiction: a cyclic CSV reaches the
    # same guard block and must reach the same KPI. Pins the two together, so neither can grow
    # a special case the other doesn't.
    app.segmented_control[0].set_value("Upload CSV").run()  # Source
    app.file_uploader[0].set_value(
        ("cycle.csv", b"node,parent,value\na,b,1\nb,a,2\n", "text/csv")
    ).run()
    chart_type = next(sb for sb in app.selectbox if sb.label == "Chart type")
    chart_type.set_value("sunburst").run()
    assert not app.exception
    assert _metrics(app)["Sectors"] == "0"


def test_app_sunburst_a_cyclic_csv_warns_instead_of_crashing(app):
    # The one BUILDER error a user can reach just by uploading a file. The interactive path
    # doesn't catch, so the app has to stop on it first — and the KPI row runs ABOVE that
    # guard, which is why count_marks returns 0 on a contradictory tree rather than raising.
    # If it raised, this page would be a traceback instead of an explanation.
    app.segmented_control[0].set_value("Upload CSV").run()  # Source
    app.file_uploader[0].set_value(
        ("cycle.csv", b"node,parent,value\na,b,1\nb,a,2\n", "text/csv")
    ).run()
    # By LABEL, not index: the Upload CSV path has no Dataset selectbox, so every positional
    # index shifts by one against the sample-dataset path the other app tests use.
    chart_type = next(sb for sb in app.selectbox if sb.label == "Chart type")
    chart_type.set_value("sunburst").run()
    assert not app.exception  # NOT a traceback
    assert app.warning
    assert "is a cycle" in app.warning[0].value
    # The message is the builder's own — explain_tree_error returns the very string
    # build_options raises — so the warning can't drift from the exception it stands in for.
    assert "must describe a tree" in app.warning[0].value


def test_app_sunburst_kpi_shows_sectors_including_the_appended_root(app):
    # Sunburst is one series of sectors, so the KPI swaps "Series plotted" (which would read a
    # bare 1) for "Sectors" — mirroring heatmap's "Cells", treemap's "Tiles", sankey's "Flows",
    # boxplot's "Boxes" and waterfall's "Steps". It is the SECOND KPI that exceeds its row
    # count, because the appended root is a sector the chart really draws; sourcing it from
    # count_marks is what keeps that true rather than merely asserted here.
    from highcharts_builder import count_marks

    df = _pick_sunburst_sample(app)
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    expected = count_marks(
        df, "sunburst", "team", ["headcount"], parent_col="reports_to"
    )
    assert metrics["Sectors"] == f"{expected:,}"
    assert expected == len(df) + 1 == 16  # every node a sector, plus the root


# A real Gantt CSV: a lane column and two DATE columns, and so NOT ONE numeric column. This
# is the file the app used to refuse at the door — `select_dtypes("number")` is empty, and
# the no-numeric-columns gate ran ABOVE the chart-type picker and st.stop()ped the page.
_GANTT_CSV = (
    b"task,start,end\n"
    b"Design,2026-01-05,2026-02-10\n"
    b"Build,2026-02-01,2026-04-20\n"
    b"QA,2026-04-10,2026-05-15\n"
)


def _pick_xrange_sample(app):
    """Select the xrange sample dataset and switch the chart type to xrange.

    The DEFAULT dataset (monthly revenue vs cost) has no coordinate pair to span — and its
    `month` column is the very one that must NOT sniff as a date (see `_coordinates`) — so
    the KPI test needs the release plan to have bars to count.
    """
    from sample_data import SAMPLES

    label = next(key for key in SAMPLES if "(xrange)" in key)
    app.selectbox[0].set_value(label).run()  # Dataset
    app.selectbox[1].set_value("xrange").run()  # Chart type
    return SAMPLES[label]()


def test_app_switch_to_xrange_shows_end_control_and_regenerates_config(app):
    # Xrange is the fourth type with a required extra column (after bubble's Size, sankey's
    # Target and sunburst's Parent): it reveals an "End" selectbox no other type shows, and
    # drives the config through the end_col plumbing. Network-free.
    assert not any(sb.label == "End" for sb in app.selectbox)  # absent
    _pick_xrange_sample(app)
    assert not app.exception
    assert len([sb for sb in app.selectbox if sb.label == "End"]) == 1  # now present
    # Single-select Y — and it is labelled as a COORDINATE ("Start"), not a value, because it
    # says WHEN rather than HOW MUCH.
    assert any(sb.label == "Start" for sb in app.selectbox)
    assert not app.pills
    _reveal_config(app)
    assert not app.exception
    js = app.code[0].value
    assert "type: 'xrange'" in js
    assert "x2:" in js  # the extent survived to the chart
    assert "type: 'datetime'" in js  # ...and the ISO date strings became a time axis


def test_app_xrange_start_and_end_pickers_offer_only_coordinate_columns(app):
    # Both are sourced from the builder's `coordinate_columns`, so a picker cannot offer a
    # column the builder would only turn around and reject. `workstream` is text — it names a
    # lane, it cannot place a bar on an axis — so it must not appear in either.
    _pick_xrange_sample(app)
    start = next(sb for sb in app.selectbox if sb.label == "Start")
    end = next(sb for sb in app.selectbox if sb.label == "End")
    for picker in (start, end):
        assert "workstream" not in picker.options
        assert set(picker.options) == {"start", "end", "headcount"}


def test_app_xrange_end_survives_a_lane_change(app):
    # The keyless-widget trap the End selectbox's constant `index` guards against, exactly as
    # sankey's Target and sunburst's Parent do. A default derived from the Start column (the
    # tempting "the column after Start") would re-mint the widget whenever Start changed,
    # silently discarding the user's End. A dynamic index makes this fail — nothing else in
    # the suite would notice.
    _pick_xrange_sample(app)  # columns: workstream, start, end, headcount
    end = next(sb for sb in app.selectbox if sb.label == "End")
    end.set_value("headcount").run()  # not the default
    assert not app.exception
    app.selectbox[2].set_value("start").run()  # Lane: workstream -> start
    assert not app.exception
    end = next(sb for sb in app.selectbox if sb.label == "End")
    assert end.value == "headcount"  # not reset to the default


def test_app_xrange_start_equals_end_shows_guard_warning(app):
    # Xrange's own collision, the third of these: a bar's two ends. Not the x-in-y rule (the
    # End column is never among the Y series). It must be GUARDED rather than tolerated
    # because it fails silently — every bar would be zero-length, so the chart would come back
    # as a column of milestone slivers rather than as anything anyone asked for.
    _pick_xrange_sample(app)
    end = next(sb for sb in app.selectbox if sb.label == "End")
    end.set_value("start").run()  # == the Start column
    assert not app.exception  # the guard fires; it does NOT blow up the page
    assert app.warning
    assert "Start and End must be different" in app.warning[0].value


def test_app_xrange_a_date_start_beside_a_numeric_end_warns_instead_of_crashing(app):
    # The SECOND builder error a user can reach without writing any code (sunburst's cyclic CSV
    # was the first). The interactive path doesn't catch, so the app has to stop on it — and
    # the KPI row runs ABOVE that guard, which is why count_marks returns 0 on a contradictory
    # column pair rather than raising. If it raised, this page would be a traceback.
    #
    # A TEXT start is the other contradiction, but it is unreachable from the app by
    # construction: `coordinate_columns` keeps a column of task names out of both pickers (see
    # the test above), which is the point of sourcing them from the builder. The date-beside-a-
    # number mismatch is the one a user CAN still select, so that is the one to drive here.
    app.segmented_control[0].set_value("Upload CSV").run()  # Source
    app.file_uploader[0].set_value(
        (
            "mixed.csv",
            b"task,start,end,sprint\nDesign,2026-01-05,2026-02-10,3\n",
            "text/csv",
        )
    ).run()
    chart_type = next(sb for sb in app.selectbox if sb.label == "Chart type")
    chart_type.set_value("xrange").run()
    end = next(sb for sb in app.selectbox if sb.label == "End")
    end.set_value("sprint").run()  # a NUMBER beside a DATE start
    assert not app.exception  # NOT a traceback
    assert app.warning
    # The message is the builder's own — explain_xrange_error returns the very string
    # build_options raises — so the warning can't drift from the exception it stands in for.
    assert "must be the same kind" in app.warning[0].value
    # ...and the KPI reports the true count of the chart about to be replaced by that warning.
    assert _metrics(app)["Bars"] == "0"


def test_app_xrange_plots_a_csv_with_no_numeric_columns_at_all(app):
    # THE GATE. A real Gantt CSV is a lane column and two DATE columns — and a date column is
    # object dtype, so `select_dtypes("number")` finds NOTHING in it. The no-numeric-columns
    # gate used to run above the chart-type picker and st.stop() the page, so this file — the
    # single most natural input for this chart type — was refused before xrange could even be
    # chosen. The gate now runs BELOW the picker and asks the question the type actually has.
    app.segmented_control[0].set_value("Upload CSV").run()  # Source
    app.file_uploader[0].set_value(("gantt.csv", _GANTT_CSV, "text/csv")).run()
    chart_type = next(sb for sb in app.selectbox if sb.label == "Chart type")
    chart_type.set_value("xrange").run()
    assert not app.exception
    assert not app.error  # NOT "this dataset has no numeric columns to plot"
    metrics = _metrics(app)
    assert metrics["Numeric columns"] == "0"  # ...and yet
    assert metrics["Bars"] == "3"  # ...it plots

    # The gate stays honest in the other direction: the same file on a type that really does
    # need a number must still be refused.
    chart_type = next(sb for sb in app.selectbox if sb.label == "Chart type")
    chart_type.set_value("line").run()
    assert app.error
    assert "no numeric columns" in app.error[0].value


def test_app_xrange_kpi_shows_bars(app):
    # Xrange is one series of bars, so the KPI swaps "Series plotted" (which would read a bare
    # 1) for "Bars" — mirroring heatmap's "Cells", treemap's "Tiles", sankey's "Flows",
    # boxplot's "Boxes", waterfall's "Steps" and sunburst's "Sectors". Unlike the last two it
    # appends nothing, so its count is exactly its surviving rows — the milestone included,
    # because the builder floors that bar to a visible sliver rather than dropping it.
    df = _pick_xrange_sample(app)
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    expected = count_marks(df, "xrange", "workstream", ["start"], end_col="end")
    assert metrics["Bars"] == f"{expected:,}"
    assert (
        expected == len(df) == 8
    )  # every row a bar; nothing appended, nothing dropped


def _pick_columnrange_sample(app):
    """Select the columnrange sample dataset and switch the chart type to columnrange.

    The DEFAULT dataset (monthly revenue vs cost) would build a columnrange too, but the
    temperature sample is the one whose two numeric columns ARE a low and a high, so the KPI
    and picker tests read the numbers the type is meant to draw."""
    from sample_data import SAMPLES

    label = next(key for key in SAMPLES if "(columnrange)" in key)
    app.selectbox[0].set_value(label).run()  # Dataset
    app.selectbox[1].set_value("columnrange").run()  # Chart type
    return SAMPLES[label]()


def test_app_switch_to_columnrange_shows_high_control_and_regenerates_config(app):
    # Columnrange is the fifth type with a required extra column (after bubble's Size, sankey's
    # Target, sunburst's Parent and xrange's End): it reveals a "High (top)" selectbox no other
    # type shows, and drives the config through the high_col plumbing. Network-free.
    assert not any(sb.label == "High (top)" for sb in app.selectbox)  # absent
    _pick_columnrange_sample(app)
    assert not app.exception
    assert (
        len([sb for sb in app.selectbox if sb.label == "High (top)"]) == 1
    )  # now present
    # Single-select Y, labelled as a MAGNITUDE ("Low (bottom)") — one end of the range, not a
    # coordinate like xrange's "Start". No pills.
    assert any(sb.label == "Low (bottom)" for sb in app.selectbox)
    assert not app.pills
    _reveal_config(app)
    assert not app.exception
    assert "type: 'columnrange'" in app.code[0].value


def test_app_columnrange_low_and_high_pickers_offer_only_numeric_columns(app):
    # High is a MAGNITUDE, sourced from numeric_cols — NOT coordinate_columns like xrange's End,
    # because a high can never be a date. `month` is a category, so it must appear in NEITHER
    # value picker (the mirror of xrange excluding its text lane column from its coordinate ones).
    _pick_columnrange_sample(app)  # columns: month, record_low, record_high
    low = next(sb for sb in app.selectbox if sb.label == "Low (bottom)")
    high = next(sb for sb in app.selectbox if sb.label == "High (top)")
    for picker in (low, high):
        assert "month" not in picker.options
        assert set(picker.options) == {"record_low", "record_high"}


def test_app_columnrange_high_survives_a_low_change(app):
    # The keyless-widget trap High's constant `index` guards against, exactly as xrange's End,
    # sankey's Target and sunburst's Parent do. A default derived from the current Low would
    # re-mint High whenever Low changed, silently discarding the user's pick. A 3-numeric CSV
    # gives room to change Low without colliding with High.
    app.segmented_control[0].set_value("Upload CSV").run()  # Source
    app.file_uploader[0].set_value(
        ("ranges.csv", b"category,a,b,c\nX,1,5,9\nY,2,6,10\n", "text/csv")
    ).run()
    chart_type = next(sb for sb in app.selectbox if sb.label == "Chart type")
    chart_type.set_value("columnrange").run()
    high = next(sb for sb in app.selectbox if sb.label == "High (top)")
    high.set_value("c").run()  # not the default (which is the 2nd numeric, "b")
    assert not app.exception
    low = next(sb for sb in app.selectbox if sb.label == "Low (bottom)")
    low.set_value("b").run()  # change Low a -> b
    assert not app.exception
    high = next(sb for sb in app.selectbox if sb.label == "High (top)")
    assert high.value == "c"  # not reset to the default


def test_app_columnrange_low_equals_high_shows_guard_warning(app):
    # Columnrange's own collision, xrange's one type over: a bar's low and high. Not the x-in-y
    # rule (High is the high_col selector, never among the Y series). It must be GUARDED rather
    # than tolerated because it fails silently — every bar would span zero height.
    _pick_columnrange_sample(app)  # Low defaults record_low, High defaults record_high
    high = next(sb for sb in app.selectbox if sb.label == "High (top)")
    high.set_value("record_low").run()  # == the Low column
    assert not app.exception  # the guard fires; it does NOT blow up the page
    assert app.warning
    assert "Low and High must be different" in app.warning[0].value


def test_app_columnrange_kpi_shows_ranges(app):
    # Columnrange is one series of low/high bars, so the KPI swaps "Series plotted" (which would
    # read a bare 1) for "Ranges" — mirroring heatmap's "Cells", xrange's "Bars" and the rest.
    # One bar per category, nothing appended or dropped, so its count is exactly its rows.
    df = _pick_columnrange_sample(app)
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    expected = count_marks(df, "columnrange", "month", ["record_low"])
    assert metrics["Ranges"] == f"{expected:,}"
    assert expected == len(df) == 12


def test_app_heatmap_kpi_shows_cells_from_count_marks(app):
    # Heatmap swaps "Series plotted" for "Cells", sourced from the builder's count_marks so
    # the KPI can't drift from the grid the chart draws. Assert the app's number equals
    # count_marks on the default selection (X = first column, Y = first numeric column).
    from highcharts_builder import count_marks
    from sample_data import SAMPLES

    app.selectbox[1].set_value("heatmap").run()  # Chart type -> heatmap
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    default_df = next(iter(SAMPLES.values()))()
    x = default_df.columns[0]
    y = [default_df.select_dtypes("number").columns[0]]
    assert metrics["Cells"] == f"{count_marks(default_df, 'heatmap', x, y):,}"


def test_app_treemap_kpi_shows_tiles_from_count_marks(app):
    # Treemap swaps "Series plotted" for "Tiles", likewise from count_marks (rows with a
    # drawable label AND a plottable value), so the KPI matches the tiles actually laid out.
    from highcharts_builder import count_marks
    from sample_data import SAMPLES

    app.selectbox[1].set_value("treemap").run()  # Chart type -> treemap
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    default_df = next(iter(SAMPLES.values()))()
    x = default_df.columns[0]
    y = [default_df.select_dtypes("number").columns[0]]
    assert metrics["Tiles"] == f"{count_marks(default_df, 'treemap', x, y):,}"


@pytest.mark.parametrize("chart_type", ["funnel", "pyramid"])
def test_app_funnel_family_kpi_shows_stages_from_count_marks(app, chart_type):
    # Funnel/pyramid swap "Series plotted" for "Stages", from count_marks (rows with a drawable
    # label AND a plottable value) — unlike their twin pie, which opts out and shows a bare 1. So
    # the KPI matches the stages actually drawn.
    from highcharts_builder import count_marks
    from sample_data import SAMPLES

    app.selectbox[1].set_value(chart_type).run()  # Chart type -> funnel / pyramid
    assert not app.exception
    metrics = _metrics(app)
    assert "Series plotted" not in metrics
    default_df = next(iter(SAMPLES.values()))()
    x = default_df.columns[0]
    y = [default_df.select_dtypes("number").columns[0]]
    assert metrics["Stages"] == f"{count_marks(default_df, chart_type, x, y):,}"


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


# The gauge family's app tests are PARAMETRIZED over GAUGE_TYPES rather than written twice, and
# that is the point rather than a saving. Every behaviour below — the absent X control, the
# builder-sourced aggregation picker, the builder-seeded keyless dial and both halves of its
# re-mint rule, the no-span warning, the KPI — belongs to the FAMILY: it follows from having no
# label channel and from reducing whole columns against one dial, which is exactly what
# `GAUGE_TYPES` means. A second copy would let the two drift, and the drift would be invisible.
# Only the emitted `chart.type` is per-type, and it is threaded through as a literal.
def _gauge_app(app, chart_type: str):
    """Switch the app to one of the gauge types and return it. The default dataset works: its
    numerics are revenue/cost, which either gauge happily reduces."""
    app.selectbox[1].set_value(chart_type).run()  # Chart type
    assert not app.exception
    return app


@pytest.mark.parametrize("chart_type", GAUGE_TYPES)
def test_app_switch_to_gauge_hides_the_x_control_and_shows_the_dial_controls(
    app, chart_type
):
    # The ONLY SUBTRACTIVE control change in this app: every other type's extra widget is
    # additive (bubble's Size, sankey's Target, sunburst's Parent, xrange's End), but the gauge
    # family REMOVES the X selectbox — no label channel, so a control there would do nothing,
    # and a control that does nothing is a lie in the UI.
    assert any(sb.label == "Category (X) axis" for sb in app.selectbox)
    _gauge_app(app, chart_type)
    assert not any(sb.label == "Category (X) axis" for sb in app.selectbox)
    assert any(sb.label == "Reduce each column by" for sb in app.selectbox)
    assert [n.label for n in app.number_input] == ["Dial min", "Dial max"]
    # Multi-select Y: each column is one mark (a ring, or a needle).
    assert app.pills
    _reveal_config(app)
    assert not app.exception
    assert f"type: '{chart_type}'" in app.code[0].value
    # The solid gauge's pane is what resolves highcharts-more — without it the iframe is silently
    # blank while the PNG renders perfectly. The needle's pane is only geometry (it resolves the
    # module from chart.type alone), but both emit one, so the assertion holds for the family.
    assert "pane" in app.code[0].value


@pytest.mark.parametrize("chart_type", GAUGE_TYPES)
def test_app_gauge_aggregation_picker_offers_exactly_the_builders_reductions(
    app, chart_type
):
    # Sourced from the builder, so the app can never offer a reduction the builder rejects —
    # `coordinate_columns`' can't-drift rule, applied to a POLICY rather than to a column.
    _gauge_app(app, chart_type)
    picker = next(sb for sb in app.selectbox if sb.label == "Reduce each column by")
    assert list(picker.options) == list(GAUGE_AGGREGATIONS)


@pytest.mark.parametrize("chart_type", GAUGE_TYPES)
def test_app_gauge_dial_defaults_come_from_the_builder(app, chart_type):
    # The can't-drift rule applied to a widget's VALUE rather than to its options: the number the
    # app SHOWS is the very dial the chart DRAWS. The app must not recompute it — a max derived
    # here from the raw column would be smaller than every reading under `sum`, pinning every mark
    # at 100% with nothing on the page to say why.
    from sample_data import SAMPLES

    _gauge_app(app, chart_type)
    df = next(iter(SAMPLES.values()))()
    y_cols = [p for p in app.pills[0].value]
    low, high = gauge_dial(df, y_cols, "sum")
    assert [n.value for n in app.number_input] == [low, high]


@pytest.mark.parametrize("chart_type", GAUGE_TYPES)
def test_app_gauge_dial_override_reaches_the_chart_and_survives_an_inert_rerun(
    app, chart_type
):
    # HALF ONE of the keyless-widget decision. A typed dial is scoped to its derivation, not to
    # every rerun: it survives a change that cannot affect it (the title).
    _gauge_app(app, chart_type)
    app.number_input[1].set_value(1000.0).run()
    assert not app.exception
    _reveal_config(app)
    assert "max:1000" in "".join(app.code[0].value.split())  # it reached the chart
    app.text_input[0].set_value("A different title").run()  # inert w.r.t. the dial
    assert not app.exception
    assert app.number_input[1].value == 1000.0  # the override stands


@pytest.mark.parametrize("chart_type", GAUGE_TYPES)
def test_app_gauge_dial_re_mints_when_the_aggregation_changes(app, chart_type):
    # HALF TWO, and the reason there is NO `key=` on these inputs. A dial derives from the DATA
    # under a REDUCTION, so an override of it is meaningless the moment either changes: a max of
    # 500 typed against `sum` would leave every mark at ~1% under `mean`. A `key=` is how you
    # would CAUSE that — with a key, `value=` is honoured only on the FIRST render, so the stale
    # number would become permanent and silent. Re-minting is the INTENDED behaviour here, and
    # it is visible: the box shows the newly derived number.
    _gauge_app(app, chart_type)
    app.number_input[1].set_value(9999.0).run()
    assert app.number_input[1].value == 9999.0
    picker = next(sb for sb in app.selectbox if sb.label == "Reduce each column by")
    picker.set_value("mean").run()  # the derivation changed
    assert not app.exception
    assert app.number_input[1].value != 9999.0  # re-derived, not carried over


@pytest.mark.parametrize("chart_type", GAUGE_TYPES)
def test_app_gauge_a_dial_with_no_span_warns_instead_of_crashing(app, chart_type):
    # The third builder error reachable from this page (after sunburst's cycle and xrange's
    # axis mismatch), and the first that is not about a COLUMN at all: two number inputs accept
    # any two numbers, so a max at or below the min is one keystroke away. The interactive path
    # does not catch builder errors, so this must warn and stop rather than throw a traceback.
    _gauge_app(app, chart_type)
    app.number_input[1].set_value(-10.0).run()  # max below min
    assert not app.exception
    assert app.warning
    assert "must be a finite number above its minimum" in app.warning[0].value


@pytest.mark.parametrize("chart_type", GAUGE_TYPES)
def test_app_gauge_kpi_counts_the_marks_as_series(app, chart_type):
    # The family is deliberately absent from MARK_METRICS: its marks ARE its series, so the
    # default "Series plotted" is already literally the ring/needle count. An entry would force a
    # count_marks rule that only restated len(y_cols) — the can't-drift rule run backwards.
    _gauge_app(app, chart_type)
    metrics = _metrics(app)
    assert metrics["Series plotted"] == str(len(app.pills[0].value))


def test_app_needle_gauge_y_control_names_the_mark_it_draws(app):
    # The one place the two types' controls DIFFER, and the reason it is worth differing: a
    # reader picking columns should be told what each one will BECOME. Same widget, same
    # cardinality, different noun.
    _gauge_app(app, "solidgauge")
    assert "Rings" in app.pills[0].label
    _gauge_app(app, "gauge")
    assert "Needles" in app.pills[0].label
