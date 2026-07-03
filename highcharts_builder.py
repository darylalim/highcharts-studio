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

import pandas as pd
from highcharts_core.chart import Chart
from highcharts_core.constants import EnforcedNull

# Chart types this example supports, grouped by the data shape they need.
CARTESIAN_TYPES = ("line", "spline", "area", "column", "bar")
SINGLE_VALUE_TYPES = ("pie",)
XY_TYPES = ("scatter",)
SUPPORTED_TYPES = CARTESIAN_TYPES + SINGLE_VALUE_TYPES + XY_TYPES

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

# Chart "chrome" (backgrounds, text, axes, gridlines) for dark mode. The series
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


def _themed(options: dict, *, dark: bool) -> dict:
    """Inject dark-mode chrome into a Highcharts options ``dict``.

    A no-op for light mode, so the light-mode output is byte-for-byte what it was
    before dark mode existed. In dark mode it sets the chart background and the
    title/legend/axis/gridline colors to match the dark app shell, leaving the
    series ``colors`` (``DEFAULT_COLORS``) untouched.
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
    return options


def _num(value):
    """Coerce one DataFrame value to a JSON-friendly number or Highcharts null."""
    if pd.isna(value):
        return EnforcedNull
    return float(value)


def build_options(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_cols: list[str],
    *,
    title: str | None = None,
    colors: list[str] | None = None,
    dark: bool = False,
) -> dict:
    """Return a Highcharts options ``dict`` for the given DataFrame and columns.

    - cartesian types (line/spline/area/column/bar): ``x_col`` becomes the
      category axis and each column in ``y_cols`` becomes a series.
    - ``pie``: ``x_col`` labels the slices and the first column in ``y_cols``
      gives their values.
    - ``scatter``: ``x_col`` and each ``y_cols`` column form (x, y) point pairs.
      A non-numeric ``x_col`` is plotted by row position and labelled with the
      column's values via the x-axis categories.

    ``colors`` overrides the series palette; it defaults to ``DEFAULT_COLORS``.
    ``dark=True`` themes the chart chrome (background, text, axes, gridlines) for
    dark mode; the series palette itself is shared across modes.

    Raises ``ValueError`` for an unsupported ``chart_type``, empty ``y_cols``,
    or (for cartesian types) an ``x_col`` that is also one of the ``y_cols``.
    """
    if chart_type not in SUPPORTED_TYPES:
        raise ValueError(
            f"Unsupported chart_type {chart_type!r}; expected one of {SUPPORTED_TYPES}"
        )
    if not y_cols:
        raise ValueError("At least one y column is required.")
    if chart_type in CARTESIAN_TYPES and x_col in y_cols:
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
                points = [
                    [i, float(y)] for i, y in enumerate(df[col]) if not pd.isna(y)
                ]
            series.append({"name": col, "data": points})
        # With a non-numeric x_col the points use the row position as x, so
        # label those positions with the actual values instead of a bare 0..N.
        x_axis: dict[str, object] = {"title": {"text": x_col}}
        if not numeric_x:
            x_axis["categories"] = [str(v) for v in df[x_col].tolist()]
        return _themed(
            {
                "chart": {"type": "scatter", "zooming": {"type": "xy"}},
                "colors": colors,
                "title": {"text": title},
                "xAxis": x_axis,
                "yAxis": {"title": {"text": ", ".join(y_cols)}},
                "legend": {"enabled": len(series) > 1},
                "series": series,
            },
            dark=dark,
        )

    # cartesian: line / spline / area / column / bar
    categories = [str(v) for v in df[x_col].tolist()]
    series = [
        {"name": col, "data": [_num(v) for v in df[col].tolist()]} for col in y_cols
    ]
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
) -> Chart:
    """Build and return a highcharts-core ``Chart`` for the given columns."""
    options = build_options(df, chart_type, x_col, list(y_cols), title=title, dark=dark)
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
) -> str:
    """Build a full, self-contained HTML document that renders the chart.

    Includes the Highcharts CDN ``<script>`` tags the chart actually needs
    (resolved by ``get_script_tags``) plus the ``Highcharts.chart(...)`` call
    emitted by ``to_js_literal``. Pass the result to ``st.iframe(html,
    height=...)``.
    """
    chart = make_chart(
        df, chart_type, x_col, y_cols, container_id=container_id, title=title, dark=dark
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
) -> bytes:
    """Render the chart to PNG bytes via the Highcharts export server.

    The image is produced server-side, so displaying it (e.g. with
    ``st.image``) needs **no client-side Highcharts JavaScript** — useful for
    static reports or browsers that can't reach the Highcharts CDN. It does
    require the running process to reach the Highcharts export server
    (``export.highcharts.com`` by default; pass a ``server_instance`` to
    ``download_chart`` to self-host). ``scale=2`` yields a crisper image.
    """
    chart = make_chart(df, chart_type, x_col, y_cols, title=title, dark=dark)
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
