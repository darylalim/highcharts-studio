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
import math

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
)

# Types whose x_col is a *category* axis, so it can't double as a y series: the
# cartesian family plus radar (which shares their category-x data shape). Kept to
# exactly cartesian + radar because it also parametrizes the shared category-x
# series tests (EnforcedNull gaps, numeric-x-to-string), which heatmap's grid
# shape doesn't share.
CATEGORY_X_TYPES = CARTESIAN_TYPES + POLAR_TYPES

# The full set the x-in-y guard rejects (x_col can't also be a y series): the
# category-axis types plus heatmap and boxplot, whose x_col is likewise a category
# axis (heatmap's values label the columns; boxplot's name the boxes) but which stay
# out of CATEGORY_X_TYPES above so the shared series tests skip them — neither uses
# the cartesian per-point series build. Grouping boxplot's observation column by
# itself would give every box exactly one observation, equal to its own label.
# Named once so the builder guard and its streamlit_app mirror share one constant
# and can't drift apart. Sankey is deliberately absent: its x_col is a node label,
# not an axis, and its collision is source-vs-target — target_col isn't in y_cols
# at all, so this rule can't express it (see the dedicated guard in build_options).
X_IN_Y_GUARD_TYPES = CATEGORY_X_TYPES + HEATMAP_TYPES + BOXPLOT_TYPES

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
# (the `<svg>`), because Highcharts sets `color-scheme` on that element — a rule on `html`
# is simply overridden by it. Note this reaches the iframe only: the export server renders
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
    if options["chart"].get("type") in ("column", "bar"):
        # column/bar draw filled shapes with a 1px border that defaults to
        # var(--highcharts-background-color) -> white, which the color-scheme pin
        # keeps white even in dark mode, ringing every bar. Match it to the dark
        # background so the separators disappear as they do in light mode (where the
        # same var resolves to the white shell) -- the pie/treemap/sankey gap rule.
        # The cartesian branch emits no plotOptions, so create it here. Restricted to
        # column/bar: line/spline/area/areaspline have no such border (verified: they
        # paint no white against the dark background).
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
    scatter, bubble, sankey's weight). A ``float()`` that raises ``ValueError`` on a text
    column keeps doing so, here rather than one line later.

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
    numeric = values.astype("float64")
    clean = numeric[numeric.abs() != float("inf")].dropna()
    if clean.empty:
        return EnforcedNull, []
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
    return box, [float(value) for value in outside]


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


def build_options(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_cols: list[str],
    *,
    title: str | None = None,
    colors: list[str] | None = None,
    dark: bool = False,
    size_col: str | None = None,
    target_col: str | None = None,
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

    ``colors`` overrides the series palette; it defaults to ``DEFAULT_COLORS``.
    ``dark=True`` themes the chart chrome (background, text, axes, gridlines,
    tooltip) for dark mode; the series palette itself is shared across modes.
    ``size_col`` names the marker-size column and is required for ``bubble``;
    ``target_col`` names the destination-node column and is required for
    ``sankey``. Each is ignored by the other types.

    Raises ``ValueError`` for an unsupported ``chart_type``, empty ``y_cols``,
    a ``bubble`` chart with no ``size_col``, a ``sankey`` chart with no
    ``target_col`` or whose ``target_col`` is its ``x_col``, or (for the
    category-axis types — cartesian, radar, heatmap, and boxplot) an ``x_col`` that
    is also one of the ``y_cols``.
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
    if chart_type in X_IN_Y_GUARD_TYPES and x_col in y_cols:
        raise ValueError(
            f"x_col {x_col!r} cannot also be a y series for a {chart_type} chart"
        )

    title = title or f"{chart_type.title()} chart"
    colors = list(colors) if colors is not None else list(DEFAULT_COLORS)

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
                        "dataLabels": {
                            "enabled": True,
                            "format": "{point.name}<br>{point.value}",
                            "color": "contrast",
                            "style": {
                                "textOutline": "1px contrast",
                                "fontWeight": "normal",
                            },
                        },
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
            # The nodes are LABELS, so only presence matters for them (a numeric node
            # column is stringified below); the weight is a number, so it must also be
            # finite — see _plottable.
            if not pd.isna(src) and not pd.isna(dst) and _plottable(weight)
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
            heatmap_opts["dataLabels"] = {
                "enabled": True,
                "format": "{point.value}",
                "color": "contrast",
                "style": {"textOutline": "1px contrast", "fontWeight": "normal"},
            }
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


def make_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_cols: list[str],
    *,
    container_id: str = "hc_chart",
    title: str | None = None,
    dark: bool = False,
    size_col: str | None = None,
    target_col: str | None = None,
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
    )
    chart = Chart.from_options(options)
    chart.container = container_id
    return chart


def build_chart_html(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_cols: list[str],
    *,
    container_id: str = "hc_chart",
    height: int = 480,
    title: str | None = None,
    dark: bool = False,
    size_col: str | None = None,
    target_col: str | None = None,
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
    )

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
    x_col: str,
    y_cols: list[str],
    *,
    title: str | None = None,
    height: int | None = None,
    scale: int = 2,
    width: int | None = None,
    timeout: int = 30,
    dark: bool = False,
    size_col: str | None = None,
    target_col: str | None = None,
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
