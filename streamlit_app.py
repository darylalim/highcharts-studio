"""Streamlit example app that renders ONLY Highcharts visualizations.

Every chart on this page is produced by the Highcharts for Python toolkit
(``highcharts-core``): a pandas DataFrame is turned into a Highcharts options
object, serialized to JavaScript, and embedded in the page via ``st.iframe``
(or rendered server-side to a PNG). No Streamlit-native charts are used.

Run it with:

    uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from highcharts_builder import (
    CARTESIAN_TYPES,
    SUPPORTED_TYPES,
    build_chart_html,
    build_chart_png,
    make_chart,
)

st.set_page_config(page_title="Highcharts × Streamlit", page_icon="📈", layout="wide")


def embed_html(html: str, height: int) -> None:
    """Embed a raw HTML document in a fixed-height iframe.

    Uses the current ``st.iframe`` API when available, falling back to the
    older ``components.v1.html`` on Streamlit versions before ``st.iframe``.
    """
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:  # Streamlit < 1.56
        import streamlit.components.v1 as components

        components.html(html, height=height, scrolling=False)


# --------------------------------------------------------------------------- #
# Sample data (so the app works with no upload). Each returns a fresh DataFrame.
# --------------------------------------------------------------------------- #
def _revenue_vs_cost() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "revenue": [120, 135, 128, 150, 162, 171],
            "cost": [80, 88, 90, 95, 101, 108],
        }
    )


def _fruit_sales() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fruit": ["Apples", "Bananas", "Cherries", "Grapes", "Oranges"],
            "units_sold": [620, 540, 210, 380, 470],
        }
    )


def _height_vs_weight() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "height_cm": [152, 158, 161, 165, 168, 172, 175, 180, 185, 190],
            "weight_kg": [50, 55, 58, 61, 65, 70, 74, 80, 86, 94],
        }
    )


SAMPLES = {
    "Monthly revenue vs cost (line/area/column)": _revenue_vs_cost,
    "Fruit sales (pie/bar/column)": _fruit_sales,
    "Height vs weight (scatter)": _height_vs_weight,
}


@st.cache_data(show_spinner=False)
def load_csv(file) -> pd.DataFrame:
    return pd.read_csv(file)


@st.cache_data(show_spinner="Rendering Highcharts…")
def cached_chart_html(df, chart_type, x_col, y_cols, height, title) -> str:
    return build_chart_html(
        df,
        chart_type,
        x_col,
        list(y_cols),
        height=height,
        title=title,
    )


@st.cache_data(show_spinner="Rendering PNG via the Highcharts export server…")
def cached_chart_png(df, chart_type, x_col, y_cols, height, title) -> bytes:
    return build_chart_png(
        df,
        chart_type,
        x_col,
        list(y_cols),
        height=height,
        title=title,
    )


@st.cache_data(show_spinner=False)
def cached_chart_js(df, chart_type, x_col, y_cols, title) -> str:
    # highcharts-core stubs `to_js_literal` as `str | None`; it returns the JS
    # literal string for a built chart.
    return make_chart(df, chart_type, x_col, list(y_cols), title=title).to_js_literal()  # ty: ignore[invalid-return-type]


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.title("📈 Highcharts visualizations in Streamlit")
st.caption(
    "Every chart below is rendered by **highcharts-core** (the Highcharts for "
    "Python toolkit) and embedded via `st.iframe` — no native Streamlit charts "
    "are used."
)


# --------------------------------------------------------------------------- #
# Sidebar — data source + chart configuration
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("1 · Data")
    source = st.radio("Source", ["Sample dataset", "Upload CSV"], horizontal=True)

    if source == "Sample dataset":
        name = st.selectbox("Dataset", list(SAMPLES))
        df = SAMPLES[name]()
    else:
        uploaded = st.file_uploader("CSV file", type="csv")
        if uploaded is None:
            st.info("Upload a CSV, or switch to a sample dataset.")
            st.stop()
        df = load_csv(uploaded)

    numeric_cols = df.select_dtypes("number").columns.tolist()
    if not numeric_cols:
        st.error("This dataset has no numeric columns to plot.")
        st.stop()

    st.header("2 · Chart")
    chart_type = st.selectbox("Chart type", SUPPORTED_TYPES)

    if chart_type == "pie":
        x_label, y_label, multi = "Slice labels", "Slice values", False
    elif chart_type == "scatter":
        x_label, y_label, multi = "X axis", "Y axis (one or more)", True
    else:  # cartesian
        x_label, y_label, multi = "Category (X) axis", "Series (Y) — one or more", True

    x_col = st.selectbox(x_label, df.columns)

    if multi:
        y_cols = st.multiselect(y_label, numeric_cols, default=numeric_cols[:1])
    else:
        y_cols = [st.selectbox(y_label, numeric_cols)]

    # A stable key keeps a typed title across reruns; an empty field falls back
    # to a per-chart-type default (shown as the placeholder, applied in
    # build_options) instead of silently resetting when the chart type changes.
    title = st.text_input(
        "Chart title",
        key="chart_title",
        placeholder=f"{chart_type.title()} chart",
    )
    height = st.slider("Height (px)", min_value=300, max_value=800, value=480, step=20)

    st.header("3 · Render")
    static = st.toggle(
        "Static image (PNG)",
        value=False,
        help="Render the chart server-side via the Highcharts export server and "
        "show it as a PNG — the browser loads no Highcharts JS. Leave it off "
        "for the interactive (CDN-loaded) chart.",
    )


# --------------------------------------------------------------------------- #
# Main panel
# --------------------------------------------------------------------------- #
left, right = st.columns([3, 2], gap="large")

with right:
    st.subheader("Source data")
    st.dataframe(df, height=min(height, 360))
    st.caption(f"{len(df)} rows × {len(df.columns)} columns")

with left:
    st.subheader("Highcharts output")

    if not y_cols:
        st.warning("Pick at least one numeric column to plot.")
        st.stop()
    if chart_type in CARTESIAN_TYPES and x_col in y_cols:
        st.warning("The X-axis column can't also be a Y series — pick a different X.")
        st.stop()

    if static:
        # Server-side render: no Highcharts JS runs in the browser.
        try:
            png = cached_chart_png(df, chart_type, x_col, tuple(y_cols), height, title)
        except Exception as exc:  # build error or export-server failure
            st.error(
                f"Static (PNG) render failed.\n\n`{type(exc).__name__}: {exc}`\n\n"
                "This usually means the Highcharts export server is unreachable — "
                "check your network, or switch the toggle off for the interactive "
                "chart."
            )
            st.stop()
        st.image(png, width="stretch")
        st.download_button(
            "⬇ Download PNG",
            png,
            file_name=f"{chart_type}-chart.png",
            mime="image/png",
        )
        st.caption(
            "Static PNG rendered server-side via the Highcharts export server — "
            "the browser loads no Highcharts JS."
        )
    else:
        html = cached_chart_html(df, chart_type, x_col, tuple(y_cols), height, title)
        # The HTML is embedded in a sandboxed iframe with a FIXED height — it
        # does not auto-grow to its content, so size it to the chart.
        embed_html(html, height=height + 24)
        st.caption(
            "Interactive chart — Highcharts JS is loaded from the CDN in the browser."
        )

    with st.expander("View the generated Highcharts config (JavaScript)"):
        chart_js = cached_chart_js(df, chart_type, x_col, tuple(y_cols), title)
        st.code(chart_js, language="javascript")
