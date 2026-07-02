# CLAUDE.md

## Project Overview

`highcharts-studio` is an interactive Streamlit app that builds Highcharts
visualizations from pandas DataFrames. Every chart is produced by the Highcharts
for Python toolkit (`highcharts-core`) — the app uses no native Streamlit charts.

## Structure

- `streamlit_app.py` — the Streamlit UI: data source (sample datasets or CSV
  upload), chart-type/column controls, caching, the render-mode selector
  (interactive iframe / interactive click-events / static PNG), and the chart
  embed.
- `highcharts_builder.py` — pure, Streamlit-free helpers that turn a DataFrame
  into a Highcharts options `dict`, a `Chart`, and embeddable HTML or PNG bytes.
  Independently importable and unit-testable.
- `highcharts_component.py` — Streamlit-importing wrapper that renders the chart
  as a bidirectional Custom Component v2 (CCv2): it reuses `build_options` and
  feeds it (via `json_safe`) to a client-side Highcharts instance that sends
  point clicks back to Python. Powers the "Interactive + click events" mode and
  owns all `hc_*` click-events session state. Public helpers: `interactive_chart`,
  `get_selected_point`, `clear_selected_point`, `forget_selection_if_config_changed`,
  `point_label`, `matching_rows`, `json_safe`.
- `sample_data.py` — pure (Streamlit-free) built-in sample datasets and the
  `SAMPLES` registry the app offers when no CSV is uploaded.
- `tests/test_smoke.py` — builder unit tests (every chart type, the missing-data
  and scatter edge cases, the brand palette, and the validation guards),
  component and `sample_data` unit tests (`json_safe`, `_read_state_value`,
  `point_label`), plus headless `AppTest` interaction tests (including the click
  round-trip and stale-selection clearing).
- `.streamlit/config.toml` — project Streamlit theme (brands the app shell). The
  chart colors are themed separately (see Conventions) since charts render in an
  iframe/component the shell theme can't reach.

## How a chart is built

`highcharts_builder.py` exposes the public helpers the app uses:

```python
# build_options() -> Chart.from_options() -> set container, in one call:
chart = make_chart(df, chart_type, x_col, y_cols, title=title)

# interactive: get_script_tags() + to_js_literal() wrapped as HTML for st.iframe
html = build_chart_html(df, chart_type, x_col, y_cols, height=height, title=title)

# static: rendered server-side to PNG bytes via the export server, for st.image
png = build_chart_png(df, chart_type, x_col, y_cols, title=title)
```

The click-events mode instead mounts the chart through
`highcharts_component.interactive_chart(...)`, which reuses `build_options` and
renders Highcharts client-side as a bidirectional Custom Component v2.

Supported chart types: `line`, `spline`, `area`, `column`, `bar`, `pie`,
`scatter`.

## Run

```bash
uv run streamlit run streamlit_app.py
```

`.streamlit/config.toml` themes the shell and enables `runOnSave`, so saves
auto-rerun. When a stale chart or an export-server failure is suspected, flush
the four `@st.cache_data` renderers with `uv run streamlit cache clear`; verify
config with `uv run streamlit config show`.

## Test

```bash
uv run pytest
```

`tests/test_smoke.py` exercises the pure builder (`build_options`) —
parametrized across every supported chart type, covering missing data
(`EnforcedNull` for cartesian series, dropped points/slices elsewhere), the
numeric vs non-numeric scatter paths, the brand palette, and the validation
guards — plus the component helpers (`json_safe`, `_read_state_value`,
`point_label`) and the sample datasets, then drives the full app headless via
Streamlit's `AppTest` (switching controls, the click round-trip and
stale-selection clearing, and the guard messages).

## Lint & format

Ruff handles both (config in `pyproject.toml`). CI runs the tests and these
checks on every push to `main` and every PR.

```bash
uv run ruff check --fix . && uv run ruff format .   # fix + format
uv run ruff check . && uv run ruff format --check .  # verify (as CI does)
```

## Type check

[ty](https://docs.astral.sh/ty/) (Astral's type checker, pinned in
`pyproject.toml`) runs in CI. It needs the project venv to resolve imports, so
run it through `uv run`:

```bash
uv run ty check
```

A few highcharts-core stub mismatches (Optional `options`/`chart`,
`to_js_literal` typed `str | None`) are suppressed inline with
`# ty: ignore[rule]`, not by downgrading rules globally — so the rules still
catch the same problems in our own code.

## Conventions

- Keep chart-building logic (DataFrame → Highcharts) in `highcharts_builder.py`,
  free of Streamlit imports, so it stays unit-testable.
- Render every visualization with Highcharts (`highcharts-core`); do not use
  native Streamlit charts.
- Use `EnforcedNull` (from `highcharts_core.constants`) for missing data points
  in dict configs fed to highcharts-core (`Chart.from_options`), not Python
  `None`. The one sanctioned exception is the CCv2 JSON `data` path:
  `highcharts_component.json_safe` rewrites `EnforcedNull` to JSON `null`
  (`None`) before the options are handed to Highcharts in the browser.
- Theme charts via `highcharts_builder.DEFAULT_COLORS` (applied by
  `build_options` to every chart, so the iframe and PNG paths are themed too),
  keeping its first color in sync with `primaryColor` in `.streamlit/config.toml`.
  The interactive CCv2 chart additionally re-reads the live `--st-*` theme
  variables in the browser so it tracks light/dark switches.
