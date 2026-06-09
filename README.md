# Highcharts for Python — Data Visualizations

Generate data visualizations with the
[Highcharts for Python](https://github.com/highcharts-for-python) toolkit. This
repo is an interactive [Streamlit](https://streamlit.io) app that builds them
from pandas DataFrames — **every chart is produced by `highcharts-core`**, with
no native Streamlit charts.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync
```

## Run

```bash
uv run streamlit run streamlit_app.py
```

Then open <http://localhost:8501>. Pick a sample dataset (or upload a CSV),
choose a chart type and columns, and toggle between an interactive (CDN) chart
and a static PNG render.

## What it does

- Turns a `pandas.DataFrame` into a Highcharts options `dict`, then a `Chart`
  via `Chart.from_options(...)`.
- Two render modes via the **"Static image (PNG)"** toggle:
  - **Interactive** (default): serialize the chart with its own
    `get_script_tags()` (Highcharts CDN `<script>` tags) + `to_js_literal()`,
    wrap it in a small HTML document, and embed it with `st.iframe`. Highcharts
    JS runs in the browser.
  - **Static**: render server-side with `chart.download_chart(format="png")`
    and show the PNG with `st.image` (plus a download button). No Highcharts JS
    runs in the browser; the process talks to the Highcharts export server.
- Supported chart types: `line`, `spline`, `area`, `column`, `bar`, `pie`,
  `scatter`.

## Files

| File | Purpose |
| --- | --- |
| `streamlit_app.py` | The Streamlit UI: data source, chart controls, caching, render-mode toggle, and the chart embed. |
| `highcharts_builder.py` | Pure (Streamlit-free) functions that turn a DataFrame into a Highcharts options dict, a `Chart`, and embeddable HTML / PNG bytes. Independently importable and unit-testable. |

## Test

```bash
uv run pytest
```

## Lint & format

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and
formatting (config in `pyproject.toml`).

```bash
# Auto-fix lint issues and format (run before committing):
uv run ruff check --fix . && uv run ruff format .

# Verify only, exactly as CI does (non-mutating):
uv run ruff check . && uv run ruff format --check .
```

Optional: install the [pre-commit](https://pre-commit.com/) hooks so this runs
automatically on every commit:

```bash
uv tool install pre-commit && pre-commit install
```

VS Code users get format-on-save and fix-on-save via the committed
`.vscode/settings.json` (install the recommended Ruff extension).

## CI

GitHub Actions runs the tests and the Ruff lint/format checks on every push to
`main` and every pull request (`.github/workflows/ci.yml`).

## Notes

- There is **no official `streamlit-highcharts` integration** for the
  `highcharts-core` object model, so this app uses the dependency-free
  `Chart` → HTML → `st.iframe` bridge.
- In **interactive** mode, charts load Highcharts JS from the CDN
  (`https://code.highcharts.com/`), so the browser needs network access. The
  iframe has a fixed height (it does not auto-grow).
- In **static** mode, the running process must reach the Highcharts export
  server (`export.highcharts.com` by default). To remove that external
  dependency, self-host an export server and pass a `server_instance` to
  `download_chart`.

## Dependencies

Runtime:

- `highcharts-core` — Highcharts for Python charting library
- `pandas` — DataFrames feeding the charts
- `streamlit` — app runtime

Dev (in the `dev` dependency group, installed by `uv sync`):

- `pytest` — tests
- `ruff` — linter and formatter
- `watchdog` — faster, more reliable Streamlit hot-reload

## License

No license is granted for this project — all rights reserved. With no license,
the default of copyright law applies: you may view the code here, but you may
not use, copy, modify, or distribute it without the author's permission.
Rendering relies on Highcharts JS (loaded from the CDN) and the Highcharts
export server, which are subject to Highcharts' own licensing — free for
non-commercial use; commercial use requires a Highcharts license.
