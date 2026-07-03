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
def cached_chart_html(df, chart_type, x_col, y_cols, height, title, dark) -> str:
    return build_chart_html(
        df,
        chart_type,
        x_col,
        list(y_cols),
        height=height,
        title=title,
        dark=dark,
    )


@st.cache_data(
    show_spinner="Rendering PNG via the Highcharts export server…", max_entries=64
)
def cached_chart_png(df, chart_type, x_col, y_cols, height, title, dark) -> bytes:
    return build_chart_png(
        df,
        chart_type,
        x_col,
        list(y_cols),
        height=height,
        title=title,
        dark=dark,
    )


@st.cache_data(show_spinner=False, max_entries=128)
def cached_chart_js(df, chart_type, x_col, y_cols, title, dark) -> str:
    # highcharts-core stubs `to_js_literal` as `str | None`; it returns the JS
    # literal string for a built chart.
    return make_chart(  # ty: ignore[invalid-return-type]
        df, chart_type, x_col, list(y_cols), title=title, dark=dark
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
    if not numeric_cols:
        st.error(
            "This dataset has no numeric columns to plot.", icon=":material/error:"
        )
        st.stop()

    st.header(":material/bar_chart: 2 · Chart")
    chart_type = st.selectbox(
        "Chart type",
        SUPPORTED_TYPES,
        help=(
            "How the type reshapes the controls below:\n"
            "- **pie** — one label column + one value column\n"
            "- **scatter** — an X column paired with one or more numeric Y series\n"
            "- **line / spline / area / column / bar** — a category X axis with "
            "one or more numeric Y series"
        ),
    )

    if chart_type == "pie":
        x_label, y_label, multi = "Slice labels", "Slice values", False
    elif chart_type == "scatter":
        x_label, y_label, multi = "X axis", "Y axis (one or more)", True
    else:  # cartesian
        x_label, y_label, multi = "Category (X) axis", "Series (Y) — one or more", True

    x_col = st.selectbox(x_label, df.columns)

    if multi:
        # Pills keep every series choice inline and compact, but the reference
        # bounds them at ~5 options: a wide uploaded CSV can have many numeric
        # columns, which would wrap the pills into several rows in the narrow
        # sidebar. Past that threshold fall back to st.multiselect (a dropdown).
        # Either way the empty-set guard in the main panel handles a cleared
        # selection. (st.multiselect is inherently multi, so it takes no
        # selection_mode — hence the two separate calls.)
        if len(numeric_cols) <= 5:
            y_cols = st.pills(
                y_label, numeric_cols, selection_mode="multi", default=numeric_cols[:1]
            )
        else:
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
# At-a-glance summary of the active data + config, above the two cards.
# st.container(horizontal=True) is the reference's KPI-row pattern (wraps on small
# screens; preferred over st.columns for metric rows). "Series plotted" reads 0
# before the empty-selection guard fires below — a useful empty state, not a blank.
with st.container(horizontal=True):
    st.metric("Rows", f"{len(df):,}", border=True)
    st.metric("Numeric columns", len(numeric_cols), border=True)
    st.metric("Series plotted", len(y_cols), border=True)
    st.metric("Chart type", chart_type.title(), border=True)

left, right = st.columns([3, 2], gap="large")

with right.container(border=True, height="stretch"):
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

with left.container(border=True, height="stretch"):
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
                df, chart_type, x_col, tuple(y_cols), height, title, dark
            )
        except Exception as exc:  # build error or export-server failure
            st.error(
                f"Static (PNG) render failed.\n\n`{type(exc).__name__}: {exc}`\n\n"
                "This usually means the Highcharts export server is unreachable — "
                "check your network, or switch to the **Interactive** mode instead.",
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
            df, chart_type, x_col, tuple(y_cols), height, title, dark
        )
        # The HTML is embedded in a sandboxed iframe with a FIXED height — it
        # does not auto-grow to its content, so size it to the chart.
        st.iframe(html, height=height + 24)
        st.caption(
            "Interactive chart — Highcharts JS is loaded from the CDN in the browser."
        )

    # Gate the generated-config panel behind a toggle so cached_chart_js only
    # builds (and re-hashes df) when the user actually asks for it. A plain
    # st.expander renders its body on every rerun even while collapsed (Streamlit
    # only hides it client-side), so the JS would be rebuilt on every slider or
    # title change for a panel that's closed by default. An expander with
    # on_change="rerun" + `.open` would also skip that work, but AppTest can't
    # open it — so the toggle (the performance reference's alternative) keeps the
    # config both cheap and observable to the headless tests.
    if st.toggle(":material/code: Show the generated Highcharts config (JavaScript)"):
        chart_js = cached_chart_js(df, chart_type, x_col, tuple(y_cols), title, dark)
        st.code(chart_js, language="javascript")
