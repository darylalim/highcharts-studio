"""Streamlit example app that renders ONLY Highcharts visualizations.

Every chart on this page is produced by the Highcharts for Python toolkit
(``highcharts-core``): a pandas DataFrame is turned into a Highcharts options
object, then shown one of two ways — embedded via ``st.iframe`` or rendered
server-side to a PNG. No Streamlit-native charts are used.

Run it with:

    uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

from typing import Literal

import pandas as pd
import streamlit as st

from highcharts_builder import (
    FUNNEL_TYPES,
    GAUGE_AGGREGATIONS,
    GAUGE_TYPES,
    MAGNITUDE_RANGE_TYPES,
    NODE_LINK_TYPES,
    ORGANIZATION_TYPES,
    SUPPORTED_TYPES,
    UNWEIGHTED_NODE_LINK_TYPES,
    WEIGHTED_NODE_LINK_TYPES,
    X_IN_Y_GUARD_TYPES,
    build_chart_html,
    build_chart_png,
    coordinate_columns,
    count_marks,
    explain_export_failure,
    explain_gauge_error,
    explain_tree_error,
    explain_xrange_error,
    gauge_dial,
    make_chart,
)
from sample_data import SAMPLES

# Render modes for the "3 · Render" control.
MODE_INTERACTIVE = "Interactive"
MODE_STATIC = "Static PNG"
RENDER_MODES = [MODE_INTERACTIVE, MODE_STATIC]

# Above this many numeric columns the Y-series pills would wrap the narrow
# sidebar, so fall back to st.multiselect (selection-widgets.md bounds pills at
# ~5 options).
MAX_PILL_OPTIONS = 5

# Short status badge (label, icon, color) shown above the chart per mode; the
# caption below the chart carries the full description.
_BadgeColor = Literal["blue", "violet"]
MODE_BADGES: dict[str, tuple[str, str, _BadgeColor]] = {
    MODE_INTERACTIVE: ("Interactive (iframe)", ":material/public:", "blue"),
    MODE_STATIC: ("Static PNG", ":material/image:", "violet"),
}

# The one-series types, and the mark each one draws. These render a SINGLE series (of
# cells/tiles/flows/boxes/steps), so the default "Series plotted" metric would misreport
# them as a bare 1; they show their mark count instead, sourced from the builder's
# count_marks. Membership of this dict is what makes a type count-adaptive, so the KPI
# below stays one branch however many such types there are. Every other type plots one
# series per y column, where len(y_cols) IS the series count.
MARK_METRICS = {
    "heatmap": "Cells",
    "treemap": "Tiles",
    # Funnel and its inverted mirror pyramid opt INTO the count-adaptive KPI, unlike their
    # structural twin pie (whose omission is an unjustified gap). Their one series' points are the
    # stages, so the default "Series plotted" would misreport them as a bare 1; instead the KPI
    # shows the drawable-stage count from count_marks (a valueless stage dropped like a pie slice),
    # which meaningfully differs from the row count when a value can't be plotted.
    "funnel": "Stages",
    "pyramid": "Stages",
    "sankey": "Flows",
    # Dependencywheel is sankey's circular twin — the same single weighted-link series, so its
    # default "Series plotted" would misreport as a bare 1 exactly as sankey's does. Its marks are
    # the same {from, to, weight} links, so it shares sankey's count_marks rule AND its "Flows"
    # label: the KPI counts the same thing for the flow and the ring.
    "dependencywheel": "Flows",
    # Networkgraph is the OTHER single-series node-link type, so — like sankey — its default
    # "Series plotted" would misreport its one edge-series as a bare 1. Its marks are the edges,
    # counted by count_marks (one per drawable row, both node ends present). It needs this entry
    # for the same reason sankey does, and — unlike the gauge family, its mirror in having a
    # subtractive control — it is NOT a `marks == len(y_cols)` type: its y_cols is empty.
    "networkgraph": "Links",
    # Organization is the fourth node-link type — also single-series (one org series), so its
    # default "Series plotted" would misreport as a bare 1. Its marks are the REPORTING LINES
    # (one per employee with a real manager; a root/CEO draws a box but no line), counted by the
    # same both-ends-present predicate as networkgraph but reading "Reports". A blank manager is a
    # root, not an edge, so the count uses `not _is_top_level` there rather than `_label_ok`.
    "organization": "Reports",
    "boxplot": "Boxes",
    "waterfall": "Steps",  # counts the appended Total, as the chart draws it
    "sunburst": "Sectors",  # likewise counts the appended root — the other appending type
    # Xrange appends nothing, so unlike those two its count never exceeds its row count: one
    # bar per surviving row. A zero-length bar (a milestone) IS one of them — the builder
    # floors it to a visible sliver rather than dropping it, so counting it is honest.
    "xrange": "Bars",
    # Columnrange is a single low/high series like xrange is a single lane-bar series, so its
    # default "Series plotted" would misreport as 1 too. Its marks are the floating bars, one
    # per surviving category — a missing/inverted range keeps its slot as a null bar and still
    # counts (waterfall's rule without the appended total, so it never exceeds the row count).
    "columnrange": "Ranges",
    # Arearange is columnrange's filled-band mirror — one continuous band, so its single series
    # would misreport as a bare 1 exactly as columnrange's does. Its marks are the (low, high)
    # POINTS the band is sampled at (one per surviving category, shared count_marks rule), so it
    # is count-adaptive too. The noun differs from columnrange's "Ranges" deliberately: a band is
    # ONE shape, so "Points" describes what is counted (its vertices) rather than implying N
    # discrete ranges.
    "arearange": "Points",
    # Gauge is deliberately ABSENT, and it is the first type whose absence is worth stating.
    # Its marks ARE its series — one ring per y column, and a column with no data keeps its ring
    # as a null rather than being dropped — so "Series plotted" is already literally the ring
    # count. An entry here would force a `count_marks` rule that did nothing but restate
    # `len(y_cols)`: the can't-drift rule run backwards, a second computation of a fact that
    # cannot differ from the first. (`count_marks` raises for it, exactly as it does for line.)
}

st.set_page_config(
    page_title="Highcharts Studio",
    page_icon=":material/insights:",
    layout="wide",
)


# max_entries bounds each cache so entries are evicted LRU instead of piling up
# as users sweep chart types, columns, heights, and titles. The memory-heavy
# layers get the tighter caps: an uploaded CSV DataFrame can be multi-MB
# (load_csv=8) and the PNG bytes are large (=64); the HTML and JS are small
# strings that share the looser 128 cap.
@st.cache_data(show_spinner=False, max_entries=8)
def load_csv(file) -> pd.DataFrame:
    return pd.read_csv(file)


@st.cache_data(show_spinner="Rendering Highcharts…", max_entries=128)
def cached_chart_html(
    df,
    chart_type,
    x_col,
    y_cols,
    height,
    title,
    dark,
    size_col,
    target_col,
    parent_col,
    end_col,
    high_col,
    title_col,
    agg,
    dial,
) -> str:
    return build_chart_html(
        df,
        chart_type,
        x_col,
        list(y_cols),
        height=height,
        title=title,
        dark=dark,
        size_col=size_col,
        target_col=target_col,
        parent_col=parent_col,
        end_col=end_col,
        high_col=high_col,
        title_col=title_col,
        agg=agg,
        dial=dial,
    )


@st.cache_data(
    show_spinner="Rendering PNG via the Highcharts export server…", max_entries=64
)
def cached_chart_png(
    df,
    chart_type,
    x_col,
    y_cols,
    height,
    title,
    dark,
    size_col,
    target_col,
    parent_col,
    end_col,
    high_col,
    title_col,
    agg,
    dial,
) -> bytes:
    return build_chart_png(
        df,
        chart_type,
        x_col,
        list(y_cols),
        height=height,
        title=title,
        dark=dark,
        size_col=size_col,
        target_col=target_col,
        parent_col=parent_col,
        end_col=end_col,
        high_col=high_col,
        title_col=title_col,
        agg=agg,
        dial=dial,
    )


@st.cache_data(show_spinner=False, max_entries=128)
def cached_chart_js(
    df,
    chart_type,
    x_col,
    y_cols,
    title,
    dark,
    size_col,
    target_col,
    parent_col,
    end_col,
    high_col,
    title_col,
    agg,
    dial,
) -> str:
    # highcharts-core stubs `to_js_literal` as `str | None`; it returns the JS
    # literal string for a built chart.
    return make_chart(  # ty: ignore[invalid-return-type]
        df,
        chart_type,
        x_col,
        list(y_cols),
        title=title,
        dark=dark,
        size_col=size_col,
        target_col=target_col,
        parent_col=parent_col,
        end_col=end_col,
        high_col=high_col,
        title_col=title_col,
        agg=agg,
        dial=dial,
    ).to_js_literal()


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.title(":material/insights: Highcharts Studio")
st.caption(
    "Every chart below is rendered by **highcharts-core** (the Highcharts for "
    "Python toolkit) — embedded as an interactive iframe or a static PNG — with "
    "no native Streamlit charts."
)


# --------------------------------------------------------------------------- #
# Sidebar — data source + chart configuration
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header(":material/database: 1 · Data")
    source = (
        st.segmented_control(
            "Source", ["Sample dataset", "Upload CSV"], default="Sample dataset"
        )
        or "Sample dataset"
    )

    if source == "Sample dataset":
        name = st.selectbox("Dataset", list(SAMPLES))
        df = SAMPLES[name]()
    else:
        uploaded = st.file_uploader("CSV file", type="csv")
        if uploaded is None:
            st.info(
                "Upload a CSV, or switch to a sample dataset.",
                icon=":material/upload_file:",
            )
            st.stop()
        df = load_csv(uploaded)

    numeric_cols = df.select_dtypes("number").columns.tolist()
    # The columns that can place an xrange bar on an axis: numbers OR dates. A superset of
    # numeric_cols, and sourced from the builder (see `coordinate_columns`) so a picker can
    # never offer a column the builder would refuse. A date column is object dtype, so it is
    # invisible to `select_dtypes("number")` — which is exactly why the gate below could not
    # stay where it was: the canonical Gantt CSV (`task,start,end`, all dates) has NO numeric
    # columns at all, and the old gate stopped the app dead before the chart-type picker was
    # ever drawn. The gate has to know which type is being asked for, so it now runs AFTER it.
    coord_cols = coordinate_columns(df)

    st.header(":material/bar_chart: 2 · Chart")
    chart_type = st.selectbox(
        "Chart type",
        SUPPORTED_TYPES,
        help=(
            "How the type reshapes the controls below:\n"
            "- **pie** — one label column + one value column\n"
            "- **treemap** — one label column + one value column; each tile's "
            "area shows the value (scales to more categories than a pie)\n"
            "- **funnel / pyramid** — one **stage-label** column + one value column; "
            "each stage is a band sized by its value, drawn in row order (a `funnel` "
            "puts the first row at the top and narrows down; a `pyramid` puts it at the "
            "base and narrows up to an apex)\n"
            "- **scatter** — an X column paired with one or more numeric Y series\n"
            "- **bubble** — scatter plus a numeric Size (Z) column driving each "
            "marker's area\n"
            "- **radar** — a category X axis with one or more numeric Y series, "
            "drawn on polar (spider/web) axes\n"
            "- **sankey** — a Source and a Target column of node names plus a "
            "numeric flow value; each link's width shows how much moves from one "
            "node to the next\n"
            "- **dependencywheel** — the same Source, Target and flow value as sankey, "
            "drawn as a circle: nodes sit on a ring and each curved ribbon's width shows "
            "the flow between them (best when nodes are both sources and targets)\n"
            "- **networkgraph** — a Source and a Target column of node names (no value "
            "column); each row is one edge, laid out as a force-directed graph of who "
            "connects to whom\n"
            "- **organization** — an org chart, one row per person: an **Employee** column, "
            "a **Manager** column (blank = the top of the chart, e.g. the CEO), and a **Title** "
            "column drawn inside each box (no value column). The boxes are laid out top-down as a "
            "reporting hierarchy\n"
            "- **heatmap** — a category X axis and one or more numeric Y columns "
            "form a grid (each selected column becomes a row); each cell's color "
            "shows its value\n"
            "- **boxplot** — a category X column whose values *repeat* (one row per "
            "observation) + one numeric column of raw measurements; each category's "
            "distribution becomes a box, with outliers drawn as separate dots\n"
            "- **waterfall** — a step-label column + one numeric column of signed "
            "*deltas* (not levels); each bar floats where the last one ended, showing "
            "how a starting value becomes an ending one, and a closing **Total** bar is "
            "added for you\n"
            "- **sunburst** — a hierarchy, one row per node: a Node column, a **Parent** "
            "column naming that node's parent (blank = a top-level branch), and one "
            "numeric column of *leaf* values. Each ring is a level, and a parent's arc is "
            "the **sum** of its children — so a node with children needs no value of its "
            "own. Every node needs its own row, and click a sector to zoom into it\n"
            "- **xrange** — a Gantt-style timeline, one row per bar: a **Lane** column "
            "naming the task (it may repeat — a lane can hold several bars), plus a "
            "**Start** and an **End** column. Those two are *coordinates*, so they may be "
            "dates (ISO-8601, e.g. `2026-01-05`) or plain numbers (sprint 12 → 18) — but "
            "both the same kind. A zero-length bar is a **milestone** and still draws; a "
            "backwards one is dropped\n"
            "- **columnrange** — a category X axis + a **Low** and a **High** numeric column; "
            "each category gets a bar floating from its low to its high (a min–max range). A "
            "row missing either end draws no bar but keeps its slot; an inverted range "
            "(high < low) still draws, spanning both values\n"
            "- **arearange** — the same **Low** and **High** columns as columnrange, but drawn as "
            "one continuous **filled band** between a low line and a high line (best when the X "
            "axis is an ordered progression, e.g. a forecast band over time). A row missing either "
            "end breaks the band there; an inverted range still draws\n"
            "- **solidgauge / gauge** — one mark per **numeric column**, each collapsed to a "
            "single number by the aggregation you choose (sum / mean / …), all read against one "
            "shared dial. There is **no X column**: a gauge has no labels, only readings. "
            "`solidgauge` sweeps an **arc** per column; `gauge` points a **needle** per column "
            "at a scale it actually draws\n"
            "- **line / spline / area / areaspline / column / bar** — a category X axis with "
            "one or more numeric Y series"
        ),
    )

    # The no-plottable-columns gate. It runs HERE, below the chart-type picker, because the
    # answer depends on the type. MOST types need a NUMBER, but three do not, and each is exempted:
    # xrange's start/end are coordinates and may be dates — and a date column is object dtype, so a
    # real Gantt CSV (`task,start,end`, all dates) has no numeric columns whatsoever — while the two
    # UNWEIGHTED node-link types read their columns as node/title LABELS and need no number at all,
    # so the canonical edge-list CSV (`source,target`, both text) and a plain reporting roster
    # (`employee,manager,title`, all text) likewise have none. Gating on numeric_cols before
    # the picker was drawn refused those files at the door, with a message about a requirement the
    # type does not have. Neither unweighted type needs a gate of its own: with fewer than two
    # columns the Source == Target guard in the main panel says so.
    if chart_type == "xrange" and not coord_cols:
        st.error(
            "This dataset has no date or number columns to place a bar on.",
            icon=":material/error:",
        )
        st.stop()
    if (
        chart_type != "xrange"
        and chart_type not in UNWEIGHTED_NODE_LINK_TYPES
        and not numeric_cols
    ):
        st.error(
            "This dataset has no numeric columns to plot.", icon=":material/error:"
        )
        st.stop()

    if chart_type == "pie":
        x_label, y_label, multi = "Slice labels", "Slice values", False
    elif chart_type == "treemap":
        # Single-value shape like pie: one label column + one value column.
        x_label, y_label, multi = "Tile labels", "Tile values", False
    elif chart_type in FUNNEL_TYPES:
        # Pie's single-value shape (one label column names each stage, one value column sizes
        # it), so single-select Y like pie/treemap. "Stage" for both — a pyramid is a funnel
        # read the other way up, not a different data shape. A second value column would be a
        # second funnel, which is a second chart. Keyed on the shared FUNNEL_TYPES constant (not a
        # re-listed literal) so the family can't drift between builder and app — the
        # X_IN_Y_GUARD_TYPES / GAUGE_TYPES rule.
        x_label, y_label, multi = "Stage labels", "Stage values", False
    elif chart_type in WEIGHTED_NODE_LINK_TYPES:
        # The two WEIGHTED node-link types — sankey and its circular twin dependencywheel — read
        # the identical shape: two label columns naming a link's ends (the X selectbox plus the
        # Target one below) and one numeric column weighting it. Keyed on the shared constant (not
        # a re-listed literal) so the family can't drift between builder and app, exactly as
        # FUNNEL_TYPES / NODE_LINK_TYPES are.
        x_label, y_label, multi = "Source (from)", "Flow value (weight)", False
    elif chart_type == "networkgraph":
        # Sankey's cousin: two label columns naming an edge's ends (the X selectbox plus the
        # Target one below) and NO value column — the graph is unweighted, so there is no Y
        # control at all (skipped in the y_cols block below). `y_label`/`multi` go unused, but
        # every branch here assigns the triple, so they are set for the shape rather than left
        # dangling. This is the MIRROR of the gauge family: gauge has a value but no label (no X),
        # networkgraph a label but no value (no Y).
        x_label, y_label, multi = "Source (from)", "", False
    elif chart_type in ORGANIZATION_TYPES:
        # The fourth node-link type: one row per person — the employee (this X selectbox), their
        # manager (the Target selectbox below, relabelled "Manager") and a job title (the Title
        # selectbox below). UNWEIGHTED like networkgraph, so no Y control at all (skipped in the
        # y_cols block below); `y_label`/`multi` are assigned for the shape but go unused. The X
        # label names the PERSON, not a generic "source", since a reader picking a column should be
        # told it is the employee that each box will name.
        x_label, y_label, multi = "Employee (node)", "", False
    elif chart_type == "boxplot":
        # Long/tidy: the X column's values REPEAT (one row per observation) and one
        # numeric column carries the raw measurements the builder aggregates into a box
        # per category. Single-select Y like pie/treemap/sankey — a second column would
        # be a second distribution, which is a second chart.
        x_label, y_label, multi = "Category (X) axis", "Observations (Y)", False
    elif chart_type == "waterfall":
        # Signed DELTAS, not levels: each bar floats where the last one ended. Single-select
        # Y like pie/treemap/sankey/boxplot — a second column would be a second running
        # total, which is a second chart. The label says "delta" because picking a column of
        # levels here (revenue per month, say) is the one way to get a plausible-looking but
        # meaningless bridge, and nothing downstream can detect it.
        x_label, y_label, multi = "Step labels", "Step values (signed delta)", False
    elif chart_type == "sunburst":
        # An ADJACENCY LIST: each row is one node, named by X, placed under the node named in
        # the Parent selectbox below, and — if it is a LEAF — sized by one numeric column. A
        # node with children needs no value of its own: its arc is the sum of theirs, which is
        # why the label says "leaf". Single-select Y like pie/treemap/sankey/boxplot/waterfall.
        x_label, y_label, multi = "Node labels", "Leaf values", False
    elif chart_type == "xrange":
        # Long/tidy like boxplot — the X column's values REPEAT — but for a different reason:
        # boxplot's repeats are observations to AGGREGATE into one box, while each of these is
        # its own bar, so one lane can hold several. The Y control carries the bar's START,
        # which is why it is labelled as a coordinate rather than a value: it says WHEN, not
        # HOW MUCH. Single-select, like every other extra-column type — a second start column
        # would be a second bar per row, which is a second chart.
        x_label, y_label, multi = "Lane / task labels", "Start", False
    elif chart_type in MAGNITUDE_RANGE_TYPES:
        # A category X axis (the bars stand on it / the band runs along it — column/bar's shape),
        # plus TWO magnitude columns: the Y control carries the LOW (bottom) and the dedicated High
        # selectbox below carries the top. Shared by columnrange and its filled-band mirror
        # arearange, keyed on the family constant (not a re-listed literal) so the two can't drift —
        # the FUNNEL_TYPES / WEIGHTED_NODE_LINK_TYPES rule. Single-select Y like every other
        # extra-column type — a second low column would be a second range per row, which is a
        # second chart. Labelled "Low (bottom)" rather than a bare "Y" because a reader picking a
        # value should be told which END of the range it becomes (xrange's Start/End reasoning,
        # magnitudes).
        x_label, y_label, multi = "Category (X) axis", "Low (bottom)", False
    elif chart_type in GAUGE_TYPES:
        # The two types with NO X control at all (see the selectbox below): their marks are the
        # SELECTED COLUMNS, each collapsed to one number, so there is no label column to pick.
        # Multi-select Y — and here the plural is the whole chart, not a convenience: each
        # column is one mark, which is why neither needs a MARK_METRICS entry (marks == series).
        # Only the noun differs, and it is worth differing: a reader picking columns should be
        # told what each one will BECOME.
        mark = "Rings" if chart_type == "solidgauge" else "Needles"
        x_label, y_label, multi = "", f"{mark} (Y) — one or more", True
    elif chart_type in ("scatter", "bubble"):
        x_label, y_label, multi = "X axis", "Y axis (one or more)", True
    elif chart_type == "heatmap":
        # Wide-form matrix: x_col's values are the X (column) categories, and each
        # selected numeric column becomes a Y row whose cells are the values.
        x_label, y_label, multi = (
            "Category (X) axis",
            "Value columns (Y) — one or more",
            True,
        )
    else:  # cartesian + radar (both a category X axis with one or more Y series)
        x_label, y_label, multi = "Category (X) axis", "Series (Y) — one or more", True

    # Gauge draws no X control, and passes None. It is the one type with no label channel — its
    # marks are the selected COLUMNS — so there is nothing for an X column to name. The two
    # alternatives are both lies: rendering a control that does nothing lies in the UI, and
    # passing a column the builder must ignore lies in the call site AND in three cache keys
    # (the chart would re-render on a change that cannot affect it). `build_options` takes
    # `str | None` precisely so this can be honest.
    x_col = None if chart_type in GAUGE_TYPES else st.selectbox(x_label, df.columns)

    # The node-link types' second node column, sitting next to Source so the two ends of a link
    # read as a pair. Drawn from every column, not numeric_cols like bubble's
    # Size (Z): a node name is a label. Shown for ALL FOUR node-link types — sankey, its circular
    # twin dependencywheel, networkgraph, and organization — which reuse one Target control and one
    # `target_col` (None otherwise, and
    # ignored by the other builders). Organization relabels it "Manager (to)": it reads this column
    # as each employee's manager (the far end of the reporting link), so the domain word beats the
    # generic "Target". The index is a CONSTANT for the same reason
    # the Y default below is: these widgets are keyless, so Streamlit folds it into
    # their identity — the tempting "the column after Source" default would re-mint
    # this widget and silently reset the user's Target every time they changed
    # Source. min() clamps a single-column frame. Source == Target is caught by the
    # guard in the main panel instead.
    target_col = None
    if chart_type in NODE_LINK_TYPES:
        target_col = st.selectbox(
            "Manager (to)" if chart_type in ORGANIZATION_TYPES else "Target (to)",
            df.columns,
            index=min(1, len(df.columns) - 1),
        )

    # Sunburst's second label column, sitting next to Node for the same reason sankey's Target
    # sits next to Source: the two name the ends of one relation. Drawn from every column, not
    # numeric_cols — a parent is a LABEL. The index is a CONSTANT, exactly as sankey's is:
    # these widgets are keyless, so Streamlit folds `index` into their identity, and the
    # tempting "the column after Node" default would re-mint this widget and silently reset the
    # user's Parent every time they changed Node. Node == Parent is caught by the guard in the
    # main panel, and the tree's own contradictions by the one below it.
    parent_col = None
    if chart_type == "sunburst":
        parent_col = st.selectbox(
            "Parent (blank = top level)",
            df.columns,
            index=min(1, len(df.columns) - 1),
            help=(
                "Each row's parent **node label** — a value from the Node column. A blank "
                "cell means the node is a top-level branch. A node that has children needs "
                "no value: its arc is the sum of theirs."
            ),
        )

    # Organization's third label column: a per-node job title, drawn inside each box under the
    # name. Sits after Manager (Target) for the same reason sankey's Target sits after Source — the
    # columns of one relation read together. Drawn from every column (a title is a LABEL, like
    # Manager/Parent, not a number), and the index is a CONSTANT, exactly as those are: keyless, so
    # a default derived from Employee/Manager would re-mint the widget and reset the user's Title on
    # every change. It defaults to the column after the two node ones (index 2), where a job title
    # sits in a person-per-row CSV, so the sample shows its title cards without a click. (A
    # name-only hierarchy — `title_col=None` — is reachable from the pure builder API and pinned by
    # a test; the app always names a title column, as it always names a Target/Parent/End/High.)
    title_col = None
    if chart_type in ORGANIZATION_TYPES:
        title_col = st.selectbox("Title", df.columns, index=min(2, len(df.columns) - 1))

    if chart_type in UNWEIGHTED_NODE_LINK_TYPES:
        # The two UNWEIGHTED node-link types (networkgraph and organization) draw NO Y control and
        # pass an empty list. They have no VALUE channel — a networkgraph's marks are the edges and
        # an organization's are reporting lines, sized by nothing — so a Y picker would drive
        # nothing, and rendering a control that does nothing lies in the UI exactly as an X control
        # would for the gauge family. `build_options` accepts an empty `y_cols` for both precisely
        # so this can be honest (the mirror of gauge's `None` x_col). The empty-Y guard in the main
        # panel exempts them for the same reason.
        y_cols = []
    elif multi:
        # Pills keep every series choice inline and compact, but past
        # MAX_PILL_OPTIONS a wide uploaded CSV would wrap them into several rows in
        # the narrow sidebar, so fall back to st.multiselect (a dropdown, and
        # inherently multi — hence no selection_mode and the two separate calls).
        # The empty-set guard in the main panel handles a cleared selection.
        # A constant default (not one derived from x_col): these widgets are
        # keyless, so Streamlit folds `default` into their identity — a default
        # that varied with X would re-mint the widget and silently reset the
        # user's Y selection whenever they changed X.
        default = numeric_cols[:1]
        if len(numeric_cols) <= MAX_PILL_OPTIONS:
            y_cols = st.pills(
                y_label, numeric_cols, selection_mode="multi", default=default
            )
        else:
            y_cols = st.multiselect(y_label, numeric_cols, default=default)
    else:
        # Xrange is the one type whose Y control is NOT sourced from numeric_cols. Its Y is a
        # bar's START — a coordinate, which may be a date, and a date column is object dtype,
        # so `select_dtypes("number")` cannot see it. Widened to coord_cols rather than to
        # df.columns, which matters: coord_cols is the builder's OWN answer to "can this place
        # a bar on an axis" (see `coordinate_columns`), so the picker cannot offer a column of
        # task names that the builder would only turn around and reject. That is what keeps
        # `_plottable`'s documented invariant — the app never hands the builder a column it
        # can't coerce — true after the widening.
        y_cols = [
            st.selectbox(
                y_label, coord_cols if chart_type == "xrange" else numeric_cols
            )
        ]
    # Normalize the widgets' loosely-typed return (pills/multiselect/selectbox) to a
    # concrete list[str] — the column names already are strings, so this only pins the
    # type, letting the uncached `count_marks` type-check without threading everything
    # through a cache wrapper. An empty selection stays empty for the main-panel guard.
    y_cols = [str(col) for col in y_cols]

    # Xrange's second coordinate column, sitting right after Start so the two ends of a bar
    # read as the pair they are (Lane -> Start -> End, the order a plan is written in). Drawn
    # from coord_cols, like Start and for Start's reason: an end is a coordinate, not a label
    # (sankey's Target and sunburst's Parent are drawn from every column because THOSE are
    # labels). The index is a CONSTANT, exactly as theirs are: these widgets are keyless, so
    # Streamlit folds `index` into their identity, and the tempting "the column after Start"
    # default would re-mint this widget and silently reset the user's End every time they
    # changed Start. min() clamps a single-column frame. Start == End is caught by the guard
    # in the main panel, and the columns' own contradictions by the one below it.
    end_col = None
    if chart_type == "xrange":
        end_col = st.selectbox(
            "End",
            coord_cols,
            index=min(1, len(coord_cols) - 1),
            help=(
                "Each bar's end — the **same kind** of value as Start (both dates, or both "
                "numbers). A bar that ends where it starts is a **milestone** and still "
                "draws; one that ends before it starts is dropped."
            ),
        )

    # The magnitude-range family's second MAGNITUDE column, sitting right after Low so the two ends
    # of a bar/band read as the pair they are (Category -> Low -> High). Shared by columnrange and
    # its filled-band mirror arearange, keyed on the family constant. Drawn from numeric_cols, NOT
    # coord_cols like xrange's End: a high is a value, not a coordinate, so it can never be a date
    # and must be a plottable number — the "a coordinate is not a magnitude" distinction that kept
    # this off xrange's `end_col` kwarg. The index is a CONSTANT, exactly as End's / Size's are:
    # these widgets are keyless, so Streamlit folds `index` into their identity, and a default
    # derived from the current Low would re-mint this widget and silently reset the user's High
    # every time they changed Low. min() lands on the SECOND numeric column so it starts distinct
    # from Low (which leads with the first) and clamps a single-column frame. Low == High is caught
    # by the guard in the main panel.
    high_col = None
    if chart_type in MAGNITUDE_RANGE_TYPES:
        high_col = st.selectbox(
            "High (top)",
            numeric_cols,
            index=min(1, len(numeric_cols) - 1),
            help=(
                "Each bar/band's top — a numeric column, the **same kind** as Low but a distinct "
                "column. A row missing either end draws nothing but keeps its category slot (an "
                "arearange band breaks there); a range whose high is below its low still draws, "
                "spanning both values."
            ),
        )

    # Bubble encodes a third dimension as marker size; pick the numeric column
    # that drives it. Only shown for bubble (None otherwise, and ignored by the
    # other builders). Default to the last numeric column, so it usually differs
    # from the X and Y pickers (which lead with the earlier columns).
    size_col = None
    if chart_type == "bubble":
        size_col = st.selectbox("Size (Z)", numeric_cols, index=len(numeric_cols) - 1)

    # Gauge's two controls, and the first here that name a POLICY and a SCALE rather than a
    # column. They sit BELOW the Y control because the dial is derived from the SELECTED columns
    # under the SELECTED reduction. Inert for every other type.
    agg, dial = GAUGE_AGGREGATIONS[0], None
    if chart_type in GAUGE_TYPES:
        agg = st.selectbox(
            "Reduce each column by",
            GAUGE_AGGREGATIONS,  # from the builder: it can never offer one the builder rejects
            index=0,  # a CONSTANT index, like every other keyless picker in this sidebar
            help="Each mark shows its column collapsed to **one** number.",
        )
        # The default dial comes FROM THE BUILDER — the very `gauge_dial` call `build_options`
        # makes when `dial is None` — so the number the app SHOWS can never drift from the dial
        # the chart DRAWS. The app must not recompute it: a max derived here from the raw column
        # would be smaller than every ring under `sum` (a total exceeds each of its parts), so
        # every ring would sit pinned at 100% and nothing on the page would say why. Total above
        # the empty-Y guard below, like count_marks.
        low, high = gauge_dial(df, y_cols, str(agg))
        # DELIBERATELY KEYLESS, and this is the one widget on this page where the re-mint is the
        # INTENDED behaviour rather than the bug the constant `index`es above exist to prevent.
        # The rule those comments were always applying, stated: fold the default into the
        # widget's identity iff the selection DEPENDS on the state the default derives from.
        # Sankey's Target derives from another WIDGET and stays perfectly valid when Source
        # changes, so re-minting it would discard a real answer. A dial derives from the DATA
        # under a REDUCTION, and an override of it is meaningless the moment either changes: a
        # max of 500 typed against `sum` (436) leaves every ring at ~1% under `mean` (54), and
        # one carried over from another dataset saturates them all. A `key=` is how you would
        # CAUSE that — with a key, `value=` is honoured only on the FIRST render, so the stale
        # number becomes permanent and silent. The re-mint is also visible (the box shows the
        # new derived number) and is scoped to the derivation, not to every rerun: a typed dial
        # survives a title edit, a height drag and a render-mode switch.
        dial_min, dial_max = st.columns(2)
        dial = (
            float(dial_min.number_input("Dial min", value=float(low))),
            float(dial_max.number_input("Dial max", value=float(high))),
        )

    # A stable key keeps a typed title across reruns; an empty field falls back
    # to a per-chart-type default (shown as the placeholder, applied in
    # build_options) instead of silently resetting when the chart type changes.
    title = st.text_input(
        "Chart title",
        key="chart_title",
        placeholder=f"{chart_type.title()} chart",
    )
    height = st.slider("Height (px)", min_value=300, max_value=800, value=480, step=20)

    st.header(":material/tune: 3 · Render")
    render_mode = (
        st.segmented_control(
            "Mode",
            RENDER_MODES,
            default=MODE_INTERACTIVE,
            help=(
                "- **Interactive** — Highcharts loads from the CDN in a sandboxed "
                "iframe.\n"
                "- **Static PNG** — rendered server-side via the Highcharts export "
                "server; the browser loads no Highcharts JS."
            ),
        )
        or MODE_INTERACTIVE
    )


# --------------------------------------------------------------------------- #
# Main panel
# --------------------------------------------------------------------------- #
# At-a-glance numeric summary of the active data, above the two cards.
# st.container(horizontal=True) is the reference's KPI-row pattern (wraps on small
# screens; preferred over st.columns for metric rows). "Series plotted" reads 0
# before the empty-selection guard fires below — a useful empty state, not a blank.
# The chart type is categorical, so it's a badge by the chart, not a metric here.
with st.container(horizontal=True):
    st.metric("Rows", f"{len(df):,}", border=True)
    st.metric("Numeric columns", len(numeric_cols), border=True)
    # The count comes from the builder's count_marks, which applies the very _label_ok /
    # _plottable drop rules build_options does, so the KPI can't drift from what the chart
    # draws (a missing/non-finite label drops its row in every type; a non-plottable value
    # drops a tile/flow too; a waterfall's appended Total is a bar, and a sunburst's appended
    # root is a sector, so their counts exceed their DRAWABLE mark count by one — not
    # necessarily their row count, since an undrawable label drops its row). count_marks reads
    # only the columns each type needs, so it works here above the empty-y guard, as these
    # metrics always have. See MARK_METRICS.
    #
    # This row runs ABOVE the guards below it, which is why count_marks must be TOTAL: on a
    # contradictory sunburst (a cyclic CSV, or Node == Parent) it returns 0 rather than raising,
    # so the page shows "Sectors 0" over the chart it is about to replace with a warning — the
    # true count, and the same empty state "Series plotted" gives before the empty-Y guard
    # fires. It needs no special case here; one branch, however many count-adaptive types there
    # are (the MARK_METRICS property), and sankey's own collision is already treated this way.
    if chart_type in MARK_METRICS:
        marks = count_marks(
            df,
            chart_type,
            x_col,
            y_cols,
            target_col=target_col,
            parent_col=parent_col,
            end_col=end_col,
        )
        st.metric(MARK_METRICS[chart_type], f"{marks:,}", border=True)
    else:
        st.metric("Series plotted", len(y_cols), border=True)

left, right = st.columns([3, 2], gap="large")

with right.container(border=True, height="stretch"):
    st.subheader("Source data")
    # Localized number formatting, hidden index, and the chart's X column pinned
    # so it stays visible while scrolling wide CSVs.
    column_config = {
        col: st.column_config.NumberColumn(format="localized") for col in numeric_cols
    }
    # A gauge has no X column to pin — its marks are the selected columns themselves — so
    # nothing is pinned and the table simply scrolls.
    if x_col is not None:
        column_config[x_col] = (
            st.column_config.NumberColumn(format="localized", pinned=True)
            if x_col in numeric_cols
            else st.column_config.Column(pinned=True)
        )
    st.dataframe(
        df, height=min(height, 360), hide_index=True, column_config=column_config
    )
    # Row count lives in the KPI row; the total-column count is what that row
    # (Rows + numeric-column count) doesn't already surface.
    st.caption(f"{len(df.columns)} columns total")

with left.container(border=True, height="stretch"):
    st.subheader("Highcharts output")

    if not y_cols and chart_type not in UNWEIGHTED_NODE_LINK_TYPES:
        # The two unweighted node-link types (networkgraph, organization) are exempt: they have no
        # value channel, so an empty Y selection is their normal state, not an error (the mirror of
        # the gauge family, which is exempt from the X guard). The KPI row above already shows their
        # "Links"/"Reports" count over this same empty selection.
        st.warning(
            "Pick at least one numeric column to plot.", icon=":material/warning:"
        )
        st.stop()
    if chart_type in X_IN_Y_GUARD_TYPES and x_col in y_cols:
        st.warning(
            "The X-axis column can't also be a Y series — pick a different X.",
            icon=":material/warning:",
        )
        st.stop()
    # The node-link types' own collision: an edge's two ends. Shared by sankey and networkgraph,
    # since it is a fact about the two node columns, not the weight. Not the x-in-y rule above —
    # the Target column isn't among the Y series at all (see X_IN_Y_GUARD_TYPES).
    if chart_type in NODE_LINK_TYPES and x_col == target_col:
        st.warning(
            "Source and Target must be different columns — every link would loop "
            "back to its own node.",
            icon=":material/warning:",
        )
        st.stop()
    # Sunburst's own collision, sankey's one relation over: a node and its parent. Like
    # sankey's, it isn't the x-in-y rule — the Parent column isn't among the Y series at all.
    if chart_type == "sunburst" and x_col == parent_col:
        st.warning(
            "Node and Parent must be different columns — every node would be its own "
            "parent.",
            icon=":material/warning:",
        )
        st.stop()
    # And the tree's own contradictions: a cycle, or a parent label naming more than one node.
    # Neither is missing data (that is dropped, silently and correctly) and neither has any
    # right drawing, so build_options RAISES on them — and this is the one builder error a user
    # can reach just by uploading a CSV. The interactive path doesn't catch, so it has to be
    # stopped here. The message comes from the builder (explain_tree_error), so this warning
    # cannot drift from the exception it stands in for.
    # (`x_col is not None` is true by construction here — the gauge family are the only types
    # that pass None, and neither is sunburst — but it is the narrowing the signature now needs.)
    if chart_type == "sunburst" and parent_col is not None and x_col is not None:
        problem = explain_tree_error(df, x_col, parent_col, y_cols[0])
        if problem:
            st.warning(problem, icon=":material/warning:")
            st.stop()
    # Xrange's own collision, the third of these: a bar's two ends. Like sankey's and
    # sunburst's it is not the x-in-y rule — the End column isn't among the Y series at all
    # (see X_IN_Y_GUARD_TYPES). It has to be caught rather than tolerated because it fails
    # SILENTLY: every bar would be zero-length, so the chart would come back as a column of
    # milestone slivers rather than as anything anyone asked for.
    if chart_type == "xrange" and y_cols[0] == end_col:
        st.warning(
            "Start and End must be different columns — every bar would have zero length.",
            icon=":material/warning:",
        )
        st.stop()
    # The magnitude-range family's own collision, xrange's one type over: a bar/band's low and high.
    # Like the others it is not the x-in-y rule — the High column is the `high_col` selector, not
    # among the Y series — and it fails the same SILENT way xrange's does: every columnrange bar
    # would span zero height (a row of hairlines) and an arearange band would collapse to a line.
    # Unlike xrange there is no column contradiction to report below it: an inverted low/high is
    # KEPT (drawn spanning both values), not an error, so the builder never raises for the family
    # and no explain_* call is needed. Keyed on the family constant so columnrange and arearange
    # share the one guard.
    if chart_type in MAGNITUDE_RANGE_TYPES and y_cols[0] == high_col:
        st.warning(
            "Low and High must be different columns — the bar/band would have zero height.",
            icon=":material/warning:",
        )
        st.stop()
    # And the columns' own contradiction, the one reachable from HERE: a date start beside a
    # numeric end. Both ends of a bar sit on one axis, so they must be the same kind. It is not
    # missing data — that is dropped, silently and correctly, a row at a time — and it has no
    # right drawing, so build_options RAISES; the interactive path doesn't catch, so it has to
    # be stopped here. The sunburst rule, and the second builder error a user can reach without
    # writing any code.
    #
    # explain_xrange_error also reports a SECOND contradiction — a column that is neither dates
    # nor numbers — which cannot be reached through these pickers at all, because both are
    # sourced from `coordinate_columns` and so never offer one. That is not a reason to skip the
    # call: the builder owns the diagnosis, and asking it the whole question here (rather than
    # re-deriving which half is reachable) is what keeps this warning from drifting from the
    # exception it stands in for.
    if chart_type == "xrange" and end_col is not None and x_col is not None:
        problem = explain_xrange_error(df, x_col, y_cols[0], end_col)
        if problem:
            st.warning(problem, icon=":material/warning:")
            st.stop()
    # And the gauge family's own contradiction, the third builder error reachable from this page
    # and the first that is not about a COLUMN at all: a dial with no span. The two number inputs
    # accept any two numbers, so a max at or below the min is one keystroke away — and it makes
    # every mark an undefined fraction of nothing, which has no right drawing. Same contract as
    # the two above: the message comes from the builder (explain_gauge_error), so it cannot drift
    # from the exception it stands in for.
    if chart_type in GAUGE_TYPES:
        problem = explain_gauge_error(dial)
        if problem:
            st.warning(problem, icon=":material/warning:")
            st.stop()

    badge_label, badge_icon, badge_color = MODE_BADGES[render_mode]
    with st.container(horizontal=True):
        st.badge(
            f"{chart_type.title()} chart", icon=":material/bar_chart:", color="grey"
        )
        st.badge(badge_label, icon=badge_icon, color=badge_color)

    # The chart renders in an iframe / server PNG that the shell theme can't
    # reach, so read the active light/dark mode and let the builder flip the
    # chart's chrome to match. `dark` is part of every renderer's cache key, so
    # each mode caches independently. Initial load matches the chart to the shell;
    # a *manual* mid-session theme switch is applied frontend-side without a Python
    # rerun, so the chart catches up on the next interaction. The defensive getattr
    # keeps this working under AppTest, where st.context has no theme.
    _theme = getattr(st.context, "theme", None)
    dark = getattr(_theme, "type", "light") == "dark"

    if render_mode == MODE_STATIC:
        # Server-side render: no Highcharts JS runs in the browser.
        try:
            png = cached_chart_png(
                df,
                chart_type,
                x_col,
                tuple(y_cols),
                height,
                title,
                dark,
                size_col,
                target_col,
                parent_col,
                end_col,
                high_col,
                title_col,
                agg,
                dial,
            )
        except Exception as exc:  # build error or export-server failure
            # The three causes need three different answers, and the builder owns the
            # export-server relationship, so it owns the explanation too (a pure,
            # importable function, as the hooks convention asks).
            st.error(
                f"Static (PNG) render failed.\n\n`{type(exc).__name__}: {exc}`\n\n"
                f"{explain_export_failure(exc)}",
                icon=":material/cloud_off:",
            )
            st.stop()
        st.image(png, width="stretch")
        st.download_button(
            "Download PNG",
            png,
            file_name=f"{chart_type}-chart.png",
            mime="image/png",
            icon=":material/download:",
        )
        st.caption(
            "Static PNG rendered server-side via the Highcharts export server — "
            "the browser loads no Highcharts JS."
        )
    else:
        html = cached_chart_html(
            df,
            chart_type,
            x_col,
            tuple(y_cols),
            height,
            title,
            dark,
            size_col,
            target_col,
            parent_col,
            end_col,
            high_col,
            title_col,
            agg,
            dial,
        )
        # The HTML is embedded in a sandboxed iframe with a FIXED height — it
        # does not auto-grow to its content, so size it to the chart.
        st.iframe(html, height=height + 24)
        st.caption(
            "Interactive chart — Highcharts JS is loaded from the CDN in the browser."
        )

    # Gate the generated-config panel behind a toggle so cached_chart_js only
    # builds (and re-hashes df) when the user actually asks for it. A plain
    # st.expander re-runs its body on every rerun even while collapsed (Streamlit
    # only hides it client-side): it would re-hash df for the cache lookup and
    # re-render st.code each rerun, rebuilding the JS whenever the cache key (chart
    # type / columns / title / theme — note height is not a key) changes. An
    # expander with on_change="rerun" + `.open` would also skip that, but AppTest
    # can't open it — so the toggle (the performance reference's alternative) keeps
    # the config both cheap and observable to the headless tests.
    if st.toggle(":material/code: Show the generated Highcharts config (JavaScript)"):
        chart_js = cached_chart_js(
            df,
            chart_type,
            x_col,
            tuple(y_cols),
            title,
            dark,
            size_col,
            target_col,
            parent_col,
            end_col,
            high_col,
            title_col,
            agg,
            dial,
        )
        st.code(chart_js, language="javascript")
