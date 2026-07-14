"""Build Highcharts (highcharts-core) charts from pandas DataFrames.

Produces either self-contained HTML for embedding in Streamlit with
``st.iframe``, or PNG bytes rendered via the Highcharts export server.

This module is deliberately Streamlit-free so it can be imported and unit
tested on its own. ``streamlit_app.py`` wraps it with the UI and caching.

The flow mirrors the highcharts-core pattern (an options ``dict`` ->
``Chart.from_options`` -> serialize), then uses the chart's own
``get_script_tags`` / ``to_js_literal`` to produce embeddable HTML.
"""

from __future__ import annotations

import html
import itertools
import math
import warnings
from typing import Any

import pandas as pd
from highcharts_core.chart import Chart
from highcharts_core.constants import EnforcedNull

# Chart types this example supports, grouped by the data shape they need.
CARTESIAN_TYPES = ("line", "spline", "area", "areaspline", "column", "bar")
SINGLE_VALUE_TYPES = ("pie",)
XY_TYPES = ("scatter",)
BUBBLE_TYPES = ("bubble",)  # scatter (x, y) plus a size (z) dimension
POLAR_TYPES = ("radar",)  # a polar (spider/web) line chart over the categories
HEATMAP_TYPES = ("heatmap",)  # an x-category × y-category matrix colored by value
TREEMAP_TYPES = ("treemap",)  # nested rectangles sized by value, like pie
SANKEY_TYPES = ("sankey",)  # node-link flows: source -> target links sized by weight
BOXPLOT_TYPES = ("boxplot",)  # per-category distributions, aggregated from raw rows
WATERFALL_TYPES = ("waterfall",)  # signed deltas floating at a running total
SUNBURST_TYPES = ("sunburst",)  # a hierarchy as concentric rings, re-rootable by click
XRANGE_TYPES = ("xrange",)  # a Gantt timeline: bars spanning [start, end] on lanes
# The GAUGE FAMILY: the two types with NO LABEL CHANNEL, whose marks are the SELECTED COLUMNS
# themselves, each reduced to one number by `agg` and read against one dial. They differ only in
# what a mark BECOMES — an arc swept from zero, or a needle pointed at a scale — and share
# everything above that: the reduction, the readings, the dial, the palette-cycled identity hue.
#
# `GAUGE_TYPES` is the name the rest of the module already asks for, and it is asked at exactly
# the five places where the two are IDENTICAL: the `x_col is None` exemption and the `agg`/`dial`
# guard in `build_options`, `count_marks`' no-rule raise, and (in the tests) the label-drop
# sweep's exclusion and the row-less sweep's null expectation. Splitting the tuple in two while
# keeping their sum under the old name is therefore the whole of the family plumbing: every one of
# those five sites stays correct for the needle with no edit at all. The two halves exist only for
# the two BRANCHES, which share no options key worth sharing.
SOLID_GAUGE_TYPES = (
    "solidgauge",
)  # concentric arcs on one shared dial: an activity gauge
NEEDLE_GAUGE_TYPES = ("gauge",)  # needles pointing at a drawn scale: a speedometer
GAUGE_TYPES = SOLID_GAUGE_TYPES + NEEDLE_GAUGE_TYPES
SUPPORTED_TYPES = (
    CARTESIAN_TYPES
    + SINGLE_VALUE_TYPES
    + XY_TYPES
    + BUBBLE_TYPES
    + POLAR_TYPES
    + HEATMAP_TYPES
    + TREEMAP_TYPES
    + SANKEY_TYPES
    + BOXPLOT_TYPES
    + WATERFALL_TYPES
    + SUNBURST_TYPES
    + XRANGE_TYPES
    + GAUGE_TYPES
)

# Types whose x_col is a *category* axis, so it can't double as a y series: the
# cartesian family plus radar (which shares their category-x data shape). Kept to
# exactly cartesian + radar because it also parametrizes the shared category-x
# series tests (EnforcedNull gaps, numeric-x-to-string), which heatmap's grid
# shape doesn't share.
CATEGORY_X_TYPES = CARTESIAN_TYPES + POLAR_TYPES

# The full set the x-in-y guard rejects (x_col can't also be a y series): the
# category-axis types plus heatmap, boxplot and waterfall, whose x_col is likewise a
# category axis (heatmap's values label the columns; boxplot's name the boxes;
# waterfall's name the steps) but which stay out of CATEGORY_X_TYPES above so the
# shared series tests skip them — none uses the cartesian per-point series build
# unaltered. Grouping boxplot's observation column by itself would give every box
# exactly one observation, equal to its own label; waterfall builds the cartesian
# per-point series and then APPENDS the total point, so its data array is one longer
# than the shared tests assert.
# Named once so the builder guard and its streamlit_app mirror share one constant
# and can't drift apart. Sankey is deliberately absent: its x_col is a node label,
# not an axis, and its collision is source-vs-target — target_col isn't in y_cols
# at all, so this rule can't express it (see the dedicated guard in build_options).
# Sunburst is absent for the same reason, one relation over: its x_col names a node,
# and its collision is node-vs-parent, so parent_col isn't in y_cols either. x_col in
# y_cols then merely names every node by its own (numeric) value — odd, well-defined,
# drawable: scatter's x-in-y tolerance, not heatmap's grid misalignment.
# Xrange is absent for a THIRD reason, and the strongest of the three: its x_col is not
# an x axis at all. It names a LANE, and the lanes are the categories of the Y axis (the
# bars run along x, between a start and an end). Its collision is start-vs-end — two
# columns of which only one, y_cols[0], is even a y column — so like sankey's and
# sunburst's it gets a dedicated guard in build_options. x_col in y_cols then merely
# names each lane by its own start coordinate: scatter's x-in-y tolerance again.
# Gauge is absent for a FOURTH reason, and it retires the question rather than answering
# it: the rule reads "x_col cannot ALSO be a y series", and a gauge HAS no x_col. It is the
# one type with no label channel at all (its x_col is None), so there is no collision to
# express — not a tolerated one, as scatter's is, but an unstatable one.
X_IN_Y_GUARD_TYPES = CATEGORY_X_TYPES + HEATMAP_TYPES + BOXPLOT_TYPES + WATERFALL_TYPES

# Default series palette, applied to every chart so both render modes (iframe
# and static PNG) share one look that matches the Streamlit theme in
# .streamlit/config.toml. It leads with the config's LIGHT-mode primaryColor and
# is shared across light and dark (only the chart chrome flips — see _themed), so
# a series keeps its color when the viewer toggles the theme. The iframe and PNG
# paths have no theme CSS, so they rely on this palette.
DEFAULT_COLORS = (
    "#2563eb",  # blue (matches config.toml primaryColor)
    "#16a34a",  # green
    "#f59e0b",  # amber
    "#dc2626",  # red
    "#7c3aed",  # violet
    "#0891b2",  # cyan
    "#db2777",  # pink
    "#65a30d",  # lime
)

# Chart "chrome" (backgrounds, text, axes, gridlines, tooltip) for dark mode. The series
# palette (DEFAULT_COLORS) is shared across modes — only this chrome flips — so a
# series keeps its color when the viewer toggles the theme. Keep "bg"/"text" in
# sync with backgroundColor/textColor in .streamlit/config.toml [theme.dark]; the
# light path is left as Highcharts' defaults, which already match the light shell.
_DARK_CHROME = {
    "bg": "#0f172a",  # == config.toml [theme.dark] backgroundColor
    "text": "#e2e8f0",  # titles, legend, pie labels (== dark textColor)
    "muted": "#94a3b8",  # axis labels + titles
    "grid": "#334155",  # y-axis gridlines
    "axis": "#475569",  # axis + tick lines
}

# Sequential colorAxis gradient for heatmap cell values — the one chart type that
# colors by value, not by the categorical DEFAULT_COLORS series palette. The light
# ramp is anchored on the brand primary (DEFAULT_COLORS[0]); the dark ramp keeps
# the low end near the dark background and brightens the high end so cells stay
# legible against _DARK_CHROME["bg"]. Missing cells use _HEATMAP_NULL, flipped to
# _DARK_CHROME["grid"] in dark mode by _themed.
_HEATMAP_GRADIENT = {"minColor": "#e0ecff", "maxColor": DEFAULT_COLORS[0]}
_HEATMAP_GRADIENT_DARK = {"minColor": "#1e293b", "maxColor": "#60a5fa"}
_HEATMAP_NULL = "#f1f5f9"
# Above this many cells, per-cell value labels overprint into noise, so they're
# only drawn on smaller grids.
_HEATMAP_DATALABEL_MAX_CELLS = 50

# A sankey labels each link with its weight, printing the value IN the mark as pie,
# heatmap, and treemap do — so the Static-PNG mode, which has no hover tooltip,
# still shows the numbers. The label must ride on each link POINT: highcharts-core
# drops `plotOptions.sankey.dataLabels.nodeFormat` (as it drops `tooltip.nodeFormat`),
# and the `format` that does survive there applies to nodes and links alike — so
# setting it series-wide would label every link with the node format, and blank the
# node names. Above this many links the weights overprint into noise, so they're
# only drawn on smaller diagrams (the _HEATMAP_DATALABEL_MAX_CELLS rule).
_SANKEY_DATALABEL_MAX_LINKS = 30
_SANKEY_LINK_LABEL = {"enabled": True, "format": "{point.weight}"}

# Tukey's constant: a boxplot's whiskers reach the most extreme observation still within
# 1.5 x IQR of the box, and anything past that is drawn as an individual outlier. Named
# rather than inlined because both fences read it, and because the number IS the
# convention — changing it changes which points count as outliers at all.
_BOXPLOT_WHISKER_MULTIPLIER = 1.5
# Those outliers ride over the boxes as a second, linked scatter series. They take a
# FIXED brand hue — the red — read straight from DEFAULT_COLORS rather than indexed out
# of the *overridable* `colors` list, so a caller's short custom palette can't IndexError.
# Red reads against the boxes' white interior and the dark chart background alike, so
# (like the shared series palette) it needs no dark-mode flip.
_BOXPLOT_OUTLIER_COLOR = DEFAULT_COLORS[3]

# A waterfall colors its bars by MEANING, not by identity: green for a rise, red for a
# fall, and the brand primary for the closing total. So these are read straight from
# DEFAULT_COLORS by index and NOT from the overridable `colors` list — the
# _BOXPLOT_OUTLIER_COLOR rule, for both of its reasons. A caller's short custom palette
# can't IndexError; and, more to the point, red-means-loss is the chart's semantics
# rather than a series' arbitrary identity, so a custom palette must not be able to
# repaint a fall green. (`colors` is still carried, as heatmap carries it, for
# cross-type consistency — the palette tests sweep every type.)
_WATERFALL_UP_COLOR = DEFAULT_COLORS[1]  # green: the step added to the running total
_WATERFALL_DOWN_COLOR = DEFAULT_COLORS[3]  # red: the step subtracted from it
_WATERFALL_SUM_COLOR = DEFAULT_COLORS[0]  # blue: the total itself, a level not a delta
# The label of the appended closing bar. Must contain no "inf"/"nan" substring: the
# non-finite sweep (test_no_supported_type_emits_a_non_finite_js_literal) asserts those
# tokens appear NOWHERE in the emitted JS, so a category name carrying one would fail it
# spuriously.
_WATERFALL_TOTAL_LABEL = "Total"
# Above this many steps the in-bar value labels overprint into noise, so they're only
# drawn on smaller bridges (the _HEATMAP_DATALABEL_MAX_CELLS / _SANKEY_DATALABEL_MAX_LINKS
# rule). Counts the appended total, since it is drawn and labelled like any other bar.
_WATERFALL_DATALABEL_MAX_STEPS = 30

# Sunburst is the only type that reads the frame as an ADJACENCY LIST — each row is one node
# naming its PARENT by label — so it is the only one whose marks are not in the data: the
# hierarchy has to be ASSEMBLED before anything can be drawn (see _sunburst_tree).
#
# Highcharts links parent to child by `id`, and these ids are SYNTHESIZED rather than taken
# from the labels. A label is not a key. Two rows may legitimately share one ("Other" under
# both Sales and Marketing), and label-as-id would then hand Highcharts two points with the
# same id — which is not a silent mismatch but Highcharts error #31, "Non-unique point or
# node id", printed in a red band across the chart (verified by rendering). Synthesizing ids
# from the row position makes that unreachable: CSV text lands only in `name`, so nothing in
# a hostile file can collide with anything. The cost of the label-keyed shape is paid exactly
# once, and only where it is genuinely unpayable — a label that is USED as a parent must name
# one node (see _SUNBURST_AMBIGUOUS).
_SUNBURST_NODE_ID_PREFIX = "n"  # -> n0, n1, ... ; cannot collide with the root id below

# The synthesized root: the centre sector every branch hangs off. APPENDED by the builder, as
# waterfall appends its Total bar — so this is the second type whose mark count exceeds its
# row count, and the second whose chart draws a mark the frame never held. Its id is internal
# (never read from the CSV), so a node literally named "__root__" is just a node; a node named
# "All" is a cosmetic name clash on screen, exactly as a waterfall step named "Total" is.
# Neither string may contain an "inf"/"nan" substring: the non-finite sweep asserts those
# tokens appear NOWHERE in the emitted JS (the _WATERFALL_TOTAL_LABEL rule).
_SUNBURST_ROOT_ID = "__root__"
_SUNBURST_ROOT_LABEL = "All"
# The root's hue comes OFF the categorical scale entirely — the _WATERFALL_SUM_COLOR argument,
# and here it is sharper still. Ring 1 CYCLES the palette (a ninth branch reuses the first
# hue), so there is no palette entry that is guaranteed not to be some branch's color: the
# only way to say "this sector is not a category, it is the WHOLE" is a hue from outside the
# palette. Read straight from this constant and never indexed out of the overridable `colors`
# — the _BOXPLOT_OUTLIER_COLOR rule, for both of its reasons: a short custom palette can't
# IndexError, and a custom palette must not be able to repaint the total as one more branch.
# Left unset, Highcharts paints the root one of its OWN defaults — a cyan in no palette of
# ours (verified by rendering). This slate reads against the white shell and _DARK_CHROME
# alike, so like the series palette it needs no dark-mode flip.
_SUNBURST_ROOT_COLOR = "#94a3b8"  # slate: the app's "not a category" grey
# The root would otherwise take an equal share of the radius as every data ring — on a
# two-ring tree, half of it: a giant grey disc. Shrink it to a hub. A scalar rather than the
# {"unit", "value"} dict Highcharts wants: a mutable module constant would need a defensive
# copy at its one use site (the _HEATMAP_GRADIENT rule), and there is nothing to copy here.
_SUNBURST_ROOT_SIZE_PCT = 15
_SUNBURST_ROOT_LEVEL = 1  # the synthesized root
_SUNBURST_BRANCH_LEVEL = 2  # ring 1: the top-level branches, seeded from `colors`
# Sectors below ring 1 carry no color of their own — they INHERIT their branch's hue, which is
# what makes a branch read as one thing (verified by rendering) — so within a branch they are
# told apart by a brightness variation instead. The SIGN alternates per ring because the
# variation is applied to the parent's ALREADY VARIED color: a fixed -0.5 at every level walks
# a deep tree down to black.
_SUNBURST_COLOR_VARIATION = 0.5
# Above this many sectors the names overprint into noise, so they're only drawn on smaller
# trees (the _HEATMAP_DATALABEL_MAX_CELLS / _SANKEY_DATALABEL_MAX_LINKS /
# _WATERFALL_DATALABEL_MAX_STEPS rule). Counts the appended root, which is labelled like any
# other sector.
_SUNBURST_DATALABEL_MAX_SECTORS = 60

# The two ways an adjacency list can be a CONTRADICTION rather than merely incomplete. Named
# here so build_options' raise and streamlit_app's warning are literally the same string (the
# X_IN_Y_GUARD_TYPES "named once so they can't drift" rule).
_SUNBURST_CYCLE = (
    "The {parent_col!r} column must describe a tree, but {chain} is a cycle: a node "
    "cannot be its own ancestor."
)
_SUNBURST_AMBIGUOUS = (
    "The parent label {label!r} names {count} different rows in {x_col!r}, so it points "
    "at no single node: a label used as a parent must name exactly one."
)
# A 10,000-node cycle must not print a 10,000-node message.
_SUNBURST_CYCLE_PREVIEW = 6

# Xrange is the first type whose value columns are COORDINATES rather than magnitudes: a
# bar's start and end place it ALONG an axis instead of measuring how far it reaches from
# zero. So a coordinate may be a DATE, and the module gains a third column role beside the
# LABEL (_label_ok, "this names a mark") and the VALUE (_plottable, "this sizes a mark"):
# the COORDINATE (_coordinates, "this positions a mark"). These are the three kinds one
# such column can turn out to be.
_COORD_NUMBER = "number"
_COORD_DATE = "date"
_COORD_NEITHER = "neither"
# ...and the fourth answer, which is NOT a kind: the column is EMPTY — every cell missing. It
# has to be told apart from the other three rather than folded into one of them, because a
# kind is a claim about an AXIS and an empty column makes no such claim. Fold it into
# `_COORD_NUMBER` (the tempting shortcut — an all-NaN column IS float64, so `is_numeric_dtype`
# says yes) and a blank End column beside a real date Start reads as a number-vs-date
# CONTRADICTION and raises, when every row's end is simply missing and the honest answer is the
# module's own missing-data policy: drop the rows, draw an empty chart. That is not a corner
# case — it is a Gantt template whose end dates nobody has filled in yet, straight out of
# `read_csv`. An empty column is therefore compatible with EITHER kind, and contributes no
# opinion about which axis the bars sit on.
_COORD_EMPTY = "empty"

# The two ways a start/end PAIR can be a CONTRADICTION rather than merely incomplete —
# sunburst's split (missing data has a right answer and is dropped; a contradiction has no
# right drawing and is reported), applied to a column pair instead of a tree. Both are
# COLUMN-level facts, decided once for the whole frame, with no per-row right answer: a
# column of task names cannot place a bar on any axis, and a date start beside a numeric end
# describes no single axis at all. Named here so build_options' raise and streamlit_app's
# warning are literally the same string (the _SUNBURST_CYCLE rule).
_XRANGE_NOT_COORDINATE = (
    "The {col!r} column holds neither dates nor numbers, so it can't place a bar's {end} "
    "on an axis. Pick a numeric column, or dates written as ISO-8601 (2026-01-05)."
)
_XRANGE_AXIS_MISMATCH = (
    "The start column {start_col!r} reads as {start_kind}s but the end column {end_col!r} "
    "reads as {end_kind}s. Both ends of a bar sit on ONE axis, so they must be the same kind."
)

# A zero-duration bar — a milestone: a launch date, a deadline, a same-day task — is a real
# Gantt row, and one of the commonest. Highcharts draws NOTHING for it (verified by
# rendering: x == x2 left an empty lane), so without this it would be a mark the KPI counts
# and the chart never draws — the very drift _sizable drops a negative leaf to avoid. Rather
# than drop the row, which would delete a launch date from the plan without saying so, give
# the bar a floor: `minPointLength` renders it as a thin sliver at its date (verified by
# rendering, and pinned on the emitted JS — this repo has been bitten three times by options
# that validate and are then silently dropped). The mark is then genuinely drawn, so counting
# it is honest, and _spannable keeps its zero exactly as _sizable keeps its own.
_XRANGE_MIN_POINT_LENGTH = 3
# Bars are drawn at a fixed height rather than filling their lane, so a one-lane chart doesn't
# render a single bar as a thick slab spanning the plot.
_XRANGE_POINT_WIDTH = 20

# The GAUGE FAMILY has NO LABEL CHANNEL. Every other type names its marks from a column — a
# slice, an axis category, a node, a box, a lane — but a gauge's marks are the SELECTED COLUMNS
# THEMSELVES, each reduced to one number. So `x_col` names nothing and is None, which is why both
# branches run ABOVE the shared `_label_ok` filter and why `x_col` is `str | None`.
#
# `solidgauge` is drawn as an ACTIVITY GAUGE, and the canonical Highcharts recipe for one — a
# SINGLE series whose N points each carry their own radius — is UNAVAILABLE here: a POINT-level
# `radius`/`innerRadius` is accepted by `Chart.from_options` and then silently dropped from
# the emitted JS, while the SERIES-level ones survive (verified on the round-trip). This is the
# sankey-`nodeFormat` / boxplot-`fillColor` / sunburst-`levels[].colorByPoint` family again, and
# the first of them to dictate the SHAPE of a whole branch rather than one of its options: each
# ring MUST be its own series. Forced, not chosen — and that is exactly what makes
# marks == series == len(y_cols), which is why neither gauge needs a `count_marks` rule or a
# `MARK_METRICS` entry. The app's default "Series plotted" already IS the mark count.
#
# `gauge` — the NEEDLE — spends the name this comment used to reserve, and it is Highcharts' own
# name for it, so radar stays the ONE type whose `chart.type` is not its own name. The two are
# genuinely different series types (the needle has `DialOptions`/`PivotOptions`), not one type
# with two skins, which is why they get two branches rather than a flag.
#
# What the needle does NOT inherit, though every instinct says it should, is the point of the
# comments below: each of solidgauge's hard-won workarounds is a fix for a pathology that is
# SPECIFIC TO SOLID GAUGES, and on the needle the same properties fail DIFFERENTLY. The three
# inversions, all measured on the round-trip and by rendering, never inferred:
#
#   * the MODULE. A solid gauge resolves `highcharts-more` ONLY from its `pane` — which is why
#     that key is load-bearing there, and why dropping it draws an empty SVG in the browser while
#     the export server renders perfectly. A needle resolves it from `chart.type` ALONE (verified
#     against the pane, plotOptions and a bare series type in isolation). So the needle's pane is
#     GEOMETRY, not plumbing, and the scariest trap in the family simply does not exist here.
#   * the HUE. On a solid gauge a series-level `color` serializes perfectly and reaches NOTHING
#     (the arc reads the point, because `colorByPoint: true` is a default highcharts-core cannot
#     express turning off; the legend bullet draws grey and needs a `marker.fillColor`). On a
#     needle `color` reaches ONLY the legend — the needle itself is BLACK unless
#     `dial.backgroundColor` says otherwise (rendered: three coloured legend swatches above three
#     black needles). Same property, opposite failure — and the ring writes its hue to three
#     places, the needle to two, with NOT ONE of them in common.
#   * the LABEL. A solid gauge MUST print its readings in the hub: a 360° ring has nowhere to put
#     an axis, so its value can be read against nothing, and it pays for that with a gate, a
#     measured leading and a per-series offset. A needle points AT an axis. So it prints NOTHING
#     in the mark and needs no gate constant either — xrange's rule, reached from xrange's premise
#     — and the sibling's careful label machinery is not re-tuned here, it is DELETED. (It was
#     built the other way first; the renders killed it. See the branch's `dataLabels`.)
#
# The one trap that IS shared, and the only one: `plot_options/gauge.py`'s `top_width` validator
# lacks `allow_empty=True`, so ANY `dial` dict omitting `topWidth` raises `EmptyValueError`.
# It bites at `Chart.from_options`, one layer BELOW `build_options` — so an options-dict test
# passes while the chart cannot be built at all, and the app's interactive path (which does not
# catch builder errors) shows a bare traceback naming neither `dial` nor `topWidth`. Hence
# `_NEEDLE_DIAL`: every dial dict this module emits is spread from it, so the trap is
# unreachable rather than remembered.
_GAUGE_OUTER_PCT = 100.0  # the outermost ring's outer edge, in % of the pane radius
# The empty centre the stacked value labels sit in. Measured, not chosen: the hub scales with
# the chart, so the labels have least room at the SMALLEST height the app offers (300px), and
# that is where the gate below has to hold. At a 30% hub a fifth line already overprints the
# innermost arc there; at 36% five lines sit clear of it.
_GAUGE_HUB_PCT = 36.0
_GAUGE_RING_GAP_PCT = 3.0  # the space between two rings, when there is room for one
_GAUGE_MAX_GAP_FRACTION = (
    0.25  # ...but never more than a quarter of a band (see _gauge_rings)
)
# A ring has to look like a RING. Left to divide the whole radius between them, ONE column draws
# an arc 61% thick — a fat disc with a pinhole, which reads as a pie with a bite out of it rather
# than as a gauge (verified by rendering). Only n=1 and n=2 are wide enough to hit this; from
# three rings up the band is already thinner than the cap and it is inert.
_GAUGE_MAX_THICKNESS_PCT = 30.0
_GAUGE_LABEL_LINE_PX = 17  # the leading between two stacked hub labels
# Gated on ring count, like heatmap's cells, sankey's links, waterfall's steps and sunburst's
# sectors. Two DIFFERENT failures make this gate necessary, and only the second is about taste.
# Highcharts hides a data label that collides with another — by rendering the <text> and turning
# it INVISIBLE, so the element is still in the DOM and every assertion about it still passes
# while a ring's value is simply absent from the chart. `allowOverlap` below turns that off, at
# which point the labels all render and the real limit is physical: the hub is a fixed fraction
# of a radius, the stack grows with the ring count, and past this many lines they print over the
# arcs. Verified by rendering at 300px, the smallest chart the app can draw.
_GAUGE_DATALABEL_MAX_RINGS = 5
# The unfilled remainder of a ring is literally a heatmap's empty cell — "no value here" — so it
# takes the same color, and flips to the same dark one in `_themed`. No new colors.
_GAUGE_TRACK_COLOR = _HEATMAP_NULL
_GAUGE_EMPTY_DIAL = (
    0.0,
    100.0,
)  # nothing to scale: a drawable dial, never a degenerate 0..0
_GAUGE_NICE_STEPS = (1.0, 2.0, 2.5, 5.0, 10.0)

# How BOTH gauges print a reading, in the mark and in the tooltip. A bare `{point.y}` prints the
# double, and the double is what an AGGREGATION hands you: the mean of nine integer percentages is
# `66.44444444444444`, which ran off the side of the chart in a colour-matched 20-character smear
# (verified by rendering — and passed by every unit test in the suite, because the emitted `format`
# string was right; only the NUMBER it formatted was absurd). It is the one flaw an options-dict
# assertion can never see, since the value is not in the options at all.
#
# This is the FAMILY's format, not the needle's, and fixing the sibling with it is not scope creep
# but the whole point of the family: `solidgauge` had the identical latent bug — its own sample
# just happens to divide evenly (436/8 = 54.5), so under `mean` on any other CSV it would have
# printed the same smear. Two types sharing one reduction must round it one way, or the number a
# reader compares between them is formatted by whichever branch they happened to open.
#
# `.1f` and not a trailing-zero-trimming `g`: Highcharts' format strings run through its own
# `numberFormat`, which implements `f`/`e`/`s` and NOT `g`. So a `sum` of 436 prints as `436.0`.
# That is the honest trade — one redundant zero on the integers, against an unreadable chart on
# every reduction that divides.
_GAUGE_VALUE_FORMAT = "{point.y:,.1f}"

# ---- the NEEDLE gauge -------------------------------------------------------------------
# The arc the dial is drawn on. A solid gauge sweeps a full 360° because an arc's LENGTH is its
# reading and a circle is the most length you can get; a needle's reading is its ANGLE, so the
# scale has to be legible, and a semicircle is where the tick labels stop crowding. This is also
# what makes the needle the type that can DROP solidgauge's subtitle-borne dial: the numbers are
# on the chart.
_NEEDLE_START_ANGLE = -90
_NEEDLE_END_ANGLE = 90
# THE PANE CARRIES NO GEOMETRY AT ALL — no `size`, and no `center` either — and that is a
# conclusion, not an omission. It is the one place in this module where the right answer turned out
# to be to stop steering.
#
# `size` is a SILENT DROP, and reading the library says exactly why: `options/pane.py`'s setter
# runs `validators.string(value)`, checks the result for '%', and then FALLS OFF THE END WITHOUT
# EVER ASSIGNING `self._size` — only the numeric `except` branch writes it. So the `size: "85%"`
# that every Highcharts gauge demo on the internet sets is accepted and discarded, while
# `size: 200` (raw pixels, and useless to a chart whose height the user drags) survives. Note
# `inner_size`, ten lines above it, assigns in BOTH branches: this is one copy-paste slip, not a
# policy.
#
# That leaves `center` as the only lever, and a hand-placed centre CANNOT be made safe, because
# Highcharts reserves no room for the tick labels outside the pane and the pane's radius scales
# with the plot box. Every value trades one chart height for another: at 58% the topmost label
# printed through the subtitle; at 65% it was clean at 300px and 800px and CLIPPED CLEAN OFF THE
# CANVAS at 420 (verified by rendering all three — the failure is not even monotonic in the
# height, which is the tell that this is not a number to be tuned).
#
# Highcharts' own default — centre ["50%", "50%"], size 85% — is correct at every height the app
# offers (300, 420, 800: all rendered, all clean), because it is the one placement that knows how
# much room the labels need. So the pane says only what the CHART is (an arc from here to there)
# and nothing about where to put it. `_LIGHT_COLOR_SCHEME_CSS`'s rule, one level up: what we do not
# set, we do not have to keep right.
# The dial FACE. `shape` must be said out loud: a pane background defaults to a CIRCLE, so an arc
# gauge left to itself draws a full disc behind its semicircle (and `_themed` would then flip a
# whole dark disc in). It is the same chrome as a solid gauge's track — "the scale lives here" —
# so it takes the same color and the same dark-mode hook. No new colors.
_NEEDLE_FACE_INNER_PCT = "62%"
_NEEDLE_FACE_OUTER_PCT = "100%"
# The needles are STAGGERED — longest first, so `y_cols[0]` (the column named first) is the
# headline needle, exactly as it is the outermost ring. This is not decoration, it is the fix for
# a real corruption: two columns with EQUAL readings put two needles at the SAME ANGLE, and the
# later one covers the earlier one COMPLETELY — three series, two visible needles, and the legend
# still naming three (verified by rendering: a 70 and a 70 drew one needle).
# `marks == series` is the invariant this whole family rests on, and that made it a lie ON SCREEN.
# Staggering fixes it because Highcharts draws later series ON TOP and both needles start at the
# same pivot: the shorter one overlays the longer one's inner portion, leaving its TIP exposed in
# its own hue (verified: a green needle with a blue tip). Capped at both ends like `_gauge_rings`,
# and for the same reason — the shortest needle must still reach out of the pivot at 40 columns,
# and the longest must not overshoot the face at 1.
_NEEDLE_LONGEST_PCT = 88.0
_NEEDLE_SHORTEST_PCT = 46.0
# EVERY dial dict this module emits is spread from this one, which is what makes the `topWidth`
# trap unreachable (see the family comment above) rather than a thing to remember at four call
# sites. `rearLength: "0%"` because a needle that pokes out behind its pivot is a clock hand, not
# an instrument — and with N of them the tails cross each other's faces.
_NEEDLE_DIAL: dict[str, object] = {
    "topWidth": 1,  # MANDATORY: omitting it raises EmptyValueError out of highcharts-core
    "baseWidth": 9,
    "baseLength": "5%",
    "rearLength": "0%",
}
# How far past the end of the scale a needle may swing, in degrees — and it is the one thing that
# keeps an OVERRIDDEN dial honest. `gauge_dial` guarantees every reading sits inside the scale it
# DERIVES, so this is unreachable by default; but the app's two Dial inputs accept any two numbers,
# so a user who zooms the scale to 0..50 on a column that sums to 436 is one keystroke away.
#
# Left unset, Highcharts pegs such a needle EXACTLY ON the final tick — pixel-identical to a true
# reading of 50 (verified by rendering: the needle sits on the 50 and there is nothing anywhere to
# say otherwise). That is a confident, plausible, wrong chart, and the Static PNG has no tooltip to
# contradict it. It is also the ONE place the two gauges would disagree: a solid gauge in the same
# state fills its arc and PRINTS "north: 436" in the hub, so its reader is told; a needle prints
# nothing in the mark, so its reader is not. The family must not be honest in one branch and
# mute in the other.
#
# Overshoot is the instrument's own answer, and it needs no words: the needle swings PAST the last
# tick, which is what a real meter does when it slams its end stop. It cannot say HOW far over the
# reading is — a dial that stops at 50 cannot draw a 436 — but it says, unmissably, that it IS
# over, which is the whole of the difference between an under-scaled chart and a lying one. Applies
# symmetrically at the bottom, so a negative reading on a zero-floored dial swings below it.
_NEEDLE_OVERSHOOT_DEGREES = 5
# The hub the needles turn on. ONE color, set once in plotOptions — NOT per series, which is the
# obvious move and a lie: N needles pivot at the SAME POINT, so N hued pivots draw N discs on top
# of each other and the reader sees whichever series happened to be last. It is not a mark and it
# has no identity, so it takes the module's existing off-palette "not a category" slate — the
# color sunburst's root already uses, whose comment certifies it reads on both backgrounds and
# needs no dark flip. Left unset it defaults to BLACK, invisible on the dark shell. No new colors.
_NEEDLE_PIVOT_COLOR = _SUNBURST_ROOT_COLOR
_NEEDLE_PIVOT_RADIUS = 5

# The reductions a gauge may apply. Exported as a public tuple so the app's picker is SOURCED
# from the builder — `coordinate_columns`' can't-drift rule, applied to a POLICY rather than to
# a column: the app can never offer a reduction the builder would reject.
_GAUGE_REDUCERS: dict[str, Any] = {
    "sum": lambda s: float(s.sum()),
    "mean": lambda s: float(s.mean()),
    "median": lambda s: float(s.median()),
    "min": lambda s: float(s.min()),
    "max": lambda s: float(s.max()),
    "last": lambda s: float(
        s.iloc[-1]
    ),  # the last KNOWN reading: `_finite_values` ran first
}
GAUGE_AGGREGATIONS = tuple(_GAUGE_REDUCERS)
_GAUGE_DEFAULT_AGG = "sum"

_GAUGE_BAD_AGG = "Unsupported gauge aggregation {agg!r}; expected one of {allowed}"
_GAUGE_BAD_DIAL = (
    "The dial's maximum ({high}) must be a finite number above its minimum ({low}): a dial "
    "with no span makes every ring an undefined fraction of nothing."
)

# Highcharts >= 13 expresses its own default colors as CSS custom properties wrapped in
# `light-dark(...)` — e.g. `--highcharts-background-color: light-dark(#ffffff, #141414)`.
# So every color we do NOT set explicitly resolves against the *browser's*
# `prefers-color-scheme`, not against the app's theme. Two consequences, one rule:
#
# 1. `_themed` is deliberately a no-op in light mode, leaving those defaults in place —
#    so on a dark-OS browser a LIGHT-mode chart paints itself dark (background #141414,
#    pale text) inside the light app shell.
# 2. `boxplot` is the one type whose MARK fill comes from such a variable
#    (`plotOptions.boxplot.fillColor`, which highcharts-core cannot express at all — see
#    the boxplot branch), so its boxes would be filled differently per browser.
#
# The export server already rasterizes with the LIGHT resolution, so pinning the chart's
# own root to `only light` makes the iframe agree with the PNG in both themes and leaves
# `_themed` as the single source of truth for dark mode. It must target `.highcharts-root`
# (the `<svg>`), NOT `html`: Highcharts declares `color-scheme: light dark` on
# `.highcharts-container` (the div between `html` and the `<svg>`; verified against
# Highcharts 13), and since `color-scheme` inherits, that container value shadows any
# `html`-level rule for the whole SVG subtree. The pin therefore has to sit at or below
# the container — `.highcharts-root` is the `<svg>` directly under it — to win. Note this
# reaches the iframe only: the export server renders
# the extracted SVG server-side, where no CSS of ours applies (and neither `chart.style`
# nor `ExportServer.global_options` is an escape hatch — the former is applied with
# `elem.style[key]`, which ignores custom properties, and the latter is coerced through
# the same model that drops `fillColor`).
_LIGHT_COLOR_SCHEME_CSS = ".highcharts-root{color-scheme:only light}"


def _themed(options: dict, *, dark: bool) -> dict:
    """Inject dark-mode chrome into a Highcharts options ``dict``.

    A no-op for light mode, so the light-mode output is byte-for-byte what it was
    before dark mode existed. In dark mode it sets the chart background and the
    title/legend/tooltip/axis/gridline colors to match the dark app shell, leaving
    the series ``colors`` (``DEFAULT_COLORS``) untouched.
    """
    if not dark:
        return options
    t = _DARK_CHROME
    options["chart"]["backgroundColor"] = t["bg"]
    options["title"] = {**options.get("title", {}), "style": {"color": t["text"]}}
    legend = options.setdefault("legend", {})
    legend["itemStyle"] = {"color": t["text"]}
    legend["itemHoverStyle"] = {"color": t["muted"]}
    # The tooltip is lazily rendered by Highcharts and defaults to a light box, so
    # in dark mode it floats light-on-dark on hover unless themed here (config.toml
    # can't reach it inside the iframe/PNG). Merge so the pie path's pointFormat
    # survives.
    options["tooltip"] = {
        **options.get("tooltip", {}),
        "backgroundColor": t["bg"],
        "borderColor": t["axis"],
        "style": {"color": t["text"]},
    }
    for key in ("xAxis", "yAxis"):
        axis = options.get(key)
        if not isinstance(axis, dict):
            continue
        axis["labels"] = {**axis.get("labels", {}), "style": {"color": t["muted"]}}
        if isinstance(axis.get("title"), dict):
            axis["title"] = {**axis["title"], "style": {"color": t["muted"]}}
        axis["lineColor"] = t["axis"]
        axis["tickColor"] = t["axis"]
        axis["gridLineColor"] = t["grid"]
    if options["chart"].get("type") in ("column", "bar", "xrange"):
        # column/bar draw filled shapes with a 1px border that defaults to
        # var(--highcharts-background-color) -> white, which the color-scheme pin
        # keeps white even in dark mode, ringing every bar. Match it to the dark
        # background so the separators disappear as they do in light mode (where the
        # same var resolves to the white shell) -- the pie/treemap/sankey gap rule.
        # The cartesian branch emits no plotOptions, so create it here. Restricted to
        # column/bar: line/spline/area/areaspline have no such border (verified: they
        # paint no white against the dark background).
        #
        # Xrange joins them, and it belongs HERE rather than with waterfall -- which is
        # the other bar-shaped type, and which needs the opposite treatment. That was
        # MEASURED, not inferred from the shared bar base class: waterfall is the standing
        # proof the inference is unsound, since its border turned out to be a fixed
        # #333333. Pixel-scanning a dark-mode xrange PNG off the export server puts its
        # default border at pure #ffffff -- the background var, exactly column/bar's case.
        # Matching it to the dark background dissolves the ring where a bar meets the
        # background while KEEPING a visible 1px seam between two bars that abut within one
        # lane (they are then separated by background, not by white) -- which is precisely
        # what the white border does on the light shell, so the per-lane hues survive it.
        bar_type = options["chart"]["type"]
        options.setdefault("plotOptions", {}).setdefault(bar_type, {})[
            "borderColor"
        ] = t["bg"]
    if options["chart"].get("type") == "pie":
        pie = options["plotOptions"]["pie"]
        pie["dataLabels"] = {**pie.get("dataLabels", {}), "color": t["text"]}
        pie["borderColor"] = t["bg"]  # slice gaps match the dark background
    if options["chart"].get("type") == "treemap":
        # Tile gaps default to light borders; match them to the dark background so
        # they don't read as white grid-lines (as pie does for its slice gaps). The
        # data-label color stays "contrast" (set in build_options): tiles are
        # palette-colored in both themes, so it needs no dark flip.
        options["plotOptions"]["treemap"]["borderColor"] = t["bg"]
    if options["chart"].get("type") == "heatmap":
        # The colorAxis gradient legend + its tick labels aren't reached by the
        # xAxis/yAxis loop above (nor by the categorical legend theming), so flip
        # them here: a dark-anchored ramp, muted labels, and an empty-cell
        # nullColor that reads against the dark background.
        color_axis = options["colorAxis"]
        # Swap the whole gradient as one unit (mirroring the light side's
        # dict(_HEATMAP_GRADIENT)) so the two can't drift if a key is ever added.
        color_axis.update(_HEATMAP_GRADIENT_DARK)
        color_axis["labels"] = {
            **color_axis.get("labels", {}),
            "style": {"color": t["muted"]},
        }
        # The gradient legend's tick lines default to white and cross the bar as bright
        # dashes at each value (the xAxis/yAxis loop above doesn't reach colorAxis). Two
        # elements draw them — full-width gridlines and the shorter edge ticks — so mute
        # both to the same colors the real axes use in that loop, or the gridlines stay
        # white while only the ticks flip.
        color_axis["gridLineColor"] = t["grid"]
        color_axis["tickColor"] = t["axis"]
        options["plotOptions"]["heatmap"]["nullColor"] = t["grid"]
    if options["chart"].get("type") == "sankey":
        # Only the node/link borders need flipping: they default to light and would
        # read as white outlines against the dark background, as pie's slice gaps do.
        # The labels are deliberately left alone — Highcharts draws both the node
        # names and the link weights in its default `contrast` color, computed
        # against whatever each label sits on, so they stay legible in either theme
        # (the treemap reasoning, not pie's).
        options["plotOptions"]["sankey"]["borderColor"] = t["bg"]
    if options["chart"].get("type") == "waterfall":
        waterfall = options["plotOptions"]["waterfall"]
        # Two flips, and NEITHER is the column/bar case above — waterfall's bar border and
        # its connector lines both default to a FIXED #333333 (measured off the rendered
        # PNG on both backgrounds), not to the var(--highcharts-background-color) that
        # resolves to white for column/bar. So the bars are never ringed white and the flips
        # below are not that bug; they are two smaller, real ones:
        #
        # The 1px border reads as a crisp definition line on the white shell, but against
        # the dark background #333333 is only a shade off it, so every bar picks up a muddy
        # grey ring. Nothing separates adjacent bars in a waterfall (they never touch), so
        # the border buys nothing there — match it to the background and let it go, the way
        # pie, treemap and sankey dissolve their own gaps.
        waterfall["borderColor"] = t["bg"]
        # The CONNECTOR lines are the dashes bridging each bar to the next, and they are
        # what makes a waterfall read as a running total rather than a row of floating bars
        # — so they must stay legible. At #333333 on the dark background they survive, but
        # only barely; lift them to the color the real axis lines take. This half has no
        # precedent among the other types: it is the only line Highcharts draws *between*
        # marks.
        waterfall["lineColor"] = t["axis"]
        # The bar hues (up/down/sum) need no flip: like the shared series palette, they
        # read against both backgrounds, and their meaning is fixed (see the constants).
    if options["chart"].get("type") == "sunburst":
        # Sector borders default to var(--highcharts-background-color), which the color-scheme
        # pin holds at WHITE in both themes — so in dark mode every sector is ringed white
        # (verified by rendering). Dissolve them into the dark background, exactly as pie,
        # treemap and sankey dissolve their gaps. Nothing else flips: the sector LABELS ride
        # Highcharts' `contrast`, computed against the fill they sit on rather than the chart
        # background (the treemap rule, not pie's), and the branch hues and the root's slate
        # read on both backgrounds like the shared palette.
        options["plotOptions"]["sunburst"]["borderColor"] = t["bg"]
    if isinstance(options.get("subtitle"), dict):
        # Beside the title line above. Gauge is the first type to carry a subtitle; any future
        # one gets this for free.
        options["subtitle"] = {
            **options["subtitle"],
            "style": {"color": t["muted"]},
        }
    if options["chart"].get("type") in GAUGE_TYPES:
        # The dial FACE — the solid gauge's unfilled ring tracks, the needle gauge's arc behind
        # the ticks. The FIRST `_themed` hook to reach a TOP-LEVEL key rather than
        # `plotOptions[type]`, and less an exception than a demonstration: a dial face is CHROME
        # (the gauge's gridline; the colour of "no value here") that happens to belong to one
        # family, so it lives on the pane, not on the series.
        #
        # It is the whole of BOTH types' dark-mode needs, for two different reasons. For the
        # rings it is the ONLY hook available: `SolidGaugeSeries` models no border at any level
        # and a plotOptions `borderColor` is silently dropped (boxplot's `fillColor`, exactly).
        # For the needles it is the only one NEEDED: their axis — labels, ticks, line — is a real
        # `yAxis` dict, so the generic axis loop above has already themed it, and the needles and
        # their labels carry palette hues that read on both backgrounds. The pivot takes the
        # off-palette slate that needs no flip either (`_NEEDLE_PIVOT_COLOR`).
        #
        # Left unset, a pane background takes a Highcharts default that `_LIGHT_COLOR_SCHEME_CSS`
        # pins to its LIGHT resolution in BOTH themes — so every dial would sit on a glaring white
        # rail against the dark shell (verified by rendering: a white arc, unmissable).
        for face in options["pane"]["background"]:
            face["backgroundColor"] = t["grid"]
    return options


def _plottable(value) -> bool:
    """True when a value can actually be drawn: present, and FINITE.

    An infinity is not missing — ``pd.isna(inf)`` is ``False`` — but it can't be plotted
    either, and it can't even be *serialized*. ``to_js_literal`` renders a Python ``inf``
    as the bare token ``inf``, which is not a JavaScript identifier (JS spells it
    ``Infinity``), so the whole ``Highcharts.chart(...)`` call dies with a ReferenceError
    and the iframe renders blank; the export server, handed the same value as the
    non-standard JSON literal ``Infinity``, rejects the payload with a 400. So a
    non-finite number is treated exactly as a missing one — a gap for the types that keep
    a slot (via ``_num``), a dropped row for the types that drop one (pie, treemap,
    scatter, bubble, sankey's weight). A ``float()`` that raises on a non-numeric cell
    keeps doing so, here rather than one line later — ``ValueError`` for a text value
    (``float("x")``), ``TypeError`` for an object like a ``Timestamp`` (``float()`` has no
    conversion). The app never hits either: ``streamlit_app.py`` draws value columns from
    ``select_dtypes("number")``, so only the pure builder API can pass a non-numeric one.

    Reachable from a plain CSV: ``inf``, ``Infinity``, ``-inf`` and ``1e400`` (which
    silently overflows) all parse to a float infinity that survives ``select_dtypes``.
    """
    return not pd.isna(value) and math.isfinite(float(value))


def _num(value):
    """Coerce one DataFrame value to a JSON-friendly number or Highcharts null.

    Missing *and* non-finite values both become ``EnforcedNull`` — a gap in the line, an
    empty heatmap cell — for the reason ``_plottable`` explains.
    """
    if pd.isna(value):
        return EnforcedNull
    number = float(value)
    return number if math.isfinite(number) else EnforcedNull


def _label_ok(value) -> bool:
    """True when a value can NAME a mark: present, and — if it is a real number — finite.

    The label-column counterpart to ``_plottable``. Every type reads ``x_col`` as the name
    of a mark (a pie slice, an axis category, a sankey node, a boxplot group) except
    scatter/bubble with a numeric x, where x is a coordinate ``_plottable`` already guards.
    A missing (``NaN``/``NaT``) or non-finite label names nothing drawable: it would either
    render as the literal category ``"nan"``/``"inf"`` or, for a non-finite NUMERIC label,
    stringify past the value-column guard entirely. So its row is dropped, the same policy
    the value columns get — uniformly, rather than the split it used to have (kept as
    ``"nan"`` by most types, dropped only by sankey and boxplot).

    Unlike ``_plottable``, a *string* label is valid and must NOT raise: ``math.isfinite``
    rejects a non-number with ``TypeError``, which here means "not a number, so it can't be
    non-finite" — a drawable label. Only a numeric label is range-checked.
    """
    if pd.isna(value):
        return False
    try:
        return math.isfinite(value)
    except TypeError:
        return True


def _sizable(value) -> bool:
    """True when a value can SIZE AN ARC: plottable, and NON-NEGATIVE.

    ``_plottable`` is not enough for a sunburst, and the gap is not fussiness. Highcharts
    draws no sector for a negative node AND excludes it from its parent's children-sum, so a
    negative leaf does not merely fail to appear: it quietly shrinks its parent's arc below
    the total the CSV plainly states, with nothing on screen saying so. (Verified by
    rendering: a ``-400`` leaf beside a ``500`` one drew nothing and left its parent sized
    500, not 100.) That is exactly the failure sankey drops a link for — one that "serializes
    SILENTLY, as an invisible zero-width one" — and it would break the rule ``count_marks``
    exists to hold: the KPI would count a mark the chart never draws. An arc has no negative
    length and a part-of-whole has no negative part, so the row is dropped: pie's and
    treemap's drop-the-row rule, widened by one comparison.

    ZERO is kept. It is a real measurement ("this team has nobody"), it draws a zero-width
    sector, and — unlike a negative — it corrupts no ancestor's sum. Pie and treemap keep
    their zeros for the same reason.
    """
    return _plottable(value) and float(value) >= 0


def _node_key(value) -> str:
    """The string a sunburst node label is matched BY — and displayed AS.

    Sunburst is the only type whose two label columns must COMPARE EQUAL to one another: the
    parent column names a parent BY ITS LABEL, so a bare ``str()`` is a trap rather than a
    formality. pandas widens any column holding a blank cell to ``float64``, and a blank
    parent cell is precisely how a top-level branch is spelled — so the most canonical
    adjacency-list CSV there is::

        node,parent,value
        1,,
        2,1,10

    hands us an ``int64`` node column and a ``float64`` parent column. Under ``str()`` those
    stringify to ``"1"`` and ``"1.0"``, every parent dangles, every row is dropped, and the
    chart comes out SILENTLY EMPTY. So an integral float is rendered as the integer it is,
    and the two columns meet.

    This deliberately diverges from ``_category_labels``, which stringifies with a bare
    ``str()`` — it can afford to, because nothing there has to match anything.
    """
    # np.float64 subclasses Python float, so this catches a pandas cell too.
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _is_top_level(parent) -> bool:
    """True when a sunburst parent cell names NO parent, so its row is a top-level branch.

    Sunburst's parent column is the one place in this module where a MISSING label is not an
    error but a STATEMENT. Everywhere else ``_label_ok`` returning False means "this names
    nothing drawable, so drop the row"; here it means "this node hangs off the root".

    A non-finite parent folds into the same answer by the module's own equation (a non-finite
    value IS a missing one — see ``_plottable``). So does an empty or whitespace-only string,
    which is what a blank cell becomes in a hand-built frame and in a quoted CSV: read as a
    LABEL it would match no node, dangle, and drop the row — the silently wrong answer, where
    "top-level branch" is the visibly right one.
    """
    if not _label_ok(parent):
        return True
    return isinstance(parent, str) and not parent.strip()


def _epoch_millis(series: pd.Series) -> pd.Series:
    """A datetime column as epoch MILLISECONDS — the unit Highcharts' ``x``/``x2`` and its
    ``datetime`` axis read.

    The resolution is NORMALIZED before the int64 view is taken, never divided after it.
    ``.astype("int64")`` reads a datetime column in ITS OWN resolution, and this project's
    pandas (3.x) hands back ``datetime64[us]`` from ``to_datetime`` and from
    ``read_csv(parse_dates=...)`` — not the ``[ns]`` that the obvious ``// 1_000_000`` would
    assume. That divisor is not merely inexact, it is wrong by a factor of a thousand: it
    renders ``2024-01-05`` as ``1970-01-20`` (verified by running it). Every bar keeps its
    correct relative order at catastrophically wrong absolute dates, drawn confidently, with
    no error anywhere — the silent-lie failure mode this module drops rows to avoid. Pinning
    the unit first makes the view already the number we want.

    A tz-aware column is converted to UTC and dropped to naive, matching Highcharts' UTC
    datetime axis; without it the ``astype`` raises on an ordinary ISO CSV column carrying an
    offset. ``NaT`` views as an int64 sentinel rather than ``NaN``, so it is masked back to
    ``NaN`` and folds into the one missing-value policy ``_plottable``/``_spannable`` apply
    everywhere else.
    """
    values = series
    if isinstance(values.dtype, pd.DatetimeTZDtype):
        values = values.dt.tz_convert("UTC").dt.tz_localize(None)
    millis = values.astype("datetime64[ms]").astype("int64").astype("float64")
    return millis.mask(values.isna())


def _coordinates(series: pd.Series) -> tuple[pd.Series, str]:
    """Coerce one start/end column to axis coordinates: ``(floats, kind)``.

    The COORDINATE column role (see ``_COORD_NUMBER``): one float per row — epoch
    milliseconds for a date column, the column's own numbers otherwise — with ``NaN`` for
    anything missing or unparseable. That is what lets the drop predicates downstream
    (``_plottable``, ``_spannable``) meet numbers and never raw text, and it is what makes
    ``count_marks`` TOTAL *by construction* rather than by an app-side promise about which
    columns the pickers offer.

    The ORDER of the tests is the whole design:

    - A NUMERIC dtype is a number, full stop, and is never shown to a date parser.
      ``pd.to_datetime(12)`` does not fail — it returns ``1970-01-01T00:00:00.000000012`` —
      so a "try dates, fall back to numbers" sniff would silently move a column of sprint
      numbers to an instant at the epoch.
    - A ``datetime64`` dtype (naive or tz-aware) is a date, full stop.
    - Only an OBJECT column is a genuine question, and it is answered by counting how many
      cells each coercion recovers — the MAJORITY wins, and the minority's cells become
      ``NaN`` and drop their rows as missing data. A column is one kind or the other; a few
      stray cells of the other kind are typos, not a second axis. A TIE goes to NUMBER (the
      test is a strict ``>``), which is the safe way to break it: a date read as a number
      leaves a visibly missing bar, while a number read as a date would silently place it at
      the epoch — the failure this whole function is ordered to prevent.
      The date parse is PINNED to ISO-8601 because pandas'
      default parser is wildly permissive on free text: ``["Jan","Feb","Mar"]`` parses to
      YEAR 1 AD and ``["00:00","01:00"]`` to TODAY'S DATE (both verified). The first is not
      hypothetical — it is ``sample_data._revenue_vs_cost``'s ``month`` column, the app's
      LANDING dataset, which a permissive sniff would offer as a date axis on the page you
      see when you open the app. ISO-8601 rejects both, and rejects a numeral string
      (``"12"``), so the numeric-string case needs no bespoke regex. It also emits no
      format-inference ``UserWarning`` and does not fall back to per-element ``dateutil``
      parsing.
    - ``utc=True`` because ``errors="coerce"`` is NOT total without it: a column crossing a
      DST boundary (one ``-05:00`` cell, one ``-04:00``) raises "Mixed timezones detected"
      even under ``coerce`` (verified) — and this function is called from ``count_marks``,
      which runs ABOVE the app's guards, where a raise becomes a traceback on the page.
    - Nothing parsed, but something is THERE -> ``_COORD_NEITHER``: a column of task names
      can't place a bar on an axis, and there is no per-row right answer, so it is a
      CONTRADICTION (a returned message), not a drop.

    And the EMPTY test comes FIRST, above the dtype dispatch, which is the one ordering
    constraint that is not about the date parser. A column with nothing in it is missing DATA
    — every row drops, the chart comes out empty — and it must not be allowed to masquerade as
    a KIND, because a kind is a claim about an axis and it makes no such claim. The dtype
    dispatch cannot tell the difference: a blank CSV column arrives as all-``NaN`` ``float64``,
    so ``is_numeric_dtype`` says "number" with total confidence, and that phantom number then
    collides with a real DATE partner and raises ``_XRANGE_AXIS_MISMATCH`` — telling the user
    their empty End column "reads as numbers", which is both false and unactionable. A ROW-LESS
    frame lands here too (nothing present, nothing to draw), which is why it draws an empty
    chart rather than reporting a contradiction.
    """
    if not bool(series.notna().any()):
        # Every cell missing (or no cells at all). Not a kind — see `_COORD_EMPTY`. The
        # coordinates are handed back as all-NaN floats, so every row drops through
        # `_spannable` exactly as a per-row missing value does.
        return pd.Series(
            float("nan"), index=series.index, dtype="float64"
        ), _COORD_EMPTY
    if pd.api.types.is_numeric_dtype(series):
        return series.astype("float64"), _COORD_NUMBER
    if pd.api.types.is_datetime64_any_dtype(series):
        return _epoch_millis(series), _COORD_DATE
    dates = pd.to_datetime(series, format="ISO8601", utc=True, errors="coerce")
    numbers = pd.to_numeric(series, errors="coerce").astype("float64")
    if int(dates.notna().sum()) > int(numbers.notna().sum()):
        return _epoch_millis(dates), _COORD_DATE
    if int(numbers.notna().sum()):
        return numbers, _COORD_NUMBER
    # Something is present and neither coercion recovered any of it.
    return numbers, _COORD_NEITHER


def _spannable(start: float, end: float) -> bool:
    """True when a coerced ``(start, end)`` pair draws a real bar.

    The one predicate in this module that takes TWO values, because an interval's validity is
    a fact about the RELATION and not about either end — ``_sizable`` widened to a PAIR,
    rather than widened by one comparison.

    Both ends must be ``_plottable`` (present, FINITE) before they are compared, and the
    finiteness half is load-bearing rather than ceremonial: ``end >= start`` alone accepts
    ``(-inf, 10)`` and ``(10, inf)``, which would put a bare ``inf`` in the emitted JS — the
    ReferenceError / HTTP-400 the whole non-finite doctrine exists to prevent, and reachable
    from a plain CSV via ``1e400``. A ``NaT`` end folds in for free, having coerced to ``NaN``
    in ``_coordinates`` upstream.

    Then, NON-STRICTLY, ``end >= start``. The two failures the comparison decides are not
    symmetric, and only one of them is a drop:

    - ``end == start`` (a MILESTONE — a launch date, a deadline, a same-day task) is KEPT,
      exactly as ``_sizable`` keeps its zero: it is a real event, one of the commonest rows a
      Gantt has, and dropping it would delete a launch date from the plan without saying so.
      Highcharts draws nothing for it unaided (verified by rendering), so the branch gives it
      a floor with ``_XRANGE_MIN_POINT_LENGTH`` and the mark is genuinely drawn — which is
      what keeps counting it honest.
    - ``end < start`` (INVERTED — an interval that ends before it begins) is DROPPED. Left in,
      Highcharts draws a bar spanning the ENTIRE axis (verified by rendering): not a visible
      error but a confident, plausible lie that reads as the longest task in the project. It
      is the xrange counterpart of sunburst's silent re-parenting, and it drops rather than
      raises for ``_sizable``'s reason — there IS a right drawing (nothing), unlike a cycle,
      where every alternative is a lie.
    """
    return _plottable(start) and _plottable(end) and float(end) >= float(start)


def _finite_values(values: pd.Series) -> pd.Series:
    """One column's observations as ``float64``, reduced to the FINITE ones.

    Shared by the module's two AGGREGATING types — ``_box_stats`` and ``_gauge_value`` — which
    are exactly the two that need it, and need it for one reason. Casting first means a text
    column raises ``ValueError`` here, as ``float(value)`` does in the pointwise branches,
    rather than an opaque dtype error out of ``.quantile()`` or ``.sum()``. Dropping the
    infinities means the arithmetic downstream cannot be poisoned by one (``inf - inf = nan``
    for a whisker; an ``inf`` summand for a ring) and cannot smuggle the bare token ``inf``
    into the emitted JS (see ``_plottable``).
    """
    numeric = values.astype("float64")
    return numeric[numeric.abs() != float("inf")].dropna()


def _gauge_value(values: pd.Series, agg: str) -> object:
    """One column reduced to the ONE number its ring draws — or ``EnforcedNull``.

    The EMPTY test runs FIRST, above the reducer, and that order is the whole design
    (``_coordinates``' ``_COORD_EMPTY`` ordering, for the identical reason).
    ``pd.Series([], dtype="float64").sum()`` is ``0.0``, not NaN — and so is an all-NaN
    column's — so pandas hands back the additive IDENTITY. Under ``sum`` an unfilled column
    would therefore report "the total is zero": a confident CLAIM where the truth is "there is
    no data", drawn as a real ring sitting at the dial's floor to say so. mean/median/min/max/
    last all give NaN; only ``sum`` lies, which makes it worse rather than better, because the
    bug would live in exactly one of the six reductions and look like a rounding quirk in the
    other five. Testing for empty ABOVE the dispatch makes it unrepresentable rather than a
    special case somebody has to remember.

    Then ``_num``, not ``float()``: gauge is the second type (after boxplot) that does
    ARITHMETIC on the values, so it can manufacture a NON-FINITE reading out of finite inputs
    (``1e308 + 1e308`` is ``inf``, and a 1e308 cell parses out of a plain CSV). Boxplot's
    overflow lesson, one type over.
    """
    clean = _finite_values(values)
    if clean.empty:
        return EnforcedNull  # no data — NOT "the total is zero"
    with warnings.catch_warnings():
        # A finite column can still overflow the double range while being summed. The overflow
        # is expected and `_num` handles it; silence the RuntimeWarning rather than let it spam
        # the server log as if it were an unguarded bug (`_box_stats`' reasoning, same fix).
        warnings.simplefilter("ignore", RuntimeWarning)
        return _num(_GAUGE_REDUCERS[agg](clean))


def _check_gauge_agg(agg: str) -> None:
    if agg not in _GAUGE_REDUCERS:
        raise ValueError(_GAUGE_BAD_AGG.format(agg=agg, allowed=GAUGE_AGGREGATIONS))


def _nice_ceiling(value: float) -> float:
    """Round a positive number UP to the next 1/2/2.5/5/10 x 10**k — 436 -> 500, 79 -> 100.

    A dial ending exactly at the largest reading would draw that ring 100% full whatever it
    holds, with no headroom and a maximum nobody would choose. "436 of 500" is the only reading
    a gauge ever gives, so the 500 has to come from somewhere.

    The two fallbacks are not defensive; they are the two ways this arithmetic breaks on real
    input. A candidate can OVERFLOW (``2.0 * 1e308`` is ``inf``, and one 1.5e308 cell parses
    fine out of a plain CSV), which would put the bare token ``inf`` in the emitted JS — the
    ReferenceError-in-the-iframe / HTTP-400 failure this module's whole missing-data doctrine
    exists to prevent. And the magnitude can UNDERFLOW (``10.0 ** -324`` is ``0.0``), leaving
    every candidate at zero and the dial with no extent. In both cases the reading itself is
    finite and positive, so it is its own ceiling.
    """
    if not _plottable(value) or value <= 0:
        return 0.0
    magnitude = 10.0 ** math.floor(math.log10(value))
    for step in _GAUGE_NICE_STEPS:
        candidate = step * magnitude
        if candidate >= value and _plottable(candidate):
            return candidate
    return float(value)


def _nice_floor(value: float) -> float:
    """``_nice_ceiling``'s mirror for a negative reading: -436 -> -500.

    Zero for anything non-negative: a gauge is read FROM zero (see the branch's ``threshold``),
    so a dial that need not go below it does not.
    """
    return 0.0 if value >= 0 else -_nice_ceiling(-value)


def gauge_dial(
    df: pd.DataFrame, y_cols: list[str], agg: str = _GAUGE_DEFAULT_AGG
) -> tuple[float, float]:
    """The dial ``(min, max)`` a gauge draws when the caller names none.

    EXPORTED so ``streamlit_app`` can SEED its Dial min/max inputs from the builder instead of
    recomputing them — ``coordinate_columns``' can't-drift rule, and the first time this module
    hands the app a VALUE to put in a widget rather than a SET of options to populate one.

    Derived from the READINGS, never from the raw columns, and that is the type's central
    invariant rather than a nicety. Under ``sum`` a reading EXCEEDS every observation in its own
    column, so a max derived from the raw column would pin every ring past the end of its own
    dial — "everyone hit target", drawn confidently, on data that says nothing of the sort.
    Reducing first, with the very reduction the rings draw, makes a ring that overflows its own
    derived dial arithmetically unrepresentable.

    TOTAL by construction, like ``count_marks``: it runs ABOVE the app's empty-Y guard, so an
    empty selection, an all-missing column and a row-less frame each give the empty dial rather
    than raising — or, worse, a degenerate ``0..0`` that Highcharts would divide by.
    """
    _check_gauge_agg(agg)
    return _dial_from_readings([_gauge_value(df[col], agg) for col in y_cols])


def _dial_from_readings(readings: list[object]) -> tuple[float, float]:
    """The dial a set of READINGS is read against — the half of ``gauge_dial`` that cannot cheat.

    Split out for one reason, and it is not tidiness: it makes the family's central invariant a
    SIGNATURE rather than a rule two branches have to remember. A function that cannot see a
    DataFrame cannot derive a dial from a raw column, and deriving one from a raw column is the
    exact bug the invariant exists to forbid (under ``sum`` a reading EXCEEDS every observation in
    its own column — 436 against a maximum cell of 63 — so a raw-column dial pins every mark past
    the end of its own scale and draws "everyone smashed target" on data that says nothing of the
    sort). Both gauges call ``gauge_dial``, so both are held to it by construction.
    """
    # `isinstance(..., float)` IS the "a reading, or an absence?" question: `_gauge_value`
    # returns one or the other, and an EnforcedNull is not a number to take a min over.
    known = [value for value in readings if isinstance(value, float)]
    if not known:
        return _GAUGE_EMPTY_DIAL
    # Anchored at zero on BOTH ends — a gauge is read from zero, so the dial contains it even
    # when no reading is near it. (`_nice_floor` returns 0.0 for anything non-negative, so a
    # dial only goes below zero when a reading does.)
    low = _nice_floor(min(0.0, min(known)))
    high = _nice_ceiling(max(0.0, max(known)))
    if high <= low:  # every reading is exactly zero — a dial with no extent
        return _GAUGE_EMPTY_DIAL
    return low, high


def explain_gauge_error(dial: tuple[float, float] | None) -> str | None:
    """``None`` when a dial has extent; otherwise the reason it hasn't.

    The third of the ``explain_tree_error`` / ``explain_xrange_error`` family, and the first
    that reads NO FRAME at all: this contradiction is a fact about two numbers the user typed,
    not about a column or a tree. Same contract, for the same reason — the builder owns the
    dial, so it owns the diagnosis, and the message it RETURNS here is the very one
    ``build_options`` RAISES, so the app's warning and the exception it stands in for cannot
    drift apart. Returned rather than raised because it is reachable from the app (the two
    number inputs accept any two numbers) and the interactive path does not catch builder
    errors.
    """
    if dial is None:
        return None  # not an error: "derive it" (see gauge_dial)
    low, high = dial
    if _plottable(low) and _plottable(high) and float(high) > float(low):
        return None
    return _GAUGE_BAD_DIAL.format(low=low, high=high)


def _gauge_rings(count: int) -> list[tuple[float, float]]:
    """The ``(outer, inner)`` radius of each ring, in percent, OUTERMOST FIRST.

    So ``y_cols[0]`` — the column the user named first — is the headline ring.

    Two caps, each stopping the band from degenerating at one END of the range, and neither is
    tidiness.

    The GAP is capped at a fraction of the band, for MANY rings. A fixed 3% gap exceeds the band
    once there are more than ~21 of them, at which point ``inner > outer`` and Highcharts draws
    garbage — and a wide CSV with 40 numeric columns is one click away. Capping the RING COUNT
    instead would mean dropping a column the user asked for (the renumbering lie the null ring
    exists to prevent), so the geometry DEGRADES — thin rings — rather than breaking: thickness
    stays >= 0.75 x band > 0 for every count >= 1, and the empty-``y_cols`` guard makes 0
    unreachable. What genuinely stops scaling is the centred LABEL STACK, and that is gated on
    count (``_GAUGE_DATALABEL_MAX_RINGS``) like every other in-mark label in this module.

    The THICKNESS is capped for FEW rings, and it is the same failure at the other end: with the
    whole radius to divide between them, one column draws an arc 61% thick — a fat disc with a
    pinhole, which reads as a pie with a bite out of it rather than as a gauge (verified by
    rendering). A ring has to look like a ring. Inert from three rings up, where the band is
    already thinner than the cap.
    """
    band = (_GAUGE_OUTER_PCT - _GAUGE_HUB_PCT) / count
    gap = min(_GAUGE_RING_GAP_PCT, band * _GAUGE_MAX_GAP_FRACTION)
    thickness = min(band - gap, _GAUGE_MAX_THICKNESS_PCT)
    return [
        (
            _GAUGE_OUTER_PCT - index * band,
            _GAUGE_OUTER_PCT - index * band - thickness,
        )
        for index in range(count)
    ]


def _needle_radii(count: int) -> list[float]:
    """Each needle's length, in percent of the pane radius, LONGEST FIRST.

    ``_gauge_rings``' opposite number, and it exists for a reason that only looks cosmetic. Two
    columns whose readings are EQUAL put two needles at the SAME ANGLE, and Highcharts draws the
    later series ON TOP: at one length the second needle covers the first COMPLETELY, so a chart
    with three series draws two needles while the legend goes on naming
    three (verified by rendering — a 70 beside a 70 drew one needle). ``marks == series`` is the
    invariant this whole family rests on, and equal readings are not an edge case (two columns of
    percentages, a duplicated export, a column compared with its own target); that made the
    invariant a lie ON SCREEN, in the one place a reader would never think to check.

    Staggering fixes it *because* of the overdraw rather than in spite of it: both needles start at
    the same pivot, so the shorter one lays over the longer one's inner portion and leaves its TIP
    exposed in its own hue (verified: a green needle with a blue tip, each matching its legend
    swatch). The longest is first, so ``y_cols[0]`` — the column named first — is the headline
    needle, exactly as it is the outermost ring.

    Capped at BOTH ends of the range, like ``_gauge_rings`` and for the same two reasons. With ONE
    needle there is nothing to stagger and it takes the full length. With MANY, a fixed step would
    walk the shortest needle back into the pivot (and then past it, to a negative radius Highcharts
    draws as garbage) — a wide CSV with 40 numeric columns is one click away — so the SPREAD is
    what degrades, never the count: no column the user asked for is ever dropped, the needles just
    bunch up. Two needles at 40 columns may be hard to tell apart, but they are both THERE, and the
    dial they point at is still true.
    """
    if count == 1:
        return [_NEEDLE_LONGEST_PCT]
    step = (_NEEDLE_LONGEST_PCT - _NEEDLE_SHORTEST_PCT) / (count - 1)
    return [_NEEDLE_LONGEST_PCT - index * step for index in range(count)]


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _box_stats(values: pd.Series) -> tuple[object, list[float]]:
    """Reduce one category's raw observations to a Tukey box, plus its outliers.

    Returns ``([low, q1, median, q3, high], outliers)`` — a positional 5-array, which is
    the shape Highcharts matches to ``xAxis.categories`` BY POSITION. A *named* dict
    point is the trap here: highcharts-core collapses ``{"name": n, "low": ...}`` to
    ``[n, low, q1, median, q3, high]``, sliding the label into the leading **x** slot
    where it silently misreads against the categories. A group whose observations are
    all missing returns ``(EnforcedNull, [])``, so the caller keeps its slot on the axis
    — heatmap's keep-the-grid-aligned rule, not pie's drop-the-row one — and it is
    ``EnforcedNull``, never Python ``None``, exactly as ``_num`` returns.

    Observations are first cast to ``float64`` — so a non-numeric column raises
    ``ValueError`` here, as ``float(value)`` does in the other branches, rather than an
    opaque dtype error from ``.quantile()`` — and then reduced to the FINITE ones. NaN is
    the familiar missing value; an infinity is dropped too, because it cannot size a
    whisker and it poisons the whole box: ``inf`` quantiles give ``iqr = inf - inf = nan``,
    which makes both fences ``nan`` and every comparison below false. Dropping it is the
    same rule pie applies to a valueless slice; a group with nothing finite left is simply
    an empty group.

    The whiskers are Tukey's, computed the way ``matplotlib.cbook.boxplot_stats`` (and
    so seaborn) computes them, since that is the boxplot a reader will compare this one
    against:

    - ``q1``/``median``/``q3`` come from pandas' default LINEAR interpolation — the
      type-7 quantiles matplotlib, seaborn and R default to. The method is load-bearing
      rather than incidental: it moves the quartiles, hence the fences, hence which
      points read as outliers at all.
    - The fences sit 1.5 x IQR outside the box. ``low``/``high`` are the most extreme
      ACTUAL observations still inside them — never the fence values themselves — and a
      point is an outlier iff it lies STRICTLY beyond a fence.
    - Membership at the fence is INCLUSIVE (``>=``/``<=``) and the outlier test is its
      strict complement. That is what makes ``iqr == 0`` behave: for a group of one, or
      one whose values are all identical, both fences collapse onto ``q1 == q3``, every
      observation sits exactly ON them, and none is flagged — the box is a legitimate
      flat line rather than a cloud of spurious outliers. (A zero-IQR group that really
      does have tails, with over half its mass on one value, still flags them.)
    - ``low`` is finally clamped to at most ``q1``, and ``high`` to at least ``q3``. On a
      small, sharply skewed group the interpolated ``q1`` can fall BELOW every non-outlier
      observation — ``[0, 100, 101, 102]`` gives ``q1 = 75`` while the lowest in-fence
      point is ``100`` — which would draw a whisker floating inside its own box. The
      clamp is matplotlib's (``if np.min(wisklo) > q1: whislo = q1``) and makes
      ``low <= q1 <= median <= q3 <= high`` hold for every input. It fires on BOTH ends:
      the mirror case, a group skewed the other way (``[0, 1, 2, 102]`` gives ``q3 = 27``
      while the highest in-fence point is ``2``), is what ``high``'s clamp catches.
    """
    clean = _finite_values(values)
    if clean.empty:
        return EnforcedNull, []
    # A huge-but-finite group overflows the double range during aggregation (numpy's
    # quantile interpolation subtracts a + (b - a) * frac); that overflow is expected and
    # handled by the finiteness guard below, so silence its RuntimeWarning rather than let
    # it spam the server log as if it were an unguarded bug. Stdlib `warnings`, not
    # `np.errstate` — the module never imports numpy directly (the `_plottable`/`requests`
    # reasoning: numpy reaches us only through pandas).
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        q1 = float(clean.quantile(0.25))
        median = float(clean.quantile(0.5))
        q3 = float(clean.quantile(0.75))
    iqr = q3 - q1
    lower_fence = q1 - _BOXPLOT_WHISKER_MULTIPLIER * iqr
    upper_fence = q3 + _BOXPLOT_WHISKER_MULTIPLIER * iqr
    # `inside` can never be empty, now that `clean` is finite: the fences bracket
    # lower_fence <= q1 <= median <= q3 <= upper_fence, so the middle half of the data
    # always lands within them. (Leave an infinity in and that stops being true: the
    # fences go nan, every comparison below is false, and .min()/.max() return nan.)
    inside = clean[(clean >= lower_fence) & (clean <= upper_fence)]
    outside = clean[(clean < lower_fence) | (clean > upper_fence)]
    box = [min(float(inside.min()), q1), q1, median, q3, max(float(inside.max()), q3)]
    # Dropping the non-finite INPUTS above is not enough: this is the one type that does
    # arithmetic on the values, and that arithmetic can overflow a finite group. Once the
    # spread nears the double range (~1.8e308), `iqr = q3 - q1` — and even numpy's quantile
    # interpolation, which is `a + (b - a) * frac` — exceeds it and returns +/-inf, so a
    # fence or the median itself goes non-finite while the others stay finite. A non-finite
    # stat can't size a whisker, and it serializes as the bare token `inf` (the very
    # ReferenceError/400 the missing-data policy exists to prevent — see `_plottable`). So
    # treat the whole group as unplottable: the same EnforcedNull box an all-missing group
    # gets, the same policy `_num` applies to a single non-finite value.
    if not all(math.isfinite(value) for value in box):
        return EnforcedNull, []
    return box, [float(value) for value in outside]


def _cycle_chain(loop: list[str], name_of: dict[str, str]) -> str:
    """Render a detected cycle as ``'A' → 'B' → 'A'``, truncated so a 10,000-node cycle
    doesn't print a 10,000-node message. The closing label is always kept, so the loop
    visibly closes even when the middle is elided."""
    labels = [repr(name_of[node]) for node in loop]
    if len(labels) > _SUNBURST_CYCLE_PREVIEW + 1:
        labels = [*labels[:_SUNBURST_CYCLE_PREVIEW], "...", labels[-1]]
    return " → ".join(labels)


def _sunburst_tree(
    df: pd.DataFrame, x_col: str, parent_col: str, value_col: str
) -> tuple[list[dict[str, object]], int, str | None]:
    """Assemble an adjacency list into a sunburst's node points (the root NOT included).

    Returns ``(points, max_level, None)``, or ``([], _SUNBURST_ROOT_LEVEL, message)`` when the
    parent column does not describe a tree at all.

    That split is the whole design. Everything that can be wrong with an adjacency list is one
    of exactly two kinds:

    * MISSING DATA — an undrawable label, an unsizable leaf value, a parent naming no node.
      Each has a right answer (drop the row), so it comes back as a shorter ``points`` list,
      exactly as pie and treemap drop their valueless slices and tiles.
    * A CONTRADICTION — a cycle, or a parent label naming more than one node. Neither has any
      right drawing at all, so it comes back as a MESSAGE: ``build_options`` raises it and
      ``streamlit_app`` shows it (through ``explain_tree_error``), from this one place, so the
      two can't drift.

    Returning that message rather than raising it is what keeps ``count_marks`` TOTAL, and
    that matters: the app's KPI row runs ABOVE its guards, so a ``count_marks`` that raised on
    a cyclic CSV would blow the page up with a traceback before the warning explaining it
    could ever render.

    Shared by ``build_options`` and ``count_marks`` — a stronger form of the can't-drift rule
    than the other types get. They don't merely reuse the same drop predicates; they reuse the
    whole computation, so the KPI is ``len(points) + 1`` by construction rather than by
    agreement.
    """
    ids: list[str] = []
    name_of: dict[str, str] = {}
    # Any, not object: these hold raw DataFrame cells, which is what every other branch's
    # `float(value)` / `_plottable(value)` already takes untyped. `object` would make the
    # float() below a type error rather than the runtime ValueError a text column should get.
    value_of: dict[str, Any] = {}
    raw_parent: dict[str, Any] = {}
    by_key: dict[str, list[str]] = {}

    # A plain zip, NOT a Series mask — so the `.astype(bool)` row-less trap that every other
    # type's `.map()` filter has to be cast against cannot arise here at all: a row-less frame
    # is simply an empty loop. (`_label_ok` is re-checked even though build_options already
    # filtered x_col with it, because count_marks calls this on the RAW frame — the helper has
    # to stand on its own, and is idempotent either way.)
    for label, parent, value in zip(
        df[x_col], df[parent_col], df[value_col], strict=True
    ):
        if not _label_ok(label):
            continue
        # Ids run over the SURVIVING rows rather than df.index: build_options passes an
        # already-filtered frame (whose index has gaps) while count_marks passes the raw one,
        # so a counter is what makes the two produce byte-identical ids.
        key = _node_key(label)
        node = f"{_SUNBURST_NODE_ID_PREFIX}{len(ids)}"
        ids.append(node)
        name_of[node] = key
        value_of[node] = value
        raw_parent[node] = parent
        by_key.setdefault(key, []).append(node)

    # Resolve each row's parent LABEL to a node id.
    parent_of: dict[
        str, str | None
    ] = {}  # id -> parent id, the root, or None (dangling)
    for node in ids:
        parent = raw_parent[node]
        if _is_top_level(parent):
            parent_of[node] = _SUNBURST_ROOT_ID
            continue
        key = _node_key(parent)
        matches = by_key.get(key)
        if matches is None:
            parent_of[node] = None  # dangling — pruned, with its descendants, below
        elif len(matches) > 1:
            # A duplicate label is only a contradiction once something POINTS AT it. Two
            # unreferenced "Other" leaves are two honest sectors (identity is the ROW, as it
            # is for treemap — synthesized ids are what let them coexist). But a row saying
            # `parent = "Other"` names no single node, and the alternatives to refusing it are
            # both silent lies: MERGE the twins (one sector worth a sum nobody asked for) or
            # PICK one (a subtree confidently grafted onto the wrong branch). Sankey's
            # contradiction rule — raise, and say which label.
            return (
                [],
                _SUNBURST_ROOT_LEVEL,
                _SUNBURST_AMBIGUOUS.format(label=key, count=len(matches), x_col=x_col),
            )
        else:
            parent_of[node] = matches[0]  # may be the node ITSELF — a one-node cycle

    # One walk up the parent chain does BOTH jobs: it catches cycles, and where it grounds on
    # the root it hands back each node's level for free. Iterative, not recursive — a
    # 50,000-deep chain is valid input and a 50,000-long cycle is reachable input, and
    # recursion would die on both. O(N): every node is walked once, then settled.
    #
    # It needs exactly TWO bits about a node, and they are easy to conflate: "is it on the path
    # I am walking RIGHT NOW" (a cycle) versus "was it already settled as unreachable" (it
    # dangles, or hangs off something that does). Collapsing them loses the ability to tell a
    # cycle from a walk that merely ran into a known-dead chain. So the second lives in
    # `settled` — where `None` says unreachable, because "settled at depth N" and "settled,
    # unreachable" are the same *kind* of fact about a node and belong in one map — and the
    # first in a set scoped to THIS walk, which is what makes it mean what it says.
    settled: dict[
        str, int | None
    ] = {}  # id -> level, or None: unreachable from the root
    for start in ids:
        path: list[str] = []
        on_path: set[str] = set()  # this walk only, so a stale mark can't fake a cycle
        node: str | None = start
        while node is not None and node != _SUNBURST_ROOT_ID and node not in settled:
            if node in on_path:  # stepped back onto THIS path
                loop = [*path[path.index(node) :], node]
                return (
                    [],
                    _SUNBURST_ROOT_LEVEL,
                    _SUNBURST_CYCLE.format(
                        parent_col=parent_col, chain=_cycle_chain(loop, name_of)
                    ),
                )
            on_path.add(node)
            path.append(node)
            node = parent_of[node]
        if node == _SUNBURST_ROOT_ID:
            base: int | None = _SUNBURST_ROOT_LEVEL
        elif node is None:
            base = None  # this chain's top row names a parent that is not a node
        else:
            # Joined a chain an earlier walk already settled — whose level is itself None if
            # that chain was unreachable, which is precisely what keeps the drop TRANSITIVE.
            base = settled[node]
        # Settle the path just walked, nearest-the-root first. A dangling node's descendants
        # inherit its None, so the transitive drop falls out for free: reachability-from-the-root
        # IS the dangling rule, stated once. It has to be transitive — an unmatched `parent` is
        # not left alone by Highcharts, which silently re-parents it to the root, quietly
        # promoting an orphaned grandchild into ring 1.
        for depth, walked in enumerate(reversed(path), start=1):
            settled[walked] = None if base is None else base + depth
    level = {node: depth for node, depth in settled.items() if depth is not None}

    # Prune valueless LEAVES, deepest first. A node's children all sit at level + 1, so
    # descending level is a topological order for a forest: every child is decided before its
    # parent, with no recursion and no fixed-point loop. One rule — keep(n) = the value can
    # size an arc, OR something under n survived — and its corollary is not a special case but
    # the rule itself: a node whose only child was dropped BECOMES a leaf, and then its own
    # value is what sizes it.
    kept: dict[str, bool] = {}
    has_kept_child: set[str] = (
        set()
    )  # a SET: nothing ever reads *which* children survived
    for node in sorted(level, key=lambda n: level[n], reverse=True):
        # `_sizable` is evaluated for every node, internal ones included, so a text value
        # column raises ValueError uniformly (through float() inside _plottable) rather than
        # raising or not depending on the tree's shape — boxplot's stated contract.
        keep = _sizable(value_of[node]) or node in has_kept_child
        kept[node] = keep
        parent = parent_of[node]
        # `parent is not None` can never actually be False here — a node whose parent dangles is
        # unreachable, so it never landed in `level` and never reaches this loop. It narrows the
        # type for `set[str]`; don't go hunting for the case it guards.
        if keep and parent is not None and parent != _SUNBURST_ROOT_ID:
            has_kept_child.add(parent)

    points: list[dict[str, object]] = []
    for node in ids:  # ROW order, not level order
        if not kept.get(node):
            continue
        point: dict[str, object] = {
            "id": node,
            "parent": parent_of[node],
            "name": name_of[node],
        }
        if node not in has_kept_child:
            # Only a LEAF of the DRAWN tree carries a value. An internal node is emitted with
            # none, and Highcharts sums its children into it. That is not deference, it is the
            # only honest option: an explicit parent value OVERRIDES the sum, so emitting a
            # CSV's subtotal row draws a parent whose arc disagrees with the arcs inside it
            # (verified by rendering — two branches declaring `value = 1` drew as equal halves
            # while holding 900 and 100). And it would go wrong even when the subtotal is
            # RIGHT, the moment one child row is dropped: the parent would keep claiming the
            # full total with a child missing beneath it. Omitting it makes a parent's arc
            # always equal what is actually drawn under it — the discipline count_marks
            # enforces on the KPI, applied to the geometry.
            point["value"] = float(value_of[node])
        points.append(point)
    max_level = max(
        (level[node] for node in ids if kept.get(node)), default=_SUNBURST_ROOT_LEVEL
    )
    return points, max_level, None


def _sunburst_levels(max_level: int) -> list[dict[str, object]]:
    """The per-ring ``levels`` array, for a tree of arbitrary depth.

    Ring 1 (level 2) gets no entry: its sectors are seeded with an explicit per-point color
    instead. Every ring BELOW it needs a ``colorVariation``, or a branch's descendants — which
    inherit its hue — would be indistinguishable from one another. The sign ALTERNATES because
    the variation is applied to the parent's already-varied color, so a fixed ``-0.5`` at
    every ring walks a deep tree down to black.

    ``levelIsConstant`` is left at Highcharts' default (absolute depths). Its own demo sets it
    ``false``, which is wrong here: with relative levels, drilling into a branch would make
    that branch level 1 and its children level 2 — and level 2 has no ``colorVariation`` — so
    every child would render in the parent's exact hue. Absolute levels keep a sector's color
    identical before and after a traversal, which is the point of turning traversal on.
    """
    levels: list[dict[str, object]] = [
        # Without the levelSize the root takes an equal share of the radius as every data ring
        # — on a two-ring tree, half of it: a giant slate disc.
        {
            "level": _SUNBURST_ROOT_LEVEL,
            "levelSize": {"unit": "percentage", "value": _SUNBURST_ROOT_SIZE_PCT},
        }
    ]
    for index, ring in enumerate(range(_SUNBURST_BRANCH_LEVEL + 1, max_level + 1)):
        to = -_SUNBURST_COLOR_VARIATION if index % 2 == 0 else _SUNBURST_COLOR_VARIATION
        levels.append(
            {"level": ring, "colorVariation": {"key": "brightness", "to": to}}
        )
    return levels


def _xrange_bars(
    df: pd.DataFrame, x_col: str, start_col: str, end_col: str
) -> tuple[list[dict[str, object]], list[str], bool, str | None]:
    """Assemble a frame into an xrange's bars: ``(points, lanes, is_datetime, problem)``.

    The WHOLE build, shared by ``build_options`` and ``count_marks`` — ``_sunburst_tree``'s
    contract. Xrange reaches for it for a reason that is subtler than sunburst's, and easy to
    miss: a row's SURVIVAL genuinely does look per-row (its own label, its own start, its own
    end, and none of them depend on another row), so xrange appears to belong with
    treemap/sankey on the shared-predicate mask path. It does not. The AXIS KIND is a
    COLUMN-level fact — decided once, by ``_coordinates``, over the whole column — and every
    row's start and end is then interpreted THROUGH it. And the two callers do not hold the
    same column: ``build_options`` reaches its branch on the ``_label_ok``-FILTERED frame (the
    shared filter reassigns ``df``), while ``count_marks`` and ``explain_xrange_error`` call
    this on the RAW one. A ``count_marks`` that reused only ``_spannable`` would therefore
    sniff a different frame than the chart drew, and could count against a different axis —
    or pass a guard the builder then raises on. Reusing the build instead makes the drift
    unrepresentable: the KPI is ``len(points)`` by construction.

    Two things make the raw and filtered frames produce byte-identical output: ``_label_ok``
    is re-applied HERE (idempotent when the caller has already applied it — the explicit
    ``_sunburst_tree`` contract), and the coercion runs over the SURVIVING rows only, so a
    garbage cell on a row that is dropped for its label can never sway the sniff.

    ``problem`` is a column-level contradiction (a start/end column that is neither dates nor
    numbers; two that disagree about which). It is RETURNED, never raised — that is what keeps
    ``count_marks`` total, and it matters for exactly the reason it matters for sunburst: the
    app's KPI row runs ABOVE its guards, so a raise here would blow the page up with a
    traceback before the warning explaining it could render.
    """
    # `.astype(bool)`, the row-less cast: on a frame with no rows `.map()` has no values to
    # infer a result dtype from and hands back a non-boolean Series, which pandas reads as a
    # list of COLUMN NAMES rather than as a mask. `build_options` has already applied this
    # filter by the time it calls in; `count_marks` has not.
    keep = df[x_col].map(_label_ok).astype(bool)
    labels = df.loc[keep, x_col]
    starts, start_kind = _coordinates(df.loc[keep, start_col])
    ends, end_kind = _coordinates(df.loc[keep, end_col])

    for col, kind, end_name in (
        (start_col, start_kind, "start"),
        (end_col, end_kind, "end"),
    ):
        if kind == _COORD_NEITHER:
            return [], [], False, _XRANGE_NOT_COORDINATE.format(col=col, end=end_name)
    # The two ends must agree about which axis they are on — but only the columns that HAVE an
    # opinion get a vote. An EMPTY column makes no claim (see `_COORD_EMPTY`), so it is
    # compatible with either kind and cannot manufacture a disagreement: a blank End column
    # beside a real date Start is a Gantt whose end dates are unfilled, not a contradiction,
    # and every row drops through `_spannable` as missing data. Comparing the raw kinds instead
    # would raise, and tell the user their empty column "reads as numbers".
    kinds = {kind for kind in (start_kind, end_kind) if kind != _COORD_EMPTY}
    if len(kinds) > 1:
        return (
            [],
            [],
            False,
            _XRANGE_AXIS_MISMATCH.format(
                start_col=start_col,
                end_col=end_col,
                start_kind=start_kind,
                end_kind=end_kind,
            ),
        )

    lanes: list[str] = []
    lane_index: dict[str, int] = {}
    points: list[dict[str, object]] = []
    for label, start, end in zip(labels, starts, ends, strict=True):
        if not _spannable(start, end):
            continue
        # `_node_key`, not a bare `str()`: a lane column holding one blank cell is widened to
        # float64 by pandas, and `str()` would then label lane 1 as "1.0". Nothing has to
        # MATCH here (unlike sunburst, where the same trap dangles every parent and empties
        # the chart silently), so this is cosmetic rather than load-bearing — but it is free,
        # and the two columns that DO have to match are one refactor away.
        key = _node_key(label)
        if key not in lane_index:
            # Lanes are discovered from the SURVIVORS, in first-appearance order (boxplot's
            # `groupby(sort=False)` rule). A lane whose every row dropped never enters
            # `yAxis.categories` at all: boxplot keeps an all-missing group as an
            # `EnforcedNull` box because there the group IS the mark (one group, one box), but
            # an xrange lane holds 0..n bars, so there is no "the mark for this lane" to null
            # out. An empty labelled axis row with nothing pinned to it is exactly the phantom
            # the inverted-bar drop exists to prevent — this is pie/treemap/sankey's
            # drop-the-row family: no ghost slice, no ghost lane.
            lane_index[key] = len(lanes)
            lanes.append(key)
        points.append(
            # `y` is a POSITION into `yAxis.categories`, not a value — boxplot's positional
            # trick. A lane is never a magnitude.
            {"x": float(start), "x2": float(end), "y": lane_index[key], "name": key}
        )
    # Read from the voting columns, not from `start_kind` alone: with an EMPTY start beside a
    # date end, the axis is still a date axis (no bar draws either way, but the axis should not
    # claim otherwise). `kinds` holds at most one entry by the check above.
    return points, lanes, _COORD_DATE in kinds, None


def _category_labels(df: pd.DataFrame, x_col: str) -> list[str]:
    """Coerce an x column to string category *labels* (Highcharts categories are
    labels, not values). Shared by the scatter/bubble non-numeric-x, heatmap, and
    cartesian/radar branches — highcharts-core rejects non-string categories, so a
    numeric x_col must be stringified here rather than passed through."""
    return [str(value) for value in df[x_col].tolist()]


def _xy_x_axis(df: pd.DataFrame, x_col: str, *, numeric_x: bool) -> dict[str, object]:
    """X-axis config shared by the scatter and bubble branches.

    A titled axis; for a non-numeric ``x_col`` the points are placed by row
    position, so the actual values label those positions via ``categories``
    (rather than a bare ``0..N``).
    """
    x_axis: dict[str, object] = {"title": {"text": x_col}}
    if not numeric_x:
        x_axis["categories"] = _category_labels(df, x_col)
    return x_axis


def _tooltip_label(name: str) -> str:
    """Sanitize a (possibly user/CSV-supplied) column name for use as literal
    text in a Highcharts tooltip format string. Strips the ``{``/``}`` that
    Highcharts would otherwise parse as value tokens (so ``weight {kg}`` keeps
    its unit rather than vanishing), and HTML-escapes the rest since tooltips
    render as HTML (so a name can't inject markup)."""
    return html.escape(str(name)).replace("{", "").replace("}", "")


def _in_mark_labels(fmt: str, **extra: object) -> dict[str, object]:
    """Value labels printed IN the mark, so the Static-PNG mode (which has no hover
    tooltip) still shows the numbers. "contrast" text + outline is computed against the
    FILL the label sits on, not the chart background, so -- unlike pie's labels -- it needs
    no dark-mode flip."""
    return {
        "enabled": True,
        "format": fmt,
        "color": "contrast",
        "style": {"textOutline": "1px contrast", "fontWeight": "normal"},
        **extra,
    }


def build_options(
    df: pd.DataFrame,
    chart_type: str,
    # `None` for gauge alone — the one type with no label channel, so the column role that
    # every other type takes for granted stops being universal. Guarded below.
    x_col: str | None,
    y_cols: list[str],
    *,
    title: str | None = None,
    colors: list[str] | None = None,
    dark: bool = False,
    size_col: str | None = None,
    target_col: str | None = None,
    parent_col: str | None = None,
    end_col: str | None = None,
    agg: str = _GAUGE_DEFAULT_AGG,
    dial: tuple[float, float] | None = None,
) -> dict:
    """Return a Highcharts options ``dict`` for the given DataFrame and columns.

    - cartesian types (line/spline/area/areaspline/column/bar): ``x_col`` becomes the
      category axis and each column in ``y_cols`` becomes a series.
    - ``pie``: ``x_col`` labels the slices and the first column in ``y_cols``
      gives their values.
    - ``scatter``: ``x_col`` and each ``y_cols`` column form (x, y) point pairs.
      A non-numeric ``x_col`` is plotted by row position and labelled with the
      column's values via the x-axis categories.
    - ``bubble``: like ``scatter``, but each point carries a third value from
      ``size_col`` that drives the marker area — points are (x, y, size) triples,
      and every ``y_cols`` series shares the one ``size_col``.
    - ``radar``: a polar (spider/web) line chart. Like the cartesian types,
      ``x_col`` becomes the (angular) category axis and each ``y_cols`` column a
      series, but the axes are drawn radially (so ``chart.type`` is ``line`` with
      ``chart.polar`` set — Highcharts has no ``radar`` type).
    - ``heatmap``: an x-category × y-category value matrix. ``x_col``'s values are
      the X (column) categories, each ``y_cols`` column *name* is a Y (row)
      category, and every cell is ``df[row][col]`` — the category-x shape
      reinterpreted as a grid, colored by a sequential ``colorAxis`` rather than
      the categorical series palette. A missing cell stays in place as
      ``EnforcedNull`` (an empty ``nullColor`` cell) rather than being dropped, so
      the grid never misaligns.
    - ``treemap``: nested rectangles sized by value — the same single-value shape
      as ``pie`` (``x_col`` labels each tile, the first ``y_cols`` column gives its
      value), but each tile is colored categorically from the palette
      (``colorByPoint``) and laid out by the ``squarified`` algorithm. Missing
      values are dropped like pie's slices. Pulls in the ``modules/treemap`` module.
    - ``sankey``: a node-link flow diagram. Unlike every other type, the data is
      read as *edges of a graph* rather than as series or categories: each row is
      one link, from the node named in ``x_col`` to the node named in
      ``target_col``, whose width is the first ``y_cols`` column. A node that is
      both a target and a source chains the flow into a second hop. Rows missing
      any of the three are dropped, like pie's slices. Pulls in the
      ``modules/sankey`` module.
    - ``boxplot``: per-category Tukey distributions. The one type that AGGREGATES —
      every other maps rows 1:1 onto marks, but a box summarizes many rows. The data
      is long/tidy (``x_col``'s values REPEAT, one row per observation) and each
      distinct ``x_col`` value becomes one box over that group's raw ``y_cols[0]``
      numbers, as ``[low, q1, median, q3, high]``. Observations beyond the 1.5 x IQR
      fences are drawn individually, as a second linked scatter series that is emitted
      only when some exist. A group whose observations are all missing keeps its axis
      slot as an ``EnforcedNull`` box. Shares bubble's and radar's ``highcharts-more``
      module.
    - ``waterfall``: a cumulative "bridge". The category-x data shape read as signed
      DELTAS rather than levels: ``x_col`` names each step, the first ``y_cols`` column
      gives its signed change, and each bar floats where the last one ended. A closing
      ``Total`` bar is APPENDED (Highcharts' ``isSum``), so the frame holds only the
      deltas — it is what makes the chart a bridge rather than a row of floating bars.
      Bars are colored by MEANING (rise/fall/total), not identity. Shares bubble's,
      radar's and boxplot's ``highcharts-more`` module.
    - ``sunburst``: a hierarchy drawn as concentric rings. The only type that reads the
      frame as an ADJACENCY LIST: each row is one node, named by ``x_col``, placed under
      the node named in ``parent_col`` (a blank parent means a top-level branch), and — if
      it is a LEAF — sized by the first ``y_cols`` column. An internal node carries no
      value: its arc is the SUM of its children's, computed by Highcharts. A closing root
      is APPENDED (as waterfall appends its total), so the centre reads the whole. A row
      whose parent names no node is dropped with its descendants, like pie's valueless
      slices; a cycle or an ambiguous parent label is a contradiction and raises. Pulls in
      the ``modules/sunburst`` module.
    - ``xrange``: a Gantt-style timeline, and the only type whose mark has EXTENT along
      the x axis rather than sitting at a point on it. Each row is one bar, on the LANE
      named by ``x_col`` (lanes are the categories of the *Y* axis, so ``x_col``'s values
      REPEAT — boxplot's long/tidy shape), spanning from the first ``y_cols`` column to
      ``end_col``. Those two are COORDINATES, not magnitudes, so they may be dates: the
      pair is sniffed once (see ``_coordinates``) onto one shared axis — ``datetime`` if
      they read as ISO-8601 dates, linear if they read as numbers. A row missing either
      end is dropped, as is one whose bar runs BACKWARDS; a zero-length one (a milestone)
      is kept and floored to a visible sliver. Pulls in the ``modules/xrange`` module.
    - ``solidgauge`` and ``gauge``: the GAUGE FAMILY, the two types with NO LABEL CHANNEL.
      ``x_col`` is unused (and is ``None``) because a gauge's marks are the SELECTED COLUMNS
      THEMSELVES: each ``y_cols`` column becomes one mark, showing that column REDUCED to a
      single number by ``agg`` (see ``GAUGE_AGGREGATIONS``). So they are the second and third
      AGGREGATING types after boxplot, and the only ones whose marks are not in the frame at
      all. A column with nothing finite in it keeps its mark as an ``EnforcedNull`` (boxplot's
      all-missing-group rule) rather than being dropped, so the mark count is always
      ``len(y_cols)``. ``dial`` sets the scale both read against; left ``None`` it is derived
      from the READINGS by ``gauge_dial``, never from the raw columns.

      They differ only in what a mark BECOMES. ``solidgauge`` sweeps an ARC from zero — an
      "activity gauge" — over a full 360°, which leaves nowhere to put an axis, so it prints
      its dial in the subtitle and every reading in the hub. ``gauge`` points a NEEDLE at a
      scale that is actually DRAWN: a semicircular axis with ticks and labels, which is the
      whole reason the type exists and why its subtitle carries only the ``agg``. Needles are
      staggered in length (see ``_needle_radii``) so two equal readings do not draw as one.
      ``solidgauge`` pulls in ``modules/solid-gauge`` plus ``highcharts-more`` (which only its
      ``pane`` resolves); ``gauge`` pulls in ``highcharts-more`` from ``chart.type`` alone.

    ``colors`` overrides the series palette; it defaults to ``DEFAULT_COLORS``.
    ``dark=True`` themes the chart chrome (background, text, axes, gridlines,
    tooltip) for dark mode; the series palette itself is shared across modes.
    ``size_col`` names the marker-size column and is required for ``bubble``;
    ``target_col`` names the destination-node column and is required for
    ``sankey``; ``parent_col`` names the parent-label column and is required for
    ``sunburst``; ``end_col`` names the column each bar ends at and is required for
    ``xrange``. Each is ignored by the other types. ``agg`` and ``dial`` are read only by the
    GAUGE FAMILY, and are the only two parameters here that name a POLICY and a SCALE rather
    than a column.

    Raises ``ValueError`` for an unsupported ``chart_type``, empty ``y_cols``, a missing
    ``x_col`` for any type outside the GAUGE FAMILY (``solidgauge`` and ``gauge``, the two with
    no label channel to name),
    a ``bubble`` chart with no ``size_col``, a ``sankey`` chart with no
    ``target_col`` or whose ``target_col`` is its ``x_col``, a ``sunburst`` chart
    with no ``parent_col``, whose ``parent_col`` is its ``x_col``, or whose parent
    column does not describe a tree (a cycle, or a parent label naming more than one
    node — see ``explain_tree_error``), an ``xrange`` chart with no ``end_col``, whose
    ``end_col`` is its start column, or whose start/end columns cannot place a bar on
    one axis (either is neither dates nor numbers, or the two disagree about which —
    see ``explain_xrange_error``), a GAUGE-FAMILY chart with an unknown ``agg`` or a ``dial``
    with no span (see ``explain_gauge_error``), or (for the category-axis types — cartesian,
    radar, heatmap, boxplot, and waterfall) an ``x_col`` that is also one of the
    ``y_cols``.
    """
    if chart_type not in SUPPORTED_TYPES:
        raise ValueError(
            f"Unsupported chart_type {chart_type!r}; expected one of {SUPPORTED_TYPES}"
        )
    if not y_cols:
        raise ValueError("At least one y column is required.")
    if chart_type in BUBBLE_TYPES and not size_col:
        raise ValueError("A bubble chart requires a size (z) column via size_col.")
    if chart_type in SANKEY_TYPES and not target_col:
        raise ValueError("A sankey chart requires a target (to) column via target_col.")
    if chart_type in SANKEY_TYPES and x_col == target_col:
        # Source and target name the two ends of every link, so one column can't be
        # both: each row would be a self-loop. (The weight column is free to repeat
        # either — odd, but it still renders, as scatter's x-in-y does.)
        raise ValueError(
            f"x_col {x_col!r} cannot also be the target column for a sankey chart"
        )
    if chart_type in SUNBURST_TYPES and not parent_col:
        raise ValueError("A sunburst chart requires a parent column via parent_col.")
    if chart_type in SUNBURST_TYPES and x_col == parent_col:
        # Every row would name itself as its own parent — a one-node cycle in every node. The
        # tree walk WOULD catch it, but only once there are rows, and with a mystifying
        # "'Jan' → 'Jan' is a cycle" when the real fault is that one column was picked twice.
        # Sankey's source-is-target argument: a column can't be both ends of the relation.
        raise ValueError(
            f"x_col {x_col!r} cannot also be the parent column for a sunburst chart"
        )
    if chart_type in XRANGE_TYPES and not end_col:
        raise ValueError("An xrange chart requires an end column via end_col.")
    if chart_type in XRANGE_TYPES and y_cols[0] == end_col:
        # Start and end name the two ends of every bar, so one column can't be both —
        # sankey's source-is-target and sunburst's node-is-parent rule, a third time. This
        # one has to be a guard rather than a tolerated oddity, because it fails SILENTLY:
        # every bar would have zero length, so every row would become a milestone, and the
        # chart would come back as a column of slivers rather than as anything anyone asked
        # for. (`x_col` IS free to repeat either — the lanes are then named by their own
        # start or end coordinate: odd, well-defined, drawable, scatter's x-in-y tolerance.
        # Which is also why xrange stays out of X_IN_Y_GUARD_TYPES: its x_col names a lane
        # on the Y axis, and end_col isn't in y_cols at all, so that rule cannot express
        # this collision.) `y_cols[0]` is safe: the empty-y_cols guard above runs first.
        raise ValueError(
            f"The start column {y_cols[0]!r} cannot also be the end column for an "
            f"xrange chart"
        )
    if chart_type not in GAUGE_TYPES and x_col is None:
        # Every other type NAMES its marks with x_col — a slice, a category, a node, a box, a
        # lane. Gauge is the first with no label channel at all, so the role stops being
        # universal and the signature has to admit it. A pure-API caller who omits x_col for a
        # pie deserves this message rather than a bare KeyError out of pandas.
        raise ValueError(f"A {chart_type} chart requires an x column via x_col.")
    if chart_type in GAUGE_TYPES:
        _check_gauge_agg(agg)
        problem = explain_gauge_error(dial)
        if problem:
            # The very message `explain_gauge_error` returns, so the app's warning and the
            # exception it stands in for cannot drift apart — sunburst's cycle rule, and
            # xrange's. Reachable from the app: the two number inputs accept any two numbers.
            raise ValueError(problem)
    if chart_type in X_IN_Y_GUARD_TYPES and x_col in y_cols:
        raise ValueError(
            f"x_col {x_col!r} cannot also be a y series for a {chart_type} chart"
        )

    # Every type reads x_col as a mark LABEL — a pie slice name, an axis category, a
    # sankey source node, a boxplot group — EXCEPT scatter/bubble with a numeric x, where
    # x is a coordinate the per-point `_plottable` already guards. For the label case, a
    # missing or non-finite label names nothing drawable, so drop its row once, here, in
    # one place, rather than let each branch stringify it to the literal "nan"/"inf" mark.
    # This applies the value-column missing-data policy to the label column too, uniformly
    # (see `_label_ok`); before, only sankey and boxplot dropped such a row. sankey's OTHER
    # label column, target_col, is handled in its own branch (this filter reaches x_col
    # only). Reassigning df to the filtered frame keeps every branch's position-aligned
    # `zip(..., strict=True)` and category/series builds in lockstep.
    title = title or f"{chart_type.title()} chart"
    colors = list(colors) if colors is not None else list(DEFAULT_COLORS)

    if (
        chart_type in SOLID_GAUGE_TYPES
    ):  # concentric rings: one column, reduced to one number, each
        # Placed ABOVE the shared `_label_ok` filter, and the placement is load-bearing rather
        # than tidy. Gauge has no label channel — `x_col` is None and names nothing — but the
        # exception is not merely vacuous, and that is the sharper point: gauge AGGREGATES, and
        # a row filter above an aggregating branch does not drop a MARK, it silently changes a
        # NUMBER. Filter three rows out of thirteen because their (unused) label cell happened
        # to be blank and the total comes back smaller — drawn confidently, with nothing on the
        # page saying so. Sitting above the filter makes that unreachable rather than unlikely.
        low, high = dial if dial is not None else gauge_dial(df, y_cols, agg)
        rings = _gauge_rings(len(y_cols))
        # A ring's hue is its arbitrary IDENTITY, like a pie slice's, so it reads from the
        # OVERRIDABLE `colors` (waterfall's semantic red-means-loss is the opposite case),
        # cycled so a short custom palette WRAPS rather than IndexErrors
        # (_BOXPLOT_OUTLIER_COLOR's concern). ONE `next()` per ring, then written to THREE
        # different levels below — the point (the arc), the marker (the legend swatch) and the
        # data label — because on this type each of those reads a different property and none of
        # them falls back to another. Taking the hue once makes their agreement a fact rather
        # than a coincidence maintained in three places.
        hues = itertools.cycle(colors or DEFAULT_COLORS)
        labelled = len(y_cols) <= _GAUGE_DATALABEL_MAX_RINGS
        middle = (
            len(y_cols) - 1
        ) / 2  # so the hub's lines are centred about the middle one
        # A gauge is read FROM ZERO: an arc's LENGTH is its magnitude. Left unset, Highcharts
        # sweeps each arc from the axis MINIMUM, which INVERTS an all-negative dial — on a
        # -500..0 dial a -40 would draw a LONGER arc than a -155, so the smallest loss would
        # look like the biggest. Clamped into the dial so that a custom override excluding zero
        # still has a base to sweep from.
        threshold = min(max(0.0, low), high)

        tracks: list[dict[str, object]] = []
        rings_out: list[dict[str, object]] = []
        for index, (col, (outer, inner)) in enumerate(zip(y_cols, rings, strict=True)):
            hue = next(hues)
            # The TRACK: a ring's unfilled remainder, and the only thing that says how far round
            # the ring has NOT gone. It is chart furniture, not a mark, so it lives on the PANE
            # — which is why gauge's dark-mode hook is the first to reach a top-level key.
            tracks.append(
                {
                    "outerRadius": _pct(outer),
                    "innerRadius": _pct(inner),
                    "backgroundColor": _GAUGE_TRACK_COLOR,
                    "borderWidth": 0,
                }
            )
            ring: dict[str, object] = {
                "name": col,
                # RADIUS ON THE SERIES, COLOR ON THE POINT — the exact mirror of each other, and
                # the single nastiest thing about this type. A point-level radius is silently
                # dropped (see the family constants). And the color is the converse: Highcharts'
                # solidgauge defaults `colorByPoint: true`, and highcharts-core models no
                # `color_by_point` at all, so a `colorByPoint: False` at series OR plotOptions
                # level is silently dropped and the default CANNOT be turned off. Each series'
                # single point is index 0 of its own colorCounter, so EVERY ring resolves to
                # `colors[0]`: a series-level `color` serializes perfectly and never reaches an
                # arc. Verified by rendering — three hues in the JS, three identical blue arcs on
                # screen, beside pane tracks showing the three TRUE hues, so a reader matches a
                # green track to a blue arc and reads the wrong ring. Not an error, not a blank
                # chart: a confident, plausible, wrong one. Two adjacent properties, opposite
                # levels, each silently wrong on the other's — and one hue, said twice below and
                # once again on the marker, because all three levels are load-bearing and none
                # of them substitutes for another.
                "radius": _pct(outer),
                "innerRadius": _pct(inner),
                # And the hue has to be said a THIRD time, on a third level, for the legend
                # swatch — which is not pedantry but the same drop wearing a third hat. A
                # series-level `color` serializes perfectly (it is right there in the emitted
                # JS) and Highcharts renders the legend bullet GREY anyway: `#333333`, for
                # every ring, beside arcs and hub labels carrying the true hues. Verified by
                # rendering, and then verified again by taking the series `color` away, which
                # changed NOTHING — it does no work on this type at all, so carrying it would be
                # an option that looks load-bearing and isn't. The legend symbol reads the
                # MARKER, which a solid gauge otherwise never draws (no markers on an arc), so
                # this is inert everywhere except the one place it is needed. It matters because
                # the legend is the only thing that names an EMPTY ring (a null point draws no
                # arc and no label), and a grey bullet cannot be matched back to a band.
                "marker": {"fillColor": hue, "symbol": "circle"},
                "threshold": threshold,
                "showInLegend": True,
                # A live ring is a one-point dict carrying y + color. An EMPTY one is the BARE
                # EnforcedNull, not `{"y": EnforcedNull, "color": hue}` — highcharts-core drops a
                # null `y` OUT of a point dict entirely (verified: it emits `{color: ...}`),
                # leaving a point with no value at all, while the bare form serializes as
                # `[[null]]`, a real null point. There is no arc to color anyway. The ring is
                # KEPT rather than dropped — boxplot's all-missing-group rule — and here that is
                # geometrically forced: the radii are a function of the SELECTION, so a
                # data-driven drop would resize and recolor every other ring, and the KPI
                # ("Series plotted") would count a ring the chart never drew.
                "data": (
                    [EnforcedNull]
                    if (value := _gauge_value(df[col], agg)) is EnforcedNull
                    else [{"y": value, "color": hue}]
                ),
            }
            if labelled:
                # One line per ring, stacked in the hub, outermost first. A per-SERIES pixel
                # offset is the only way to stack them: every ring's label renders at the centre
                # of the pane, so without this they land on top of each other. In the ring's own
                # hue, which needs no dark-mode flip (the palette is theme-shared) and is what
                # binds a line of text to a band on the dial.
                ring["dataLabels"] = {
                    "y": round((index - middle) * _GAUGE_LABEL_LINE_PX),
                    "style": {"color": hue},
                }
            rings_out.append(ring)

        return _themed(
            {
                "chart": {"type": "solidgauge"},
                # Genuinely read, not carried for cross-type consistency: every ring seeds from
                # it (heatmap is the type that carries `colors` without using them).
                "colors": colors,
                "title": {"text": title},
                # The scale is INVISIBLE on the chart — a 360° activity gauge has nowhere to put
                # an axis — so an arc's fraction cannot be decoded from a downloaded PNG, which
                # has no tooltip either. Print it, with the aggregation: "436" means nothing
                # until you know it is a sum of eight weeks rather than one week's reading.
                "subtitle": {"text": f"{agg} · dial {low:g} – {high:g}"},
                # THE PANE IS LOAD-BEARING, not decoration. `get_script_tags` emits
                # highcharts-more ONLY when the options tree carries a `pane` key — verified
                # against each candidate in isolation: not the series type, not
                # plotOptions.solidgauge, not a series radius, not yAxis.stops — and a solid
                # gauge WITHOUT highcharts-more draws an EMPTY SVG in the browser: zero series
                # paths, no Highcharts error band, no Python-side error, a silently blank chart.
                # The export server rasterizes it regardless, so dropping the pane would make the
                # two render modes silently DISAGREE — the class of bug `_LIGHT_COLOR_SCHEME_CSS`
                # exists to close. Pinned by a test on `get_script_tags`.
                "pane": {
                    "startAngle": 0,
                    "endAngle": 360,  # a full circle: the arc's ANGLE is the value's fraction
                    "background": tracks,
                },
                "yAxis": {
                    "min": low,
                    "max": high,
                    # No axis is drawn (see the subtitle). Silenced with WIDTHS, not with the
                    # obvious `tickPositions: []`: an empty list is PRUNED before it is emitted,
                    # and the tick dashes then stay visible ON the tracks even with the labels
                    # switched off (seen in the rendered PNG).
                    "lineWidth": 0,
                    "tickWidth": 0,
                    "minorTickWidth": 0,
                    "gridLineWidth": 0,
                    "labels": {"enabled": False},
                    # Highcharts titles a value axis "Values" unless it is explicitly CLEARED,
                    # and None does not clear it — an empty string does (heatmap's rule).
                    "title": {"text": ""},
                },
                # The one type whose legend is not redundant, and it earns its place twice. A
                # ring whose column is empty draws no arc AND no data label (Highcharts skips a
                # null point's label entirely), so the legend is the only thing that NAMES it;
                # and past the label gate it is the only thing naming any ring at all, since a
                # gauge has no axis and the Static PNG has no tooltip. Its swatch is the series
                # `color` — the one job that property can still do here.
                "legend": {"enabled": True},
                # `{series.name}`, and it is a third answer for a third reason: waterfall needs
                # `{point.category}` (its points are positional), sunburst and xrange need
                # `{point.name}` (their categories are on the wrong axis) — and a gauge ring
                # holds exactly ONE point, so the mark's identity is not on the point at all.
                # It IS the series.
                "tooltip": {
                    "headerFormat": "",
                    "pointFormat": f"{{series.name}}: <b>{_GAUGE_VALUE_FORMAT}</b>",
                },
                "plotOptions": {
                    "solidgauge": {
                        "rounded": True,
                        "linecap": "round",
                        "stickyTracking": False,  # one point per series: hover the ring you mean
                        # NOT `_in_mark_labels`: that helper exists for `color: contrast`,
                        # computed against the FILL a label sits on — and these sit in the empty
                        # hub, on no fill at all. `useHTML` is pinned False because the export
                        # server silently drops HTML labels, and the two render modes would
                        # disagree again. `allowOverlap` is pinned True because Highcharts
                        # otherwise HIDES a colliding label by rendering the <text> and turning
                        # it invisible — the element stays in the DOM, so every assertion about
                        # it still passes while a ring's value is simply absent from the chart.
                        #
                        # And, unlike heatmap's and column's, a gauge's dataLabels default to ON,
                        # so past the gate they must be disabled EXPLICITLY: merely omitting the
                        # key (heatmap's style) would be a gate that did nothing, and twenty
                        # labels would pile up at one offset.
                        "dataLabels": (
                            {
                                "enabled": True,
                                "useHTML": False,
                                "allowOverlap": True,
                                "borderWidth": 0,
                                "align": "center",
                                "verticalAlign": "middle",
                                "format": f"{{series.name}}: {_GAUGE_VALUE_FORMAT}",
                                "style": {
                                    "textOutline": "none",
                                    "fontWeight": "normal",
                                },
                            }
                            if labelled
                            else {"enabled": False}
                        ),
                        # No `colorByPoint` (it cannot even be emitted — see the point `color`),
                        # and no `yAxis.stops`, which is solidgauge's canonical coloring: stops
                        # are a VALUE ramp, so a ring would go red for being LOW. The data never
                        # said low was bad. Heatmap's colorAxis-vs-palette split, and gauge sits
                        # on the palette side of it.
                    }
                },
                "series": rings_out,
            },
            dark=dark,
        )

    if (
        chart_type in NEEDLE_GAUGE_TYPES
    ):  # needles on one drawn scale: one column, reduced to one number, each
        # Above the shared `_label_ok` filter, for the solid gauge's reason exactly: this branch
        # AGGREGATES, and a row filter above an aggregate does not drop a mark, it silently
        # changes a NUMBER.
        #
        # What it does NOT share with its sibling is the SCALE'S HOME. A solid gauge sweeps 360°,
        # which leaves nowhere to put an axis, so it prints the dial in a SUBTITLE and every
        # reading in the hub — the value can be read against nothing, so it has to be written
        # down. A needle's reading IS an angle against a drawn axis. So the axis is the whole
        # point of the type, it is what the needle POINTS AT, and the subtitle keeps only the
        # half of its job that the chart still cannot show: the `agg`. ("62" is a fact; "62, the
        # mean of nine hosts" is the finding, and no amount of axis will say the second.)
        low, high = dial if dial is not None else gauge_dial(df, y_cols, agg)
        lengths = _needle_radii(len(y_cols))
        # A needle's hue is its arbitrary IDENTITY, like a pie slice's and like a ring's, so it
        # cycles the OVERRIDABLE `colors` (waterfall's semantic red-means-loss is the opposite
        # case) and WRAPS rather than IndexErrors on a short custom palette. One `next()` per
        # needle, then written to TWO levels — and they are not two of the solid gauge's three.
        hues = itertools.cycle(colors or DEFAULT_COLORS)

        needles: list[dict[str, object]] = []
        for col, length in zip(y_cols, lengths, strict=True):
            hue = next(hues)
            needle: dict[str, object] = {
                "name": col,
                # LEVEL 1 — the LEGEND SWATCH, and ONLY the legend swatch. On every ordinary
                # Highcharts type `color` paints the mark; on a gauge it paints everything EXCEPT
                # the mark. Verified by rendering `color` alone: three perfectly coloured legend
                # bullets above three BLACK needles. (It is the mirror of the solid gauge, where
                # `color` serializes just as cleanly and reaches nothing at all — there the legend
                # bullet draws grey and needs a `marker.fillColor`. Same property, two different
                # ways of doing nothing you wanted.)
                "color": hue,
                # ...and the legend has to be asked for TWICE, because a gauge series defaults to
                # `showInLegend: false` — unlike almost every other type. Without this the chart
                # renders with no legend at all, and since a needle carries no name on the chart,
                # nothing would say which reading is which (verified: the legend was simply
                # absent until this line existed).
                "showInLegend": True,
                # LEVEL 2 — the NEEDLE. Spread from `_NEEDLE_DIAL` so `topWidth` is present by
                # construction: omit it and highcharts-core raises `EmptyValueError` out of a
                # validator that names neither the key nor the series (see the family comment).
                "dial": {
                    **_NEEDLE_DIAL,
                    "backgroundColor": hue,
                    "radius": _pct(length),
                },
                # A one-point series, and — unlike the ring's — with NO ternary for the empty
                # column. `_gauge_value` hands back a float or an `EnforcedNull`, and BOTH are
                # correct here as they stand: highcharts-core serializes the null to `[[null]]`, a
                # real null point, which draws no needle and no label. The ring needs its ternary
                # only because a LIVE ring must carry `color` on the POINT (its arc reads the
                # point, not the series) while a null point must NOT — a null `y` is dropped out
                # of a point dict entirely, leaving a point with no value. A needle's colour is on
                # its dial, so the point is just the number, and the empty column stops being a
                # special case at all rather than being handled as one.
                "data": [_gauge_value(df[col], agg)],
            }
            needles.append(needle)

        return _themed(
            {
                "chart": {"type": "gauge"},
                # Genuinely read: every needle seeds its hue from it.
                "colors": colors,
                "title": {"text": title},
                # Only the `agg` — the half of the solid gauge's subtitle the chart cannot draw.
                # The dial is on the axis now, in ticks, and repeating it here would be the one
                # thing worse than not saying it: two homes for one number, free to disagree.
                "subtitle": {"text": agg},
                # GEOMETRY, not plumbing — and that is the family's sharpest inversion. The solid
                # gauge's pane is what resolves `highcharts-more`, so dropping it there blanks the
                # iframe while the PNG renders perfectly. A needle resolves the module from
                # `chart.type` alone (verified against the pane, `plotOptions` and a bare series
                # type, each in isolation), so this key could be deleted and the chart would still
                # DRAW — just as a full circle with a disc behind it.
                #
                # It says WHAT the dial is and NOTHING about where to put it: no `size` (silently
                # dropped by highcharts-core) and no `center` (unsteerable without it). See
                # `_NEEDLE_START_ANGLE` above for why that is a conclusion rather than a gap.
                "pane": {
                    "startAngle": _NEEDLE_START_ANGLE,
                    "endAngle": _NEEDLE_END_ANGLE,
                    "background": [
                        {
                            "backgroundColor": _GAUGE_TRACK_COLOR,
                            "borderWidth": 0,
                            "innerRadius": _NEEDLE_FACE_INNER_PCT,
                            "outerRadius": _NEEDLE_FACE_OUTER_PCT,
                            # Said out loud because the default is a CIRCLE: an arc gauge left to
                            # itself draws a full disc behind its semicircle.
                            "shape": "arc",
                        }
                    ],
                },
                # The axis, DRAWN — the one thing the solid gauge cannot have and the reason this
                # type exists. Its labels, ticks and line are all themed for dark mode by
                # `_themed`'s generic axis loop, so this type needs no hook of its own for them.
                "yAxis": {
                    "min": low,
                    "max": high,
                    "tickWidth": 2,
                    "tickLength": 8,
                    "minorTickWidth": 0,
                    # BOTH grid widths, and the MINOR one is the load-bearing half — which is
                    # exactly backwards from what you would guess, and only rendering says so.
                    # `_themed` writes a `gridLineColor` onto every axis it finds, so the major
                    # one has to be pinned or dark-mode readers get concentric gridlines nobody
                    # asked for. But the MINOR gridline is not themed by anything, and Highcharts
                    # defaults it to 1px of `#f2f2f2` — invisible on the light dial face, and a
                    # BLAZING WHITE STARBURST across the dark one (verified by rendering: a dense
                    # radial fan of white lines, unmissable, on a chart whose every unit test
                    # passed). The face carries no grid at all, so both go to zero and the ticks
                    # alone mark the scale.
                    "gridLineWidth": 0,
                    "minorGridLineWidth": 0,
                    # Highcharts titles a value axis "Values" unless it is explicitly CLEARED, and
                    # None does not clear it — an empty string does (heatmap's rule).
                    "title": {"text": ""},
                },
                # Not redundant, and for a sharper reason than the ring's: this type prints NOTHING
                # in the mark, so a needle carries no name on the chart at all (the ring at least
                # has its hub label). The legend is therefore the ONLY thing that says which reading
                # is whose — always, not merely past a gate — and the only thing that names an empty
                # column, whose null point draws no needle either. It is what the whole
                # print-nothing-in-the-mark decision rests on.
                "legend": {"enabled": True},
                # `{series.name}`, the solid gauge's answer for the solid gauge's reason: a gauge
                # series holds exactly ONE point, so the mark's identity is not on the point. It
                # IS the series.
                "tooltip": {
                    "headerFormat": "",
                    "pointFormat": f"{{series.name}}: <b>{_GAUGE_VALUE_FORMAT}</b>",
                },
                "plotOptions": {
                    "gauge": {
                        # The hub. One colour for all N needles — see `_NEEDLE_PIVOT_COLOR` for
                        # why a per-series pivot is a lie rather than a nicety.
                        "pivot": {
                            "backgroundColor": _NEEDLE_PIVOT_COLOR,
                            "radius": _NEEDLE_PIVOT_RADIUS,
                            "borderWidth": 0,
                        },
                        # NO `dial` HERE, and its absence is the point. It was written first, on the
                        # reasoning that `topWidth` is demanded at "both levels" — and that is
                        # simply false: every needle carries its OWN complete dial (they must, since
                        # each needs its own hue and length), so a plotOptions dial has nothing left
                        # to default and does no work at all. Deleting it changes not one byte of the
                        # emitted JS. It is an option that LOOKS load-bearing and isn't — the exact
                        # thing this module tests other libraries for — and carrying one of our own
                        # would be worse than any of theirs, because ours comes with a comment
                        # swearing it is needed.
                        #
                        # The `topWidth` trap is real and is guarded where it actually bites: in
                        # `_NEEDLE_DIAL`, which every SERIES dial is spread from.
                        #
                        # What keeps an OVERRIDDEN dial honest: a reading past the end of the scale
                        # swings PAST the last tick instead of pegging exactly on it, where it would
                        # be pixel-identical to a true reading of the maximum. See the constant —
                        # this is the one place the two gauges would otherwise disagree, and the
                        # only reading a Static PNG could not contradict.
                        "overshoot": _NEEDLE_OVERSHOOT_DEGREES,
                        "stickyTracking": False,  # one point per series: hover the needle you mean
                        # NOTHING IS PRINTED IN THE MARK, and this type needs no gate constant
                        # either — xrange's rule, arrived at from xrange's premise. The five types
                        # that DO print a value in the mark print it because it can be read against
                        # no axis (an angle, an area, a link's width, a bar floating above an
                        # invisible running total). A needle's reading is an ANGLE AGAINST A DRAWN
                        # AXIS that renders in the Static PNG too — that IS the type — and its
                        # identity is in the legend, which it carries anyway to name an empty
                        # column. There is nothing left for a label to say that the chart does not
                        # already show.
                        #
                        # It was built the other way first, and the renders killed it. Highcharts
                        # anchors every gauge series' label at the SAME point, so N labels need N
                        # per-series offsets, a measured leading, a gate — and then the stack, the
                        # arc and the subtitle cannot all fit at 300px, the smallest chart the app
                        # draws. Both levers that would have bought the room are closed BY THE
                        # LIBRARY: `pane.size` is silently dropped (a percentage string validates
                        # and is then never assigned), and `yAxis.labels.distance` rejects 0 with
                        # `EmptyValueError` and refuses a negative outright, so the tick labels
                        # cannot be pulled inside the band. Four constants and a gate, all to
                        # reprint a number already on the axis.
                        #
                        # Disabled EXPLICITLY, and that is the whole reason this key exists: a
                        # gauge's dataLabels default to ON — unlike heatmap's and column's — so
                        # merely omitting it would print Highcharts' own boxed label, N of them
                        # stacked at one anchor.
                        "dataLabels": {"enabled": False},
                        # No `yAxis.plotBands` — the red/amber/green zones a speedometer is
                        # popularly drawn with. Solidgauge's argument against `yAxis.stops`,
                        # unchanged: a band is a JUDGMENT ("this much is bad"), and the data never
                        # said so. The user picked columns and a reduction; they did not declare a
                        # target, and inventing one for them is the confident lie this module's
                        # whole doctrine exists to refuse. (For the record it would also be a poor
                        # one: a plot band's `thickness`, `innerRadius` and `outerRadius` are all
                        # accepted by `Chart.from_options` and silently dropped, so the bands could
                        # not even be drawn where we wanted them.)
                    }
                },
                "series": needles,
            },
            dark=dark,
        )

    assert x_col is not None  # every other type NAMES its marks with it (guarded above)

    # Every type reads x_col as a mark LABEL — a pie slice name, an axis category, a
    # sankey source node, a boxplot group — EXCEPT scatter/bubble with a numeric x, where
    # x is a coordinate the per-point `_plottable` already guards. For the label case, a
    # missing or non-finite label names nothing drawable, so drop its row once, here, in
    # one place, rather than let each branch stringify it to the literal "nan"/"inf" mark.
    # This applies the value-column missing-data policy to the label column too, uniformly
    # (see `_label_ok`); before, only sankey and boxplot dropped such a row. sankey's OTHER
    # label column, target_col, is handled in its own branch (this filter reaches x_col
    # only). Reassigning df to the filtered frame keeps every branch's position-aligned
    # `zip(..., strict=True)` and category/series builds in lockstep. Gauge returned ABOVE
    # this filter and is the one type it must never reach — it has no label channel, and
    # filtering rows out of an AGGREGATE changes a number rather than dropping a mark.
    x_is_label = not (
        chart_type in (XY_TYPES + BUBBLE_TYPES)
        and pd.api.types.is_numeric_dtype(df[x_col])
    )
    if x_is_label:
        # `.astype(bool)` is load-bearing, not defensive. `.map()` infers its result dtype
        # from the values it produced, and on a ROW-LESS frame there are none to infer from,
        # so it hands back an empty *object* Series rather than an empty *boolean* one. A
        # DataFrame indexed by a non-boolean Series is not a mask at all — pandas reads it as
        # a list of COLUMN NAMES — so `df[...]` would select zero columns and the very next
        # line to touch `df[x_col]` would die with a bare `KeyError: <x_col>`, for every
        # chart type. An empty frame is a legitimate input (a CSV with headers and no rows),
        # and it should draw an empty chart, not raise. The cast pins the dtype so the empty
        # case masks exactly like the populated one.
        df = df[df[x_col].map(_label_ok).astype(bool)]

    if chart_type in SINGLE_VALUE_TYPES:  # pie
        value_col = y_cols[0]
        data = [
            {"name": str(name), "y": float(value)}
            for name, value in zip(df[x_col], df[value_col], strict=True)
            if _plottable(value)
        ]
        return _themed(
            {
                "chart": {"type": "pie"},
                "colors": colors,
                "title": {"text": title},
                "tooltip": {
                    "pointFormat": "{series.name}: <b>{point.percentage:.1f}%</b>"
                },
                "plotOptions": {
                    "pie": {
                        "allowPointSelect": True,
                        "cursor": "pointer",
                        "dataLabels": {
                            "enabled": True,
                            "format": "{point.name}: {point.y}",
                        },
                    }
                },
                "series": [{"name": value_col, "data": data}],
            },
            dark=dark,
        )

    if chart_type in TREEMAP_TYPES:  # nested rectangles sized by value (like pie)
        value_col = y_cols[0]
        # Same single-value shape as pie: x_col labels each tile, the first y
        # column sizes it. Drop NaN-valued rows like pie (a tile can't be sized
        # without a value) — not the heatmap keep-as-EnforcedNull path. The leaf
        # key is "value" (NOT pie's "y"): highcharts-core's treemap point model
        # reads "value" and silently ignores a stray "y".
        data = [
            {"name": str(name), "value": float(value)}
            for name, value in zip(df[x_col], df[value_col], strict=True)
            if _plottable(value)
        ]
        return _themed(
            {
                "chart": {"type": "treemap"},
                "colors": colors,
                "title": {"text": title},
                # Name the tile and its value (the default shows a bare value);
                # _themed() merges dark chrome onto this as it does for the pie one.
                "tooltip": {
                    "headerFormat": "",
                    "pointFormat": "{point.name}: <b>{point.value}</b>",
                },
                # In-tile labels already identify each tile, so a categorical
                # legend (which would just repeat them) is turned off.
                "legend": {"enabled": False},
                "plotOptions": {
                    "treemap": {
                        "layoutAlgorithm": "squarified",
                        # Each tile a distinct DEFAULT_COLORS hue, like pie — the
                        # area already carries the value, so color distinguishes
                        # tiles rather than re-encoding size.
                        "colorByPoint": True,
                        # Label each tile with its name AND value on two lines.
                        # Like pie ("{name}: {y}") and heatmap ("{value}"), the
                        # value is printed IN the mark, so the Static-PNG mode
                        # (which has no hover tooltip) still shows the numbers, not
                        # just relative areas. Two lines rather than one keeps it
                        # from crowding narrow tiles; Highcharts hides any label
                        # that still doesn't fit. "contrast" text + outline stays
                        # legible on every palette fill in BOTH themes — the label
                        # sits on the tile, not the chart background — so, unlike
                        # pie's labels, it needs no dark-mode color flip.
                        "dataLabels": _in_mark_labels("{point.name}<br>{point.value}"),
                    }
                },
                "series": [{"name": value_col, "data": data}],
            },
            dark=dark,
        )

    if chart_type in SANKEY_TYPES:  # node-link flows sized by weight
        assert target_col is not None  # guarded above for sankey
        weight_col = y_cols[0]
        # Links are {from, to, weight} DICTS. Not the [x, y, value] arrays heatmap
        # builds: highcharts-core rejects the equivalent `keys`-plus-arrays sankey
        # series outright (HighchartsValueError). The node names are stringified
        # like pie's/treemap's, since highcharts-core's point model rejects a
        # non-string name. A row missing any of the three can't be an edge — and a
        # weightless link serializes SILENTLY, as an invisible zero-width one — so
        # drop it, as pie drops a valueless slice. No EnforcedNull: unlike the
        # heatmap grid, there's no cell to keep aligned.
        # dict[str, object]: a link carries str/float values plus, below, a nested
        # dataLabels dict.
        links: list[dict[str, object]] = [
            {"from": str(src), "to": str(dst), "weight": float(weight)}
            for src, dst, weight in zip(
                df[x_col], df[target_col], df[weight_col], strict=True
            )
            # The nodes are LABELS, so `_label_ok` guards them (present, and finite if
            # numeric — a non-finite node would stringify to "inf"); the weight is a
            # number, so it must be finite too — see _plottable. The x_col (source) filter
            # already ran up front; target_col is this branch's own second label column,
            # so it is checked here.
            if _label_ok(src) and _label_ok(dst) and _plottable(weight)
        ]
        if len(links) <= _SANKEY_DATALABEL_MAX_LINKS:
            for link in links:
                # dict() copies the module constant so nothing downstream can mutate
                # it, as _HEATMAP_GRADIENT is copied for _themed.
                link["dataLabels"] = dict(_SANKEY_LINK_LABEL)
        return _themed(
            {
                "chart": {"type": "sankey"},
                # Cycled across the nodes (sankey colors its links from the node
                # they leave), so this is a genuinely categorical use of the palette
                # — like pie/treemap, unlike heatmap's colors-for-consistency.
                "colors": colors,
                "title": {"text": title},
                # The LINK tooltip: name both ends and the flow. The two column
                # names are user/CSV-supplied, so they go through _tooltip_label as
                # bubble's do; the {point.weight} token must stay a literal, hence
                # the plain (non-f) second segment. _themed() merges dark chrome
                # onto this, as it does for the pie and bubble tooltips.
                "tooltip": {
                    "headerFormat": "",
                    "pointFormat": (
                        f"{_tooltip_label(x_col)} → {_tooltip_label(target_col)}: "
                        "<b>{point.weight}</b>"
                    ),
                },
                # Each node is labelled on the chart, so a categorical legend would
                # only repeat those names (the treemap reasoning).
                "legend": {"enabled": False},
                "plotOptions": {
                    "sankey": {
                        # The NODE tooltip (total throughput of a hovered node) MUST
                        # live here, not on the tooltip above: highcharts-core's
                        # Tooltip model has no nodeFormat, so a top-level one is
                        # accepted by from_options and then silently dropped from
                        # the emitted JS — the treemap "value not y" trap again.
                        "tooltip": {"nodeFormat": "{point.name}: <b>{point.sum}</b>"},
                        # Labels each NODE with its name, via Highcharts' own default
                        # nodeFormat. We can't name that default explicitly (this
                        # dict's nodeFormat is dropped too) and a `format` here would
                        # apply to the links as well, blanking the node names — so
                        # the link weights are labelled per-link instead, above. No
                        # color: Highcharts' default `contrast` keeps both the names
                        # and the weights legible in light and dark alike.
                        "dataLabels": {"enabled": True},
                    }
                },
                "series": [{"name": weight_col, "data": links}],
            },
            dark=dark,
        )

    if chart_type in XY_TYPES:  # scatter
        numeric_x = pd.api.types.is_numeric_dtype(df[x_col])
        series = []
        for col in y_cols:
            if numeric_x:
                points = [
                    [float(x), float(y)]
                    for x, y in zip(df[x_col], df[col], strict=True)
                    if _plottable(x) and _plottable(y)
                ]
            else:
                # Non-numeric x: place points by row position (the values label
                # those positions via _xy_x_axis's categories); drop missing y.
                points = [[i, float(y)] for i, y in enumerate(df[col]) if _plottable(y)]
            series.append({"name": col, "data": points})
        return _themed(
            {
                "chart": {"type": "scatter", "zooming": {"type": "xy"}},
                "colors": colors,
                "title": {"text": title},
                "xAxis": _xy_x_axis(df, x_col, numeric_x=numeric_x),
                "yAxis": {"title": {"text": ", ".join(y_cols)}},
                "legend": {"enabled": len(series) > 1},
                "series": series,
            },
            dark=dark,
        )

    if chart_type in BUBBLE_TYPES:  # bubble: scatter plus a size (z) dimension
        assert size_col is not None  # guarded above for bubble
        numeric_x = pd.api.types.is_numeric_dtype(df[x_col])
        series = []
        for col in y_cols:
            if numeric_x:
                points = [
                    [float(x), float(y), float(z)]
                    for x, y, z in zip(df[x_col], df[col], df[size_col], strict=True)
                    if _plottable(x) and _plottable(y) and _plottable(z)
                ]
            else:
                # Non-numeric x: place points by row position (like scatter), each
                # still carrying its y and size; drop rows missing y or size.
                points = [
                    [i, float(y), float(z)]
                    for i, (y, z) in enumerate(zip(df[col], df[size_col], strict=True))
                    if _plottable(y) and _plottable(z)
                ]
            series.append({"name": col, "data": points})
        # Name all three dimensions in the tooltip (the default shows a bare
        # x/y/z). For a non-numeric x the point's x is a row index, so reference
        # the category label instead. _themed() merges dark chrome onto this — as
        # it does for the pie tooltip — so these labels survive theming.
        x_ref = "{point.x}" if numeric_x else "{point.category}"
        tooltip = {
            "headerFormat": "",
            "pointFormat": (
                f"{_tooltip_label(x_col)}: <b>{x_ref}</b><br/>"
                f"{{series.name}}: <b>{{point.y}}</b><br/>"
                f"{_tooltip_label(size_col)}: <b>{{point.z}}</b>"
            ),
        }
        return _themed(
            {
                "chart": {"type": "bubble", "zooming": {"type": "xy"}},
                "colors": colors,
                "title": {"text": title},
                "tooltip": tooltip,
                "xAxis": _xy_x_axis(df, x_col, numeric_x=numeric_x),
                "yAxis": {"title": {"text": ", ".join(y_cols)}},
                "legend": {"enabled": len(series) > 1},
                "series": series,
            },
            dark=dark,
        )

    if chart_type in HEATMAP_TYPES:  # an x-category × y-category value matrix
        # Wide-form: x_col's values are the X (column) categories, each y column
        # *name* is a Y (row) category, and every cell is [x_index, y_index,
        # value] — the category-x + numeric-y shape reinterpreted as a grid. A
        # missing value stays in place as EnforcedNull (an empty nullColor cell)
        # so the grid never misaligns, unlike the pie/scatter/bubble drop paths.
        # Cells are colored by a sequential colorAxis, not the categorical
        # DEFAULT_COLORS palette — so this is the one type that carries "colors"
        # only for cross-type consistency. dict() copies the module gradient so
        # _themed's dark-mode mutation can't corrupt it.
        categories = _category_labels(df, x_col)
        cells = [
            [i, j, _num(value)]
            for j, col in enumerate(y_cols)
            for i, value in enumerate(df[col].tolist())
        ]
        heatmap_opts: dict[str, object] = {"nullColor": _HEATMAP_NULL}
        # On a small grid, print each cell's value inside it (the norm for
        # annotated heatmaps); "contrast" text + outline stays legible across the
        # whole gradient and in dark mode. Skipped on large grids, where the labels
        # would overprint into noise.
        if len(cells) <= _HEATMAP_DATALABEL_MAX_CELLS:
            heatmap_opts["dataLabels"] = _in_mark_labels("{point.value}")
        return _themed(
            {
                "chart": {"type": "heatmap"},
                "colors": colors,
                "title": {"text": title},
                "xAxis": {"categories": categories, "title": {"text": x_col}},
                "yAxis": {
                    "categories": list(y_cols),
                    "reversed": True,
                    # Empty string (not None, which highcharts-core drops)
                    # suppresses Highcharts' default "Values" y-axis title — the Y
                    # categories are self-labelling and the values live in the cell
                    # colors, not on this axis.
                    "title": {"text": ""},
                },
                "colorAxis": dict(_HEATMAP_GRADIENT),
                # A vertical gradient bar on the right (the heatmap convention) —
                # reads as a quantitative scale beside the grid instead of a
                # categorical key under it competing with the x-axis title.
                "legend": {
                    "enabled": True,
                    "align": "right",
                    "layout": "vertical",
                    "verticalAlign": "top",
                },
                # Name both category axes + the value so a hovered cell says which
                # (row, column) it is. The axis categories are already stringified,
                # so unlike the x_col title this needs no _tooltip_label escaping.
                "tooltip": {
                    "headerFormat": "",
                    "pointFormat": (
                        "{series.xAxis.categories.(point.x)} · "
                        "{series.yAxis.categories.(point.y)}: <b>{point.value}</b>"
                    ),
                },
                "plotOptions": {"heatmap": heatmap_opts},
                "series": [{"name": "value", "data": cells}],
            },
            dark=dark,
        )

    if chart_type in BOXPLOT_TYPES:  # per-category Tukey distributions
        # The one branch that AGGREGATES: every other type maps rows 1:1 onto marks, but
        # a box summarizes many rows. So the frame is read long/tidy — x_col REPEATS, one
        # row per observation — and each of its distinct values becomes one box over the
        # raw numbers in y_cols[0] (a single value column, like pie/treemap/sankey).
        #
        # groupby(sort=False) keeps first-appearance order, the row fidelity every other
        # category-x type has (_category_labels never sorts either). Its default
        # dropna=True drops a row whose x_col KEY is missing: that row names no category,
        # so there is no slot to keep. A group whose observations are all missing is the
        # other case, and it DOES keep its slot, as an EnforcedNull box (see _box_stats),
        # so nothing downstream shifts along the axis.
        value_col = y_cols[0]
        categories = []
        boxes: list[object] = []  # a positional 5-array (or EnforcedNull) per category
        outliers: list[
            list[float]
        ] = []  # [category_index, value] pairs, for the scatter
        for index, (name, observations) in enumerate(df.groupby(x_col, sort=False)):
            # str(): highcharts-core rejects a non-string category (CannotCoerceError),
            # so a numeric grouping column must be stringified, as it is everywhere else.
            categories.append(str(name))
            box, group_outliers = _box_stats(observations[value_col])
            boxes.append(box)
            outliers.extend([index, value] for value in group_outliers)
        series: list[dict[str, object]] = [{"name": value_col, "data": boxes}]
        if outliers:
            # Only when there ARE outliers — an empty linked series would be dead config,
            # the restraint heatmap and sankey show in gating their labels on count.
            # ":previous" binds this to the box series above, so the two read (and toggle)
            # as one dataset. Its marker fillColor survives serialization where the BOX
            # fill does not — see plotOptions below.
            series.append(
                {
                    "type": "scatter",
                    "name": f"{value_col} outliers",
                    "linkedTo": ":previous",
                    "marker": {"fillColor": _BOXPLOT_OUTLIER_COLOR, "lineWidth": 0},
                    "data": outliers,
                }
            )
        return _themed(
            {
                "chart": {"type": "boxplot"},
                # colorByPoint draws each box from this palette, so — like pie, treemap
                # and sankey, and unlike heatmap — the colors here are genuinely used,
                # not merely carried for cross-type consistency.
                "colors": colors,
                "title": {"text": title},
                "xAxis": {"categories": categories, "title": {"text": x_col}},
                "yAxis": {"title": {"text": value_col}},
                # One box series (plus, at most, its linked outlier layer), so a legend
                # would only repeat the single column name already on the y-axis — off,
                # as treemap's and sankey's are.
                "legend": {"enabled": False},
                "plotOptions": {
                    "boxplot": {
                        # Each box takes a distinct palette hue for its border, whiskers,
                        # stem and median. Those hues read against the box's white
                        # interior in BOTH themes, which is why boxplot is the one
                        # mark-styling type with NO hook in _themed: nothing is left to
                        # flip.
                        #
                        # And the interior is white in both themes not by choice but
                        # because it cannot be set at all. `fillColor` (and `stemColor`)
                        # are ACCEPTED by Chart.from_options — _get_kwargs_from_dict reads
                        # them and even sets them on the object — then silently dropped by
                        # _to_untrimmed_dict, since BoxPlotOptions models no such
                        # property. Setting either here would look like it worked and
                        # change nothing in the emitted JS (the trap sankey's top-level
                        # tooltip.nodeFormat sets), and there is no side door: the export
                        # server's `global_options` is coerced through the very same
                        # model. So the fill falls back to Highcharts' own default,
                        # `var(--highcharts-background-color)` — which resolves to white
                        # on the export server, and which _LIGHT_COLOR_SCHEME_CSS pins to
                        # white in the iframe so the two render modes agree.
                        "colorByPoint": True,
                        # The box tooltip lives HERE, not at the top level, for two
                        # reasons. It scopes this format to the boxes, leaving the linked
                        # outlier scatter on Highcharts' own point tooltip (so no
                        # per-series override is needed); and it lets us rename the caps.
                        # Highcharts' default boxplot tooltip calls point.low/point.high
                        # "Minimum"/"Maximum", which is false the moment an outlier is
                        # drawn as its own point — 890 is the maximum, 120 is the whisker.
                        # The dark-mode tooltip CHROME still comes from the top-level
                        # tooltip that _themed writes; Highcharts merges the two.
                        "tooltip": {
                            "headerFormat": "<b>{point.key}</b><br/>",
                            "pointFormat": (
                                "Upper whisker: <b>{point.high}</b><br/>"
                                "Q3: <b>{point.q3}</b><br/>"
                                "Median: <b>{point.median}</b><br/>"
                                "Q1: <b>{point.q1}</b><br/>"
                                "Lower whisker: <b>{point.low}</b>"
                            ),
                        },
                    }
                },
                "series": series,
            },
            dark=dark,
        )

    if chart_type in WATERFALL_TYPES:  # signed deltas floating at a running total
        # The category-x data shape read as DELTAS rather than levels: each bar starts
        # where the last one ended, so the chart shows how a starting value BECOMES an
        # ending one. A single value column, like pie/treemap/sankey/boxplot.
        value_col = y_cols[0]
        categories = _category_labels(df, x_col)
        # A missing or non-finite delta KEEPS its slot as an EnforcedNull (the `_num`
        # cartesian rule) rather than dropping its row as pie and treemap do. Both the
        # shape and the semantics ask for it: the step still names a category on the axis,
        # and a null delta reads as "no change" — Highcharts draws no bar and carries the
        # running total straight through to the next step, which is exactly true. Dropping
        # the row would instead delete a step from the bridge without saying so.
        steps: list[object] = [_num(value) for value in df[value_col].tolist()]
        if steps:
            # The closing bar. `isSum` makes Highcharts total the preceding deltas itself,
            # so the bar reaches down to zero as a LEVEL instead of stacking on the running
            # total as one more delta — which is the whole difference between a bridge and
            # a row of floating bars, and is why the frame carries only the deltas. Only
            # when there IS a step to sum: a lone "Total: 0" bar is not a chart (the
            # restraint boxplot shows in omitting an empty outlier series).
            #
            # The per-point `color` is not decoration; it repairs a genuine ambiguity. Left
            # alone, Highcharts colors the sum by ITS OWN SIGN, exactly as it colors a delta
            # — a positive total takes `upColor` (green), a negative one takes `color` (red).
            # Verified by rendering it, not assumed. But the two signs do not mean the same
            # thing on the two kinds of bar: on a delta, green says "this step ADDED", while
            # on the total green would say only "the end level is above zero" — which a
            # bridge that fell 420 -> 79 would also paint green, cheerfully, all the way
            # down. Same hue, two different claims. So the total is taken off the up/down
            # scale entirely and marked as the different KIND of bar it is: a LEVEL, not a
            # change. A per-point color is the only way to say that, and — unlike boxplot's
            # fillColor — it does survive serialization.
            categories.append(_WATERFALL_TOTAL_LABEL)
            steps.append({"isSum": True, "color": _WATERFALL_SUM_COLOR})
        # `upColor` paints a rise; `color` is the fall (and would be the sum too, but for
        # the per-point override above).
        waterfall_opts: dict[str, object] = {
            "upColor": _WATERFALL_UP_COLOR,
            "color": _WATERFALL_DOWN_COLOR,
        }
        if len(steps) <= _WATERFALL_DATALABEL_MAX_STEPS:
            # Print each delta IN its bar, as pie, heatmap, treemap and sankey print their
            # values — so the Static-PNG mode, which has no hover tooltip, still shows the
            # numbers. This is where waterfall parts company with column/bar, which
            # deliberately carry no labels: their bars stand on the axis, so a height IS a
            # value, while a waterfall's bar floats at the running total and encodes its
            # value as a LENGTH, which no axis can be read against. `inside` keeps the
            # label on the bar, where "contrast" is computed against the fill it sits on
            # (the treemap rule) rather than against the chart background — so it needs no
            # dark-mode flip.
            waterfall_opts["dataLabels"] = _in_mark_labels("{point.y}", inside=True)
        return _themed(
            {
                "chart": {"type": "waterfall"},
                "colors": colors,
                "title": {"text": title},
                "xAxis": {"categories": categories, "title": {"text": x_col}},
                "yAxis": {"title": {"text": value_col}},
                # One series, whose name the y-axis already carries — treemap, sankey and
                # boxplot turn theirs off for the same reason. What a legend COULD key here
                # is rise/fall/total, and those three colors already say it themselves.
                "legend": {"enabled": False},
                # {point.category}, NOT {point.name}: the points are positional, their names
                # living in xAxis.categories, so {point.name} would render blank (bubble's
                # non-numeric-x tooltip resolves the same way, for the same reason). On the
                # appended bar {point.y} is the summed total, which is what it should read.
                "tooltip": {
                    "headerFormat": "",
                    "pointFormat": "{point.category}: <b>{point.y}</b>",
                },
                "plotOptions": {"waterfall": waterfall_opts},
                "series": [{"name": value_col, "data": steps}],
            },
            dark=dark,
        )

    if chart_type in SUNBURST_TYPES:  # a hierarchy drawn as concentric rings
        assert parent_col is not None  # guarded above for sunburst
        value_col = y_cols[0]
        points, max_level, problem = _sunburst_tree(df, x_col, parent_col, value_col)
        if problem:
            # The tree's own contradictions (a cycle, an ambiguous parent label). Raised from
            # the message _sunburst_tree returns rather than one composed here, so this and the
            # app's warning (explain_tree_error) are literally the same string.
            raise ValueError(problem)

        # Seed RING 1 — the top-level branches — with the categorical palette in
        # first-appearance order. Every deeper sector then INHERITS its branch's hue for free
        # (verified by rendering) and is separated from its siblings by the levels'
        # colorVariation, which is what makes a whole branch read as one thing.
        #
        # Seeded per POINT because both of the obvious alternatives are traps. The canonical
        # Highcharts recipe — `levels[].colorByPoint` — is accepted by Chart.from_options and
        # then silently DROPPED from the emitted JS (the treemap "value not y" / sankey
        # nodeFormat trap). And the `colorByPoint` that DOES survive is the series-wide one,
        # which is the wrong option entirely: it hands every point in the flat data array its
        # own palette hue, deep descendants included, destroying the very inheritance the
        # scheme rests on. So sunburst sets no colorByPoint at all.
        #
        # Read from `colors` (not DEFAULT_COLORS): a branch's hue is its arbitrary IDENTITY,
        # like a pie slice's, so a caller may override it — the opposite of waterfall, whose
        # red-means-loss is semantics. `cycle` wraps a short custom palette rather than
        # IndexError-ing (the _BOXPLOT_OUTLIER_COLOR concern); `or` keeps an EMPTY one from
        # exhausting it on the first `next`.
        hues = itertools.cycle(colors or DEFAULT_COLORS)
        for point in points:
            if point["parent"] == _SUNBURST_ROOT_ID:
                point["color"] = next(hues)
        if points:
            # The synthesized root, APPENDED — waterfall's Total set the precedent for drawing
            # a mark the frame never held, and appending keeps the real nodes at their row
            # positions. It carries no `parent` (a parentless point IS a root to Highcharts)
            # and no `value` (Highcharts sums its children, so the centre reads a total that is
            # computed rather than asserted). Only when there IS something to crown: a lone
            # slate disc labelled "All" is not a chart — waterfall's no-lone-Total restraint,
            # and boxplot's in omitting an empty outlier series.
            points.append(
                {
                    "id": _SUNBURST_ROOT_ID,
                    "name": _SUNBURST_ROOT_LABEL,
                    "color": _SUNBURST_ROOT_COLOR,
                }
            )

        sunburst_opts: dict[str, object] = {
            "allowTraversingTree": True,  # click a sector to re-root the chart on it
            "cursor": "pointer",  # ...so it looks clickable (pie's rule)
            "levels": _sunburst_levels(max_level),
            # The one type that does NOT print its value in the mark, and the geometry is why.
            # A sunburst sector is a thin CURVED arc with the text bent along it
            # (rotationMode), so there is room for one short string, not two — and the name is
            # the only thing that identifies a sector at all, since a sunburst has neither axis
            # nor legend, while the value is already encoded as the sector's ANGLE. So the name
            # takes the line and the value lives in the tooltip. Unlike heatmap's and column's,
            # a sunburst's dataLabels default to ON, so past the gate they must be turned off
            # EXPLICITLY: omitting the key (heatmap's and sankey's style) would be a gate that
            # did nothing.
            "dataLabels": (
                _in_mark_labels("{point.name}", rotationMode="circular")
                if len(points) <= _SUNBURST_DATALABEL_MAX_SECTORS
                else {"enabled": False}
            ),
        }
        return _themed(
            {
                "chart": {"type": "sunburst"},
                # Genuinely used, not carried for consistency: ring 1 seeds from it (pie's and
                # treemap's categorical use, not heatmap's).
                "colors": colors,
                "title": {"text": title},
                # {point.name}, not waterfall's {point.category}: a sunburst's points are NAMED
                # dicts rather than positional ones. On the appended root {point.value} is the
                # grand total Highcharts summed, which is exactly what it should read.
                "tooltip": {
                    "headerFormat": "",
                    "pointFormat": "{point.name}: <b>{point.value}</b>",
                },
                # Every sector is labelled on the chart, so a legend naming the single value
                # column would say nothing (treemap's, sankey's, boxplot's and waterfall's
                # reasoning).
                "legend": {"enabled": False},
                "plotOptions": {"sunburst": sunburst_opts},
                "series": [{"name": value_col, "data": points}],
            },
            dark=dark,
        )

    if (
        chart_type in XRANGE_TYPES
    ):  # a Gantt timeline: bars spanning [start, end] on lanes
        assert end_col is not None  # guarded above for xrange
        start_col = y_cols[0]
        points, lanes, is_datetime, problem = _xrange_bars(
            df, x_col, start_col, end_col
        )
        if problem:
            # A column-level contradiction: a start/end column that can place a bar on no
            # axis, or two that disagree about which axis they are on. Raised from the very
            # message `_xrange_bars` RETURNS, rather than one composed here, so this and the
            # app's warning (`explain_xrange_error`) cannot drift apart — the
            # `_SUNBURST_CYCLE` rule.
            raise ValueError(problem)

        # Per-LANE hue, seeded per POINT — sunburst's ring-1 rule, one relation over. A lane's
        # color is its arbitrary IDENTITY, like a pie slice's (the opposite of waterfall's
        # semantic red-means-loss), so it reads from the OVERRIDABLE `colors`. It must be
        # seeded per point rather than by `colorByPoint`, and here the trap is the mirror of
        # sunburst's: where sunburst's `levels[].colorByPoint` is silently DROPPED, xrange's
        # series-level one survives perfectly — and is the wrong option. It would hand every
        # BAR its own hue, so a task's three phases would come out three different colors and
        # the lane would stop reading as one thing. `cycle` wraps a short custom palette (the
        # `_BOXPLOT_OUTLIER_COLOR` concern); `or` keeps an empty one from exhausting `next`.
        # Indexed by the point's LANE POSITION rather than by its name: `y` is already the
        # index `_xrange_bars` assigned, so this needs no second lookup keyed on a label.
        hues = itertools.cycle(colors or DEFAULT_COLORS)
        lane_hues = [next(hues) for _ in lanes]
        for point in points:
            point["color"] = lane_hues[int(point["y"])]  # ty: ignore[invalid-argument-type]

        # A datetime axis must FORMAT its endpoints: {point.x} alone prints raw epoch millis
        # (verified by rendering — a bar labelled "1767571200000").
        span = (
            "{point.x:%Y-%m-%d} → {point.x2:%Y-%m-%d}"
            if is_datetime
            else "{point.x} → {point.x2}"
        )
        x_axis: dict[str, object] = {"title": {"text": f"{start_col} → {end_col}"}}
        if is_datetime:
            x_axis["type"] = "datetime"

        return _themed(
            {
                "chart": {"type": "xrange"},
                # Genuinely used, not carried for consistency: the lanes seed from it (pie's,
                # treemap's and sunburst's categorical use, not heatmap's).
                "colors": colors,
                "title": {"text": title},
                "xAxis": x_axis,
                "yAxis": {
                    "categories": lanes,
                    # First lane at the TOP — a Gantt is read down the page in plan order
                    # (verified by rendering; Highcharts' own default runs bottom-up).
                    "reversed": True,
                    # Highcharts titles a category y-axis "Values" unless it is explicitly
                    # CLEARED, and `None` does not clear it — an empty string does (verified
                    # by rendering). A lane is a name, not a value, so the axis needs no title
                    # at all: the lane labels say everything.
                    "title": {"text": ""},
                },
                # {point.name}, not waterfall's {point.category}: an xrange's points are NAMED
                # dicts (the sunburst rule), so the lane name rides on the point itself. This
                # is not a stylistic echo — {point.category} is waterfall's FIX and xrange's
                # BUG. It reads the X axis, and an xrange's categories are on the Y, so it
                # renders the raw x value: "1767571200000" (verified by rendering). Highcharts'
                # own {point.yCategory} would also work, but the name needs no faith in an
                # untestable internal.
                "tooltip": {
                    "headerFormat": "",
                    "pointFormat": f"<b>{{point.name}}</b><br/>{span}",
                },
                # A single per-point-colored series legends as one useless grey bullet
                # (verified by rendering), and the lane names are already on the axis:
                # treemap's, sankey's, boxplot's, waterfall's and sunburst's reasoning.
                "legend": {"enabled": False},
                "plotOptions": {
                    "xrange": {
                        "pointWidth": _XRANGE_POINT_WIDTH,
                        "minPointLength": _XRANGE_MIN_POINT_LENGTH,
                        # No dataLabels, and no gate constant either: the one mark-bearing type
                        # that needs neither. The five types that print a value IN the mark do
                        # it because the value can be read against no axis — an angle, an area,
                        # a link's width, a bar floating above an invisible running total. An
                        # xrange bar's two ends BOTH land on a real, ticked, gridlined x axis
                        # that renders in the Static PNG too: it is column/bar's case ("their
                        # bars stand on the axis"), not waterfall's. And there is no second
                        # identity left to print — the lane name IS the y-axis category, which
                        # is exactly what labelling the bar would repeat (verified by
                        # rendering).
                    }
                },
                "series": [{"name": start_col, "data": points}],
            },
            dark=dark,
        )

    # cartesian (line/spline/area/areaspline/column/bar) and radar share the same
    # category-x data shape: x_col labels the axis and each y column is a series.
    categories = _category_labels(df, x_col)
    series = [
        {"name": col, "data": [_num(v) for v in df[col].tolist()]} for col in y_cols
    ]

    if chart_type in POLAR_TYPES:  # radar: a polar (spider/web) line chart
        # Highcharts has no "radar" series type — a radar is a `line` drawn on
        # polar axes, so chart.type serializes as "line" and it's chart.polar
        # that pulls in the highcharts-more module (as bubble does). The category
        # axis becomes the angular spokes and the value axis the concentric
        # polygon rings; the value axis is left to auto-scale (no forced min),
        # like the cartesian one, so tight or negative data isn't clipped.
        return _themed(
            {
                "chart": {"type": "line", "polar": True},
                "colors": colors,
                "title": {"text": title},
                "xAxis": {
                    "categories": categories,
                    "tickmarkPlacement": "on",
                    "lineWidth": 0,
                },
                "yAxis": {"gridLineInterpolation": "polygon", "lineWidth": 0},
                "legend": {"enabled": len(series) > 1},
                "series": series,
            },
            dark=dark,
        )

    return _themed(
        {
            "chart": {"type": chart_type},
            "colors": colors,
            "title": {"text": title},
            "xAxis": {"categories": categories, "title": {"text": x_col}},
            "yAxis": {"title": {"text": ", ".join(y_cols)}},
            "legend": {"enabled": len(series) > 1},
            "series": series,
        },
        dark=dark,
    )


def explain_tree_error(
    df: pd.DataFrame, x_col: str, parent_col: str, value_col: str
) -> str | None:
    """``None`` when a sunburst's parent column describes a tree; otherwise the reason it
    doesn't — the very message ``build_options`` raises.

    The app renders this as a warning and stops, so the two can never say different things
    (the ``X_IN_Y_GUARD_TYPES`` named-once rule, and the ``explain_export_failure`` precedent:
    the builder owns the relationship, so the builder owns the diagnosis).

    Needed because the interactive path does NOT catch builder errors. Nothing the UI can
    select makes any other type raise, and sunburst's tree guards — the one failure a user can
    reach just by uploading a CSV — have to keep that true.
    """
    return _sunburst_tree(df, x_col, parent_col, value_col)[2]


def explain_xrange_error(
    df: pd.DataFrame, x_col: str, start_col: str, end_col: str
) -> str | None:
    """``None`` when an xrange's start and end columns can both place a bar on ONE axis;
    otherwise the reason they can't — the very message ``build_options`` raises.

    ``explain_tree_error``'s contract, for a column pair rather than a tree: the builder owns
    the coordinate relationship, so the builder owns the diagnosis, and the app's warning
    cannot drift from the exception it stands in for.

    Needed for exactly ``explain_tree_error``'s reason — the interactive path does NOT catch
    builder errors — and xrange adds one more that a user can reach without writing any code:
    a DATE start beside a NUMERIC end, selectable from the app's own pickers over an ordinary
    uploaded CSV. So it must warn rather than render a traceback.

    Its sibling contradiction — a start or end column that is neither dates nor numbers — is
    NOT reachable that way, and deliberately so: the app sources both pickers from
    ``coordinate_columns``, which is this module's own answer to the same question, so a column
    of task names is never offered in the first place. That leaves it reachable only through
    the pure builder API (a hand-built frame, or a caller that does its own column selection),
    which is precisely why this function reports rather than assumes: the guard in the app is
    belt, and the returned message is braces.
    """
    return _xrange_bars(df, x_col, start_col, end_col)[3]


def coordinate_columns(df: pd.DataFrame) -> list[str]:
    """The columns that can place a bar on an axis — numbers, or dates.

    Exported for the app's xrange pickers, and sourced from ``_coordinates`` itself, so a
    selectbox can never offer a column the builder would refuse: the can't-drift rule applied
    to which options appear in a widget.

    It is what lets ``streamlit_app`` widen its Start/End controls past
    ``select_dtypes("number")`` — which a Gantt needs, since a date column is object dtype and
    so is invisible to that filter — without reintroducing the hazard that filter exists to
    prevent, of handing the builder a column of text it can only reject. (And even if one got
    through, ``_coordinates`` returns a MESSAGE rather than raising, so this is belt and
    braces rather than load-bearing.)
    """
    return [col for col in df.columns if _coordinates(df[col])[1] != _COORD_NEITHER]


def count_marks(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str | None,
    y_cols: list[str],
    *,
    target_col: str | None = None,
    parent_col: str | None = None,
    end_col: str | None = None,
) -> int:
    """The number of marks ``build_options`` will draw, for the app's count-adaptive KPI
    (a heatmap's cells, a treemap's tiles, a sankey's flows, a boxplot's boxes, a
    waterfall's steps, a sunburst's sectors).

    Defined here, beside ``build_options`` and reusing its very ``_label_ok`` / ``_plottable``
    predicates, so the KPI number can never drift from what the chart actually renders — the
    reason the drop rules live in this module at all. Reads only the columns each type needs,
    so it stays correct above ``streamlit_app``'s empty-``y_cols`` guard (heatmap returns 0
    without touching ``y_cols[0]``; every other count-adaptive type uses a single-value Y
    control, which guarantees one y column). A row whose label is not drawable is dropped in
    every type (the uniform
    label policy); for treemap/sankey a non-plottable value/weight drops it too, while a
    heatmap keeps every drawable-label cell (missing ones as ``EnforcedNull``), a boxplot
    keeps one box per distinct drawable label (an all-missing group included), and a
    waterfall keeps one bar per drawable label (a missing delta included, as an
    ``EnforcedNull``) plus its appended total. Sunburst and xrange are the two types whose
    count is not a row filter at all — see their branches, which reuse the whole build rather
    than the predicates — and sunburst's, like waterfall's, exceeds its drawable row count, by
    the appended root. Xrange's does not: it appends nothing, so it is one bar per surviving
    row.

    The GAUGE FAMILY (``solidgauge`` and ``gauge``) has no rule here AT ALL, and deliberately:
    their marks ARE their series — one ring, or one needle, per y column, an empty column kept as
    a null mark rather than dropped — so ``len(y_cols)`` is an
    invariant and the app's default "Series plotted" KPI is already exactly the mark count. They
    are therefore absent from ``MARK_METRICS`` too, and a rule here that only restated
    ``len(y_cols)`` would be the can't-drift rule run backwards: a second computation of a fact
    that cannot differ from the first. (The bail below is keyed on ``GAUGE_TYPES``, so the needle
    inherited this the day it was added, with no edit.)
    """
    if chart_type in GAUGE_TYPES or x_col is None:
        # Bails out ABOVE the shared label mask below, which would otherwise die on `df[None]`
        # before reaching the same "no rule for this type" message that line/pie/scatter get.
        raise ValueError(f"count_marks has no rule for {chart_type!r}")
    if chart_type in XRANGE_TYPES:
        # Whole-build reuse, like sunburst's branch below and NOT like treemap's/sankey's
        # predicate masks — and the reason is subtler than sunburst's, which is why it is worth
        # spelling out. A row's SURVIVAL is genuinely per-row (its own label, its own start,
        # its own end), so xrange looks like it belongs on the mask path. But the AXIS KIND is
        # a COLUMN-level fact that every row's start and end is read THROUGH, and the two
        # callers do not hold the same column: `build_options` reaches its branch on the
        # `_label_ok`-FILTERED frame, while this runs on the RAW one. A branch that reused only
        # `_spannable` could therefore sniff a different axis than the chart drew. Reusing the
        # build makes that unrepresentable — this IS `len(series[0]["data"])`.
        assert end_col is not None  # the app only counts what it can also build
        points, _lanes, _is_datetime, problem = _xrange_bars(
            df, x_col, y_cols[0], end_col
        )
        # A contradictory column pair draws nothing — build_options raises, the app warns and
        # stops — so it counts nothing. And this must NOT raise, for the reason the sunburst
        # branch below must not: count_marks runs ABOVE the app's guards.
        return 0 if problem else len(points)
    if chart_type in SUNBURST_TYPES:
        # Sunburst's drops are not a per-row mask, so this branch sits ABOVE the shared one
        # below and reuses no predicate. A node's fate depends on its ANCESTORS (a dangling
        # parent, a cycle) and on its DESCENDANTS (a valueless internal node lives only if a
        # leaf under it does), so instead of reusing the drop predicates it reuses the whole
        # tree build — the same _sunburst_tree the chart is drawn from. That is the strongest
        # form of the can't-drift rule in this module: the count is len(series[0]["data"]) by
        # construction. It also means this branch touches no `.map()` mask, so the row-less
        # `.astype(bool)` trap cannot arise in it (see _sunburst_tree).
        assert parent_col is not None  # the app only counts what it can also build
        points, _max_level, problem = _sunburst_tree(df, x_col, parent_col, y_cols[0])
        # A contradictory tree draws nothing — build_options raises, and the app warns and
        # stops — so it counts nothing. And this must NOT raise: count_marks runs ABOVE the
        # app's guards, so a raise here would blow the page up with a traceback before the
        # warning that explains it could render. The KPI reads 0 over the empty chart, the same
        # useful empty state "Series plotted" gives before the empty-selection guard fires.
        if problem or not points:
            return 0
        # Plus the appended root, a drawn sector like any other — waterfall's appended-total
        # rule, and the second type whose count exceeds its row count.
        return len(points) + 1
    # `.astype(bool)` on all three masks, the same cast — and for the same reason —
    # `build_options`' label filter makes. On a ROW-LESS frame `.map()` has no values to infer
    # a result dtype from, so it hands back an empty NON-boolean Series (object, or `str` for
    # an Arrow-backed column), and each line below then breaks differently on it: `.sum()` of
    # an empty string mask is `''`, so `int()` raises ValueError; `&` between two of them
    # raises straight out of the Arrow kernel; and `&` between a bool mask and a string one
    # still "works" today but is deprecated — pandas warns that it will RAISE in pandas 4 and
    # tells you to cast explicitly, which is exactly what this is. The KPI has to survive a
    # header-only CSV the way the chart now does: reporting 0 marks over an empty chart.
    label_ok = df[x_col].map(_label_ok).astype(bool)
    if chart_type in HEATMAP_TYPES:
        return int(label_ok.sum()) * len(y_cols)
    if chart_type in BOXPLOT_TYPES:
        return int(df.loc[label_ok, x_col].nunique())
    if chart_type in WATERFALL_TYPES:
        # One bar per drawable label — the value is NOT consulted, because a missing delta
        # keeps its slot as an EnforcedNull bar rather than dropping its row (see the
        # branch). Plus the appended total, which is a drawn bar like any other, and which
        # the branch likewise appends only when there is at least one step to sum.
        steps = int(label_ok.sum())
        return steps + 1 if steps else 0
    value_ok = df[y_cols[0]].map(_plottable).astype(bool)
    if chart_type in TREEMAP_TYPES:
        return int((label_ok & value_ok).sum())
    if chart_type in SANKEY_TYPES:
        target_ok = df[target_col].map(_label_ok).astype(bool)
        return int((label_ok & target_ok & value_ok).sum())
    raise ValueError(f"count_marks has no rule for {chart_type!r}")


def make_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str | None,
    y_cols: list[str],
    *,
    container_id: str = "hc_chart",
    title: str | None = None,
    dark: bool = False,
    size_col: str | None = None,
    target_col: str | None = None,
    parent_col: str | None = None,
    end_col: str | None = None,
    agg: str = _GAUGE_DEFAULT_AGG,
    dial: tuple[float, float] | None = None,
) -> Chart:
    """Build and return a highcharts-core ``Chart`` for the given columns."""
    options = build_options(
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
        agg=agg,
        dial=dial,
    )
    chart = Chart.from_options(options)
    chart.container = container_id
    return chart


def build_chart_html(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str | None,
    y_cols: list[str],
    *,
    container_id: str = "hc_chart",
    height: int = 480,
    title: str | None = None,
    dark: bool = False,
    size_col: str | None = None,
    target_col: str | None = None,
    parent_col: str | None = None,
    end_col: str | None = None,
    agg: str = _GAUGE_DEFAULT_AGG,
    dial: tuple[float, float] | None = None,
) -> str:
    """Build a full, self-contained HTML document that renders the chart.

    Includes the Highcharts CDN ``<script>`` tags the chart actually needs
    (resolved by ``get_script_tags`` — e.g. ``highcharts-more`` for a bubble
    chart) plus the ``Highcharts.chart(...)`` call emitted by ``to_js_literal``.
    Pass the result to ``st.iframe(html, height=...)``.

    The document also pins the chart's color scheme (``_LIGHT_COLOR_SCHEME_CSS``) so
    Highcharts' own ``light-dark()`` defaults can't follow the viewer's browser instead
    of the ``dark`` flag.
    """
    chart = make_chart(
        df,
        chart_type,
        x_col,
        y_cols,
        container_id=container_id,
        title=title,
        dark=dark,
        size_col=size_col,
        target_col=target_col,
        parent_col=parent_col,
        end_col=end_col,
        agg=agg,
        dial=dial,
    )

    # For a SOLID gauge this resolves highcharts-more as well as modules/solid-gauge — and it does
    # so only because the options tree carries a `pane`. Without highcharts-more the chart renders
    # as an empty SVG here while the PNG path below renders perfectly (see the gauge branch).
    #
    # The NEEDLE gauge is the standing proof that the second sentence does not generalize: it
    # resolves highcharts-more from `chart.type` ALONE, so its pane is geometry and nothing hangs
    # on it. Two sibling types, the same module, resolved by different keys — which is precisely
    # why this comment names solidgauge rather than "a gauge". Whoever reads it next will be
    # holding one of the two, and the wrong half is a silently blank iframe beside a perfect PNG.
    script_tags = chart.get_script_tags(as_str=True)
    chart_js = chart.to_js_literal()
    # Match the iframe body to the chart's own background so there's no light
    # flash at the edges (or during load) when the app is in dark mode.
    body_bg = _DARK_CHROME["bg"] if dark else "#ffffff"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  {script_tags}
  <style>{_LIGHT_COLOR_SCHEME_CSS}html,body{{margin:0;background:{body_bg};font-family:-apple-system,Segoe UI,Roboto,sans-serif}}</style>
</head>
<body>
  <div id="{container_id}" style="width:100%;height:{height}px;"></div>
  <script>{chart_js}</script>
</body>
</html>"""


def build_chart_png(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str | None,
    y_cols: list[str],
    *,
    title: str | None = None,
    height: int | None = None,
    # The IMAGE's pixel-density multiplier, and the reason the gauge's dial kwarg is `dial`
    # rather than the `scale` it would otherwise want to be called: this one got here first, and
    # it means something completely different.
    scale: int = 2,
    width: int | None = None,
    timeout: int = 30,
    dark: bool = False,
    size_col: str | None = None,
    target_col: str | None = None,
    parent_col: str | None = None,
    end_col: str | None = None,
    agg: str = _GAUGE_DEFAULT_AGG,
    dial: tuple[float, float] | None = None,
) -> bytes:
    """Render the chart to PNG bytes via the Highcharts export server.

    The image is produced server-side, so displaying it (e.g. with
    ``st.image``) needs **no client-side Highcharts JavaScript** — useful for
    static reports or browsers that can't reach the Highcharts CDN. It does
    require the running process to reach the Highcharts export server
    (``export.highcharts.com`` by default; pass a ``server_instance`` to
    ``download_chart`` to self-host). ``scale=2`` yields a crisper image.
    """
    chart = make_chart(
        df,
        chart_type,
        x_col,
        y_cols,
        title=title,
        dark=dark,
        size_col=size_col,
        target_col=target_col,
        parent_col=parent_col,
        end_col=end_col,
        agg=agg,
        dial=dial,
    )
    if height is not None:
        # highcharts-core types `options` and `options.chart` as Optional, but
        # `Chart.from_options` always populates both, so setting height is safe.
        chart.options.chart.height = height  # ty: ignore[unresolved-attribute, invalid-assignment]
    return chart.download_chart(
        format="png",
        scale=scale,
        width=width,
        timeout=timeout,
    )


def explain_export_failure(exc: Exception) -> str:
    """Explain, in the user's terms, why a ``build_chart_png`` call failed.

    ``build_chart_png`` can fail three genuinely different ways, and telling a user to
    "check your network" when the export server answered them is worse than saying
    nothing. They are told apart WITHOUT importing ``requests``: it reaches this project
    only as a transitive dependency of highcharts-core, so importing it directly would be
    depending on something ``pyproject.toml`` never declares.

    - Nothing was ever sent. ``make_chart`` raised before the request — a bad column, an
      unsupported type. Every ``requests`` exception subclasses ``OSError``
      (``HTTPError`` -> ``RequestException`` -> ``OSError``), so anything that is *not*
      an ``OSError`` never left the process.
    - The request was made and no HTTP response came back (connection refused, DNS
      failure, timeout). Those carry ``response = None``.
    - The server answered, and its answer was an error. ``exc.response.status_code``
      separates "it rejected our chart" (4xx) from "it broke" (5xx). A 4xx is the one
      that most needs saying out loud, because the server is plainly reachable.

    Returned as plain markdown for ``st.error``; this module stays Streamlit-free.
    """
    if not isinstance(exc, OSError):
        return (
            "The chart could not be built, so nothing was sent to the export server. "
            "This is a problem with the data or the selected columns — not with your "
            "network."
        )
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status is None:
        return (
            "The Highcharts export server could not be reached. Check your network, or "
            "switch to the **Interactive** mode instead."
        )
    if 400 <= status < 500:
        return (
            f"The Highcharts export server is reachable, but it rejected this chart "
            f"(HTTP {status}). That points at the chart config it was sent, not at your "
            f"network. The **Interactive** mode renders the same chart in the browser."
        )
    return (
        f"The Highcharts export server reported an internal error (HTTP {status}). Try "
        f"again in a moment, or switch to the **Interactive** mode instead."
    )
