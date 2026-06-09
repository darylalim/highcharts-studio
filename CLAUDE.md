# CLAUDE.md

## Project Overview

Generate data visualizations with the Highcharts for Python toolkit
(`highcharts-core`). This repo is an interactive Streamlit app that builds those
visualizations from pandas DataFrames; every chart is produced by Highcharts —
the app uses no native Streamlit charts.

## Structure

- `streamlit_app.py` — the Streamlit UI: data source (sample datasets or CSV
  upload), chart-type/column controls, caching, render-mode toggle, and the
  chart embed.
- `highcharts_builder.py` — pure, Streamlit-free helpers that turn a DataFrame
  into a Highcharts options `dict`, a `Chart`, and embeddable HTML or PNG bytes.
  Independently importable and unit-testable.
- `tests/test_smoke.py` — builder unit tests plus a headless `AppTest` run.

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

Supported chart types: `line`, `spline`, `area`, `column`, `bar`, `pie`,
`scatter`.

## Run

```bash
uv run streamlit run streamlit_app.py
```

## Test

```bash
uv run pytest
```

`tests/test_smoke.py` exercises the pure builder (`build_options`) and runs the
full app headless via Streamlit's `AppTest`.

## Lint & format

Ruff handles both (config in `pyproject.toml`). CI runs the tests and these
checks on every push and PR; `pre-commit` runs them on commit when installed.

```bash
uv run ruff check --fix . && uv run ruff format .   # fix + format
uv run ruff check . && uv run ruff format --check .  # verify (as CI does)
```

## Conventions

- Keep chart-building logic (DataFrame → Highcharts) in `highcharts_builder.py`,
  free of Streamlit imports, so it stays unit-testable.
- Render every visualization with Highcharts (`highcharts-core`); do not use
  native Streamlit charts.
- Use `EnforcedNull` (from `highcharts_core.constants`) for missing data points
  in dict configs, not Python `None`.
