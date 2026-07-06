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
SUPPORTED_TYPES = (
    CARTESIAN_TYPES
    + SINGLE_VALUE_TYPES
    + XY_TYPES
    + BUBBLE_TYPES
    + POLAR_TYPES
    + HEATMAP_TYPES
)

# Types whose x_col is a *category* axis, so it can't double as a y series: the
# cartesian family plus radar (which shares their category-x data shape). Kept to
# exactly cartesian + radar because it also parametrizes the shared category-x
# series tests (EnforcedNull gaps, numeric-x-to-string), which heatmap's grid
# shape doesn't share.
CATEGORY_X_TYPES = CARTESIAN_TYPES + POLAR_TYPES

# The full set the x-in-y guard rejects (x_col can't also be a y series): the
# category-axis types plus heatmap (whose x_col is likewise a category axis, but
# which stays out of CATEGORY_X_TYPES above so the shared series tests skip it).
# Named once so the builder guard and its streamlit_app mirror share one constant
# and can't drift apart.
X_IN_Y_GUARD_TYPES = CATEGORY_X_TYPES + HEATMAP_TYPES

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
    if options["chart"].get("type") == "pie":
        pie = options["plotOptions"]["pie"]
        pie["dataLabels"] = {**pie.get("dataLabels", {}), "color": t["text"]}
        pie["borderColor"] = t["bg"]  # slice gaps match the dark background
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
        options["plotOptions"]["heatmap"]["nullColor"] = t["grid"]
    return options


def _num(value):
    """Coerce one DataFrame value to a JSON-friendly number or Highcharts null."""
    if pd.isna(value):
        return EnforcedNull
    return float(value)


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

    ``colors`` overrides the series palette; it defaults to ``DEFAULT_COLORS``.
    ``dark=True`` themes the chart chrome (background, text, axes, gridlines,
    tooltip) for dark mode; the series palette itself is shared across modes.
    ``size_col`` names the marker-size column and is required for ``bubble``
    (ignored by the other types).

    Raises ``ValueError`` for an unsupported ``chart_type``, empty ``y_cols``,
    a ``bubble`` chart with no ``size_col``, or (for the category-axis types —
    cartesian, radar, and heatmap) an ``x_col`` that is also one of the
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
            if not pd.isna(value)
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

    if chart_type in XY_TYPES:  # scatter
        numeric_x = pd.api.types.is_numeric_dtype(df[x_col])
        series = []
        for col in y_cols:
            if numeric_x:
                points = [
                    [float(x), float(y)]
                    for x, y in zip(df[x_col], df[col], strict=True)
                    if not pd.isna(x) and not pd.isna(y)
                ]
            else:
                # Non-numeric x: place points by row position (the values label
                # those positions via _xy_x_axis's categories); drop missing y.
                points = [
                    [i, float(y)] for i, y in enumerate(df[col]) if not pd.isna(y)
                ]
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
                    if not pd.isna(x) and not pd.isna(y) and not pd.isna(z)
                ]
            else:
                # Non-numeric x: place points by row position (like scatter), each
                # still carrying its y and size; drop rows missing y or size.
                points = [
                    [i, float(y), float(z)]
                    for i, (y, z) in enumerate(zip(df[col], df[size_col], strict=True))
                    if not pd.isna(y) and not pd.isna(z)
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
) -> Chart:
    """Build and return a highcharts-core ``Chart`` for the given columns."""
    options = build_options(
        df, chart_type, x_col, list(y_cols), title=title, dark=dark, size_col=size_col
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
) -> str:
    """Build a full, self-contained HTML document that renders the chart.

    Includes the Highcharts CDN ``<script>`` tags the chart actually needs
    (resolved by ``get_script_tags`` — e.g. ``highcharts-more`` for a bubble
    chart) plus the ``Highcharts.chart(...)`` call emitted by ``to_js_literal``.
    Pass the result to ``st.iframe(html, height=...)``.
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
  <style>html,body{{margin:0;background:{body_bg};font-family:-apple-system,Segoe UI,Roboto,sans-serif}}</style>
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
        df, chart_type, x_col, y_cols, title=title, dark=dark, size_col=size_col
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
