# highcharts-studio

An interactive [Streamlit](https://streamlit.io) app that builds visualizations
from pandas DataFrames with the
[Highcharts for Python](https://github.com/highcharts-for-python) toolkit —
**every chart is produced by `highcharts-core`**, with no native Streamlit charts.

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
choose a chart type and columns, and switch between three render modes:
interactive (CDN iframe), interactive with click events, or a static PNG.

## What it does

- Turns a `pandas.DataFrame` into a Highcharts options `dict`, then a `Chart`
  via `Chart.from_options(...)`. Series share a brand palette (`DEFAULT_COLORS`)
  that matches the Streamlit theme in `.streamlit/config.toml`.
- Three render modes, chosen from the sidebar **Render** selector:
  - **Interactive** (default): serialize the chart with its own
    `get_script_tags()` (Highcharts CDN `<script>` tags) + `to_js_literal()`,
    wrap it in a small HTML document, and embed it with `st.iframe`. Highcharts
    JS runs in the browser.
  - **Interactive + click events**: render the chart as a bidirectional
    [Custom Component v2](https://docs.streamlit.io/develop/api-reference/custom-components/st.components.v2.component) —
    clicked points flow back to Python (highlighting the matching data row), and
    the chart re-reads the live Streamlit theme. Requires Streamlit ≥ 1.57.
  - **Static (PNG)**: render server-side with `chart.download_chart(format="png")`
    and show the PNG with `st.image` (plus a download button). No Highcharts JS
    runs in the browser; the process talks to the Highcharts export server.
- Supported chart types: `line`, `spline`, `area`, `column`, `bar`, `pie`,
  `scatter`.

## Files

| File | Purpose |
| --- | --- |
| `streamlit_app.py` | The Streamlit UI: data source, chart controls, caching, the render-mode selector (interactive / click events / static PNG), and the chart embed. |
| `highcharts_builder.py` | Pure (Streamlit-free) functions that turn a DataFrame into a Highcharts options dict, a `Chart`, and embeddable HTML / PNG bytes. Independently importable and unit-testable. |
| `highcharts_component.py` | Streamlit Custom Component v2 wrapper for the click-events mode: reuses `build_options`, renders Highcharts client-side, and sends point clicks back to Python. |
| `sample_data.py` | Pure (Streamlit-free) built-in sample datasets offered when no CSV is uploaded. |
| `.streamlit/config.toml` | Streamlit theme (app shell) and dev settings (`runOnSave`). |
| `tests/test_smoke.py` | Builder, component, and sample-data unit tests plus headless `AppTest` interaction tests (including the click round-trip). |

## Test

```bash
uv run pytest
```

`tests/test_smoke.py` covers the builder across every chart type (parametrized),
the missing-data and scatter edge cases, the brand palette, and the validation
guards; the component helpers (`json_safe`, `_read_state_value`, `point_label`)
and the sample datasets; then drives the full app headless with Streamlit's
`AppTest` — switching controls, the click round-trip, and the guard messages.

## Lint & format

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and
formatting (config in `pyproject.toml`).

```bash
# Auto-fix lint issues and format (run before committing):
uv run ruff check --fix . && uv run ruff format .

# Verify only, exactly as CI does (non-mutating):
uv run ruff check . && uv run ruff format --check .
```

## Type check

This project uses [ty](https://docs.astral.sh/ty/), Astral's fast Python type
checker. Because ty resolves third-party imports from the project venv, run it
through `uv run`:

```bash
uv run ty check
```

It runs in CI. A few `highcharts-core` stub mismatches are suppressed inline
with `# ty: ignore[rule]` (so the rules still apply everywhere else); see
`CLAUDE.md` for details.

## CI

GitHub Actions runs the tests, the Ruff lint/format checks, and the ty type
check on every push to `main` and every pull request
(`.github/workflows/ci.yml`).

## Notes

- There is **no official Streamlit ↔ Highcharts component** (no `st.highcharts`
  widget) for the `highcharts-core` object model, so the default interactive
  mode uses a dependency-free `Chart` → HTML → `st.iframe` bridge, and the
  click-events mode uses a small inline `st.components.v2` component.
- In the **interactive** modes, charts load Highcharts JS from the CDN
  (`https://code.highcharts.com/`), so the browser needs network access. The
  iframe (default mode) has a fixed height (it does not auto-grow).
- In **static** mode, the running process must reach the Highcharts export
  server (`export.highcharts.com` by default). To remove that external
  dependency, self-host an export server and pass a `server_instance` to
  `download_chart`.

## Dependencies

Runtime:

- `highcharts-core` — Highcharts for Python charting library
- `pandas` — DataFrames feeding the charts
- `streamlit` — app runtime (≥ 1.57 for the click-events Custom Component v2)

Dev (in the `dev` dependency group, installed by `uv sync`):

- `pytest` — tests
- `ruff` — linter and formatter
- `ty` — type checker
- `watchdog` — faster, more reliable Streamlit hot-reload

## License

No license is granted for this project — all rights reserved. With no license,
the default of copyright law applies: you may view the code here, but you may
not use, copy, modify, or distribute it without the author's permission.
Rendering relies on Highcharts JS (loaded from the CDN) and the Highcharts
export server, which are subject to Highcharts' own licensing — free for
non-commercial use; commercial use requires a Highcharts license.
