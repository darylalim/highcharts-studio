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
    CARTESIAN_TYPES,
    SUPPORTED_TYPES,
    build_chart_html,
    build_chart_png,
    make_chart,
)
from sample_data import SAMPLES

# Render modes for the "3 · Render" control.
MODE_INTERACTIVE = "Interactive"
MODE_STATIC = "Static PNG"
RENDER_MODES = [MODE_INTERACTIVE, MODE_STATIC]

# Short status badge (label, icon, color) shown above the chart per mode; the
# caption below the chart carries the full description.
_BadgeColor = Literal["blue", "violet"]
MODE_BADGES: dict[str, tuple[str, str, _BadgeColor]] = {
    MODE_INTERACTIVE: ("Interactive (iframe)", ":material/public:", "blue"),
    MODE_STATIC: ("Static PNG", ":material/image:", "violet"),
}

st.set_page_config(
    page_title="Highcharts Studio",
    page_icon=":material/show_chart:",
    layout="wide",
)


# max_entries bounds each cache so entries are evicted LRU instead of piling up
# as users sweep chart types, columns, heights, and titles (PNG bytes and full
# HTML docs are the largest, so those get the tighter caps).
@st.cache_data(show_spinner=False, max_entries=8)
def load_csv(file) -> pd.DataFrame:
    return pd.read_csv(file)


@st.cache_data(show_spinner="Rendering Highcharts…", max_entries=128)
def cached_chart_html(df, chart_type, x_col, y_cols, height, title) -> str:
    return build_chart_html(
        df,
        chart_type,
        x_col,
        list(y_cols),
        height=height,
        title=title,
    )


@st.cache_data(
    show_spinner="Rendering PNG via the Highcharts export server…", max_entries=64
)
def cached_chart_png(df, chart_type, x_col, y_cols, height, title) -> bytes:
    return build_chart_png(
        df,
        chart_type,
        x_col,
        list(y_cols),
        height=height,
        title=title,
    )


@st.cache_data(show_spinner=False, max_entries=128)
def cached_chart_js(df, chart_type, x_col, y_cols, title) -> str:
    # highcharts-core stubs `to_js_literal` as `str | None`; it returns the JS
    # literal string for a built chart.
    return make_chart(df, chart_type, x_col, list(y_cols), title=title).to_js_literal()  # ty: ignore[invalid-return-type]


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
    if not numeric_cols:
        st.error(
            "This dataset has no numeric columns to plot.", icon=":material/error:"
        )
        st.stop()

    st.header(":material/bar_chart: 2 · Chart")
    chart_type = st.selectbox("Chart type", SUPPORTED_TYPES)

    if chart_type == "pie":
        x_label, y_label, multi = "Slice labels", "Slice values", False
    elif chart_type == "scatter":
        x_label, y_label, multi = "X axis", "Y axis (one or more)", True
    else:  # cartesian
        x_label, y_label, multi = "Category (X) axis", "Series (Y) — one or more", True

    x_col = st.selectbox(x_label, df.columns)

    if multi:
        # Pills show every series choice inline (vs a dropdown); the empty-set
        # guard in the main panel handles a fully-cleared selection.
        y_cols = st.pills(
            y_label, numeric_cols, selection_mode="multi", default=numeric_cols[:1]
        )
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

    st.header(":material/tune: 3 · Render")
    render_mode = (
        st.segmented_control(
            "Mode",
            RENDER_MODES,
            default=MODE_INTERACTIVE,
            help=(
                "- **Interactive** — Highcharts loads from the CDN in a sandboxed "
                "iframe (one-way).\n"
                "- **Static PNG** — rendered server-side via the Highcharts export "
                "server; the browser loads no Highcharts JS."
            ),
        )
        or MODE_INTERACTIVE
    )


# --------------------------------------------------------------------------- #
# Main panel
# --------------------------------------------------------------------------- #
left, right = st.columns([3, 2], gap="large")

with right.container(border=True):
    st.subheader("Source data")
    # Localized number formatting, hidden index, and the chart's X column pinned
    # so it stays visible while scrolling wide CSVs.
    column_config = {
        col: st.column_config.NumberColumn(format="localized") for col in numeric_cols
    }
    column_config[x_col] = (
        st.column_config.NumberColumn(format="localized", pinned=True)
        if x_col in numeric_cols
        else st.column_config.Column(pinned=True)
    )
    st.dataframe(
        df, height=min(height, 360), hide_index=True, column_config=column_config
    )
    st.caption(f"{len(df)} rows × {len(df.columns)} columns")

with left.container(border=True):
    st.subheader("Highcharts output")

    if not y_cols:
        st.warning(
            "Pick at least one numeric column to plot.", icon=":material/warning:"
        )
        st.stop()
    if chart_type in CARTESIAN_TYPES and x_col in y_cols:
        st.warning(
            "The X-axis column can't also be a Y series — pick a different X.",
            icon=":material/warning:",
        )
        st.stop()

    badge_label, badge_icon, badge_color = MODE_BADGES[render_mode]
    st.badge(badge_label, icon=badge_icon, color=badge_color)

    if render_mode == MODE_STATIC:
        # Server-side render: no Highcharts JS runs in the browser.
        try:
            png = cached_chart_png(df, chart_type, x_col, tuple(y_cols), height, title)
        except Exception as exc:  # build error or export-server failure
            st.error(
                f"Static (PNG) render failed.\n\n`{type(exc).__name__}: {exc}`\n\n"
                "This usually means the Highcharts export server is unreachable — "
                "check your network, or pick an interactive mode instead.",
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
        html = cached_chart_html(df, chart_type, x_col, tuple(y_cols), height, title)
        # The HTML is embedded in a sandboxed iframe with a FIXED height — it
        # does not auto-grow to its content, so size it to the chart.
        st.iframe(html, height=height + 24)
        st.caption(
            "Interactive chart — Highcharts JS is loaded from the CDN in the browser."
        )

    with st.expander(
        "View the generated Highcharts config (JavaScript)", icon=":material/code:"
    ):
        chart_js = cached_chart_js(df, chart_type, x_col, tuple(y_cols), title)
        st.code(chart_js, language="javascript")
