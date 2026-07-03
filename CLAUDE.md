# CLAUDE.md

## Project Overview

`highcharts-studio` is a Streamlit application for building data visualizations
with Highcharts. Every chart is produced by the Highcharts for Python toolkit
(`highcharts-core`) — the app uses no native Streamlit charts.

## Structure

- `streamlit_app.py` — the Streamlit UI: data source (sample datasets or CSV
  upload), chart-type/column controls (pills for the Y series, falling back to
  `st.multiselect` on wide CSVs), caching, a KPI metric row, the render-mode
  selector (interactive iframe / static PNG), reading the active light/dark theme
  (`st.context.theme.type`) so the charts render theme-aware, the chart embed,
  and a toggle that reveals the generated Highcharts config (JS).
- `highcharts_builder.py` — pure, Streamlit-free helpers that turn a DataFrame
  into a Highcharts options `dict`, a `Chart`, and embeddable HTML or PNG bytes.
  Independently importable and unit-testable.
- `sample_data.py` — pure (Streamlit-free) built-in sample datasets and the
  `SAMPLES` registry the app offers when no CSV is uploaded.
- `tests/test_smoke.py` — builder unit tests (every chart type, the missing-data
  and scatter edge cases, the brand palette, and the validation guards) and
  `sample_data` unit tests, plus headless `AppTest` interaction tests.
- `.streamlit/config.toml` — project Streamlit theme (brands the app shell in
  both light and dark via `[theme.light]`/`[theme.dark]`, which unlocks the
  in-app light/dark toggle). The chart colors are themed separately (see
  Conventions) since charts render in an iframe the shell theme can't reach.

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

All three helpers take an optional `dark=` flag (default `False`) that themes the
chart chrome (background/text/axes/gridlines/tooltip) for dark mode; the app
derives it from `st.context.theme.type` and threads it through the cached
renderers.

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
numeric vs non-numeric scatter paths, the brand palette, the light/dark theming
(dark-mode chrome — including the tooltip — vs. the shared palette), and the
validation guards — plus the sample datasets, then drives the full app headless
via Streamlit's `AppTest` (switching controls, revealing the generated config
behind its toggle, the KPI metric row, the wide-CSV `st.multiselect` fallback,
the render-mode selector's two modes, and asserting the guard messages).

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

- When working with Python, invoke the relevant Astral skill (`/astral:uv`,
  `/astral:ty`, `/astral:ruff`) for uv, ty, and ruff to ensure best practices
  are followed.
- Keep chart-building logic (DataFrame → Highcharts) in `highcharts_builder.py`,
  free of Streamlit imports, so it stays unit-testable.
- Render every visualization with Highcharts (`highcharts-core`); do not use
  native Streamlit charts.
- Use `EnforcedNull` (from `highcharts_core.constants`) for missing data points
  in dict configs fed to highcharts-core (`Chart.from_options`), not Python
  `None`.
- Theme charts via `highcharts_builder.DEFAULT_COLORS` (applied by
  `build_options` to every chart, so the iframe and PNG paths are themed too),
  keeping its first color in sync with the light-mode `primaryColor` in
  `.streamlit/config.toml`. The palette is shared across light/dark; only the
  chart chrome (background/text/axes/gridlines/tooltip) flips, via
  `build_options(..., dark=...)` / `_DARK_CHROME`. `streamlit_app.py` reads `dark` from
  `st.context.theme.type` and threads it through the cached renderers (so it's
  part of their cache key).
