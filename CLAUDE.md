# CLAUDE.md

## Project Overview

`streamlit-highcharts` is an interactive Streamlit app that builds Highcharts
visualizations from pandas DataFrames. Every chart is produced by the Highcharts
for Python toolkit (`highcharts-core`) — the app uses no native Streamlit charts.

## Structure

- `streamlit_app.py` — the Streamlit UI: data source (sample datasets or CSV
  upload), chart-type/column controls, caching, render-mode toggle, and the
  chart embed.
- `highcharts_builder.py` — pure, Streamlit-free helpers that turn a DataFrame
  into a Highcharts options `dict`, a `Chart`, and embeddable HTML or PNG bytes.
  Independently importable and unit-testable.
- `tests/test_smoke.py` — builder unit tests (parametrized over every chart
  type, with the missing-data and scatter edge cases and the validation guards)
  plus headless `AppTest` interaction tests for the app.

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

`tests/test_smoke.py` exercises the pure builder (`build_options`) —
parametrized across every supported chart type, covering missing data
(`EnforcedNull` for cartesian series, dropped points/slices elsewhere), the
numeric vs non-numeric scatter paths, and the validation guards — and drives the
full app headless via Streamlit's `AppTest`, switching controls and asserting on
the generated Highcharts config and the guard warnings.

## Lint & format

Ruff handles both (config in `pyproject.toml`). CI runs the tests and these
checks on every push and PR; `pre-commit` runs them on commit when installed.

```bash
uv run ruff check --fix . && uv run ruff format .   # fix + format
uv run ruff check . && uv run ruff format --check .  # verify (as CI does)
```

## Type check

[ty](https://docs.astral.sh/ty/) (Astral's type checker, pinned in
`pyproject.toml`) runs in CI and on commit via `pre-commit`. It needs the
project venv to resolve imports, so run it through `uv run`:

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
  in dict configs, not Python `None`.
