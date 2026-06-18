"""Interactive Highcharts as a Streamlit Custom Component v2 (CCv2).

Where ``highcharts_builder.build_chart_html`` produces a one-way ``st.iframe``
embed (Python -> browser, no way back), this renders Highcharts as a
*bidirectional* CCv2 component: the same options ``dict`` from
``build_options`` is passed down as JSON ``data`` and rendered client-side, and
point-click events are sent back to Python via ``setTriggerValue`` so the app
can react to them.

This module imports Streamlit, so it lives here rather than in the
Streamlit-free ``highcharts_builder`` — but it reuses ``build_options``
unchanged, keeping all DataFrame -> Highcharts logic in one tested place.

CCv2 only: the frontend uses ``export default function(component)`` and the
``setStateValue`` / ``setTriggerValue`` callbacks. No v1 globals
(``window.Streamlit``, ``setComponentValue``, ``setFrameHeight``).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v2 as components_v2
from highcharts_core.constants import EnforcedNull
from streamlit.components.v2.get_bidi_component_manager import (
    get_bidi_component_manager,
)

from highcharts_builder import build_options

# Session-state keys: the component's own mounted-instance state, the key where
# we persist the most recent click for the rest of the app, and the last chart
# configuration we saw (used to drop a stale selection when the chart changes).
COMPONENT_KEY = "hc_interactive"
SELECTION_KEY = "hc_selected_point"
CONFIG_SIG_KEY = "hc_config_sig"


def point_label(point: dict):
    """First present identifier of a clicked point: category, then name, then x.

    Uses ``is not None`` (not truthiness) so a legitimate ``x == 0`` — the first
    index of a series — is honored rather than skipped as falsy.
    """
    for field in ("category", "name", "x"):
        value = point.get(field)
        if value is not None:
            return value
    return None


def matching_rows(df: pd.DataFrame, x_col, label) -> pd.DataFrame:
    """Rows of ``df`` whose ``x_col`` equals a clicked point's ``label``.

    A numeric x column is matched numerically: a numeric-x scatter sends the raw
    x value (e.g. ``152.0``), which JS stringifies as ``"152"`` while a float64
    column's ``astype(str)`` is ``"152.0"`` — a string compare would never match.
    Categorical/label x columns (cartesian categories, pie names) match by string.
    """
    if pd.api.types.is_numeric_dtype(df[x_col]):
        try:
            return df[df[x_col] == float(label)]
        except (TypeError, ValueError):
            return df.iloc[0:0]  # non-numeric label against a numeric column
    return df[df[x_col].astype(str) == str(label)]


def json_safe(obj):
    """Recursively replace ``EnforcedNull`` sentinels with ``None``.

    ``build_options`` uses ``EnforcedNull`` for missing cartesian points so the
    highcharts-core path (``Chart.from_options`` -> ``to_js_literal``) emits JS
    ``null``. That sentinel is **not** JSON-serializable, and the CCv2 ``data``
    payload is plain JSON handed straight to Highcharts JS — where ``null`` is
    exactly the right gap marker. So this conversion is the JSON-path analogue of
    the builder's ``EnforcedNull`` rule, not a violation of it.
    """
    if obj is EnforcedNull:
        return None
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(v) for v in obj]
    return obj


# Frontend: load Highcharts from the CDN once (a global <script>, so the lib is
# shared across reruns/instances), render into a *child* of parentElement (never
# clobber it), wire point clicks back to Python, and destroy the chart on
# unmount. Inline JS must be multi-line so CCv2 treats it as code, not a path.
_JS = """\
let _hcPromise;
function loadHighcharts() {
  if (window.Highcharts) return Promise.resolve(window.Highcharts);
  if (!_hcPromise) {
    _hcPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://code.highcharts.com/highcharts.js";
      s.onload = () => resolve(window.Highcharts);
      s.onerror = () => reject(new Error("Failed to load Highcharts from the CDN"));
      document.head.appendChild(s);
    });
  }
  return _hcPromise;
}

// One live chart per mounted instance, keyed by its host element.
const _charts = new WeakMap();

export default function (component) {
  const { parentElement, data, setTriggerValue } = component;

  // Render into our own child div; do not overwrite parentElement's contents.
  let host = parentElement.querySelector("#hc-host");
  if (!host) {
    host = document.createElement("div");
    host.id = "hc-host";
    parentElement.appendChild(host);
  }
  host.style.width = "100%";
  host.style.height = ((data && data.height) || 480) + "px";

  loadHighcharts().then((Highcharts) => {
    const options = structuredClone((data && data.options) || {});

    // Theme the chart live from Streamlit's --st-* variables (set on the shadow
    // host), so the interactive chart tracks the app's light/dark/custom theme.
    // Each is optional — fall back to whatever options already carry.
    const themeHost = parentElement.host || parentElement;
    const cssVar = (name) => getComputedStyle(themeHost).getPropertyValue(name).trim();
    const palette = cssVar("--st-chart-categorical-colors");
    if (palette) options.colors = palette.split(",").map((c) => c.trim());
    const textColor = cssVar("--st-text-color");
    const fontFamily = cssVar("--st-font");
    if (textColor || fontFamily) {
      options.chart = options.chart || {};
      options.chart.style = Object.assign(
        {},
        options.chart.style,
        fontFamily ? { fontFamily } : {},
        textColor ? { color: textColor } : {},
      );
    }

    // JS -> Python: send the clicked point as a transient trigger.
    options.plotOptions = options.plotOptions || {};
    options.plotOptions.series = Object.assign({}, options.plotOptions.series, {
      cursor: "pointer",
      point: {
        events: {
          click: function () {
            setTriggerValue("point_click", {
              series: this.series && this.series.name,
              name: this.name,
              category: this.category,
              x: this.x,
              y: this.y,
            });
          },
        },
      },
    });

    const prev = _charts.get(host);
    if (prev) prev.destroy();
    _charts.set(host, Highcharts.chart(host, options));
  });

  // Cleanup when Streamlit unmounts this instance.
  return () => {
    const chart = _charts.get(host);
    if (chart) {
      chart.destroy();
      _charts.delete(host);
    }
  };
}
"""

# isolate_styles stays at its default (True): the component renders in a shadow
# root so its styles can't leak into the app. Highcharts renders there given the
# explicit host dimensions above; flip to isolate_styles=False only if a future
# Highcharts feature needs light-DOM measurement.
_COMPONENT_NAME = "highcharts_interactive"
_HTML = '<div id="hc-root"></div>'

# The mount callable, cached after the first registration in this process.
_mount = None


def _component():
    """Return the component's mount callable, registering it on first use.

    The CCv2 registry is **runtime-scoped** (``Runtime.instance()``), not
    per-rerun, so registering at module-import time only works when the import
    happens under a live runtime — and is silently lost otherwise (e.g. when the
    module is imported before the runtime exists, as under pytest/``AppTest``).
    Registering lazily and idempotently instead is robust everywhere: we
    (re)register only when the active runtime's registry lacks the component, so
    it happens once per runtime — never per call — and never logs a
    duplicate-registration warning.
    """
    global _mount
    if _mount is None or get_bidi_component_manager().get(_COMPONENT_NAME) is None:
        _mount = components_v2.component(_COMPONENT_NAME, html=_HTML, js=_JS)
    return _mount


def _read_state_value(state, name):
    """Read a state/trigger value from a mounted instance's session-state entry.

    Streamlit stores it as a dict-like object, but guard for attribute-style
    access too so a future Streamlit shape change doesn't silently break clicks.
    """
    if state is None:
        return None
    if hasattr(state, "get"):
        return state.get(name)
    return getattr(state, name, None)


def _store_click() -> None:
    """``on_point_click_change`` callback: persist the latest click.

    Callbacks run *before* the script body reruns, so writing the selection here
    (rather than after the mount returns) lets widgets above the chart in source
    order — e.g. the source-data table — reflect the click in the same rerun.
    """
    payload = _read_state_value(st.session_state.get(COMPONENT_KEY), "point_click")
    if payload:
        st.session_state[SELECTION_KEY] = payload


def interactive_chart(
    df,
    chart_type,
    x_col,
    y_cols,
    *,
    height: int = 480,
    title: str | None = None,
):
    """Mount the interactive Highcharts CCv2 component for the given columns.

    Reuses ``build_options`` (JSON-sanitized via ``json_safe``) for the chart
    config. Clicks are persisted to ``st.session_state`` — read them with
    ``get_selected_point()``.
    """
    options = json_safe(build_options(df, chart_type, x_col, list(y_cols), title=title))
    return _component()(
        key=COMPONENT_KEY,
        data={"options": options, "height": height},
        height=height + 8,
        on_point_click_change=_store_click,
    )


def get_selected_point() -> dict | None:
    """Return the most recently clicked point payload, or ``None``."""
    return st.session_state.get(SELECTION_KEY)


def clear_selected_point() -> None:
    """Forget the current click selection."""
    st.session_state.pop(SELECTION_KEY, None)


def forget_selection_if_config_changed(chart_type, x_col, y_cols) -> None:
    """Drop the click selection when the chart configuration changes.

    Keeps a stale point from a previous chart out of the click-events panels.
    Doesn't clear on the first observation (no prior signature) — only when a
    known signature actually changes.
    """
    signature = (chart_type, x_col, tuple(y_cols))
    previous = st.session_state.get(CONFIG_SIG_KEY)
    if previous is not None and previous != signature:
        clear_selected_point()
    st.session_state[CONFIG_SIG_KEY] = signature
