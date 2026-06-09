"""Build Highcharts (highcharts-core) charts from pandas DataFrames.

Produces either self-contained HTML for embedding in Streamlit with
``st.iframe`` (or the older ``components.v1.html``), or PNG bytes rendered via
the Highcharts export server.

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
) -> dict:
    """Return a Highcharts options ``dict`` for the given DataFrame and columns.

    - cartesian types (line/spline/area/column/bar): ``x_col`` becomes the
      category axis and each column in ``y_cols`` becomes a series.
    - ``pie``: ``x_col`` labels the slices and the first column in ``y_cols``
      gives their values.
    - ``scatter``: ``x_col`` and each ``y_cols`` column form (x, y) point pairs.
      A non-numeric ``x_col`` is plotted by row position and labelled with the
      column's values via the x-axis categories.

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

    if chart_type in SINGLE_VALUE_TYPES:  # pie
        value_col = y_cols[0]
        data = [
            {"name": str(name), "y": float(value)}
            for name, value in zip(df[x_col], df[value_col], strict=True)
            if not pd.isna(value)
        ]
        return {
            "chart": {"type": "pie"},
            "title": {"text": title},
            "tooltip": {"pointFormat": "{series.name}: <b>{point.percentage:.1f}%</b>"},
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
        }

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
        x_axis = {"title": {"text": x_col}}
        if not numeric_x:
            x_axis["categories"] = [str(v) for v in df[x_col].tolist()]
        return {
            "chart": {"type": "scatter", "zooming": {"type": "xy"}},
            "title": {"text": title},
            "xAxis": x_axis,
            "yAxis": {"title": {"text": ", ".join(y_cols)}},
            "legend": {"enabled": len(series) > 1},
            "series": series,
        }

    # cartesian: line / spline / area / column / bar
    categories = [str(v) for v in df[x_col].tolist()]
    series = [
        {"name": col, "data": [_num(v) for v in df[col].tolist()]} for col in y_cols
    ]
    return {
        "chart": {"type": chart_type},
        "title": {"text": title},
        "xAxis": {"categories": categories, "title": {"text": x_col}},
        "yAxis": {"title": {"text": ", ".join(y_cols)}},
        "legend": {"enabled": len(series) > 1},
        "series": series,
    }


def make_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_cols: list[str],
    *,
    container_id: str = "hc_chart",
    title: str | None = None,
) -> Chart:
    """Build and return a highcharts-core ``Chart`` for the given columns."""
    options = build_options(df, chart_type, x_col, list(y_cols), title=title)
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
) -> str:
    """Build a full, self-contained HTML document that renders the chart.

    Includes the Highcharts CDN ``<script>`` tags the chart actually needs
    (resolved by ``get_script_tags``) plus the ``Highcharts.chart(...)`` call
    emitted by ``to_js_literal``. Pass the result to ``st.iframe(html,
    height=...)`` (or ``components.v1.html``).
    """
    chart = make_chart(
        df, chart_type, x_col, y_cols, container_id=container_id, title=title
    )

    script_tags = chart.get_script_tags(as_str=True)
    chart_js = chart.to_js_literal()

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  {script_tags}
  <style>html,body{{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif}}</style>
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
) -> bytes:
    """Render the chart to PNG bytes via the Highcharts export server.

    The image is produced server-side, so displaying it (e.g. with
    ``st.image``) needs **no client-side Highcharts JavaScript** — useful for
    static reports or browsers that can't reach the Highcharts CDN. It does
    require the running process to reach the Highcharts export server
    (``export.highcharts.com`` by default; pass a ``server_instance`` to
    ``download_chart`` to self-host). ``scale=2`` yields a crisper image.
    """
    chart = make_chart(df, chart_type, x_col, y_cols, title=title)
    if height is not None:
        chart.options.chart.height = height
    return chart.download_chart(
        format="png",
        scale=scale,
        width=width,
        timeout=timeout,
    )
