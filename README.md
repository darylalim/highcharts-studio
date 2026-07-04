# highcharts-studio

A [Streamlit](https://streamlit.io) application for building data visualizations
with [Highcharts](https://github.com/highcharts-for-python) — **every chart is
produced by `highcharts-core`** (the Highcharts for Python toolkit), with no
native Streamlit charts.

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
choose a chart type and columns, and switch between two render modes:
interactive (CDN iframe) or a static PNG. The charts follow the app's
light/dark theme, which you can toggle from the settings menu.

## What it does

- Turns a `pandas.DataFrame` into a Highcharts options `dict`, then a `Chart`
  via `Chart.from_options(...)`. Series share a brand palette (`DEFAULT_COLORS`)
  that matches the Streamlit theme in `.streamlit/config.toml`.
- Two render modes, chosen from the sidebar **Render** selector:
  - **Interactive** (default): serialize the chart with its own
    `get_script_tags()` (Highcharts CDN `<script>` tags) + `to_js_literal()`,
    wrap it in a small HTML document, and embed it with `st.iframe`. Highcharts
    JS runs in the browser.
  - **Static (PNG)**: render server-side with `chart.download_chart(format="png")`
    and show the PNG with `st.image` (plus a download button). No Highcharts JS
    runs in the browser; the process talks to the Highcharts export server.
- Light and dark themes, toggled from Streamlit's settings menu (it follows your
  OS by default). The charts are theme-aware in both render modes: their
  background, text, axes, and tooltip flip to match the mode, while each series
  keeps its palette color.
- An at-a-glance KPI row (rows, numeric columns, series plotted, chart type)
  above the chart, a side-by-side source-data preview, and a toggle that reveals
  the generated Highcharts config (the `to_js_literal()` output). The Y-series
  picker uses compact pills, falling back to `st.multiselect` for wide CSVs.
- Supported chart types: `line`, `spline`, `area`, `column`, `bar`, `pie`,
  `scatter`.

## Files

| File | Purpose |
| --- | --- |
| `streamlit_app.py` | The Streamlit UI: data source, chart controls, caching, a KPI metric row, the render-mode selector (interactive / static PNG), the chart embed, and a toggle for the generated config. |
| `highcharts_builder.py` | Pure (Streamlit-free) functions that turn a DataFrame into a Highcharts options dict, a `Chart`, and embeddable HTML / PNG bytes. Independently importable and unit-testable. |
| `sample_data.py` | Pure (Streamlit-free) built-in sample datasets offered when no CSV is uploaded. |
| `.streamlit/config.toml` | Streamlit light/dark themes (app shell) and dev settings (`runOnSave`). |
| `pyproject.toml` | Dependencies + the `dev` group and the Ruff / ty config. |
| `tests/test_smoke.py` | Builder and sample-data unit tests plus headless `AppTest` interaction tests. |
| `tests/test_hooks.py` | Unit tests for the Claude Code hook scripts (pure decision functions + exit-code contract). |
| `tests/test_packaging.py` | Unit tests guarding the licensing metadata (pyproject `license` fields, the `LICENSE` file, and the `NOTICE` third-party notice) against drift. |
| `.claude/settings.json`, `.claude/hooks/` | Committed Claude Code hooks that mirror the CI gates (see Claude Code hooks below). |
| `.github/workflows/ci.yml` | GitHub Actions: pytest, Ruff lint/format, and ty on every push to `main` and every PR. |
| `LICENSE` | MIT license for this project's own code (kept pristine so GitHub detects it as MIT). |
| `NOTICE` | Third-party notice for the proprietary Highcharts JS / export server and `highcharts-core` dependencies, split out of `LICENSE`. |

## Test

```bash
uv run pytest
```

`tests/test_smoke.py` covers the builder across every chart type (parametrized),
the missing-data and scatter edge cases, the brand palette, the light/dark
theming (including the dark-mode tooltip), and the validation guards, plus the
sample datasets; then drives the full app headless with Streamlit's `AppTest` —
switching controls, revealing the generated config behind its toggle, the KPI
metric row, the wide-CSV `st.multiselect` fallback, the render-mode selector's
two modes, and asserting the guard messages. `tests/test_hooks.py` adds unit
coverage for the `.claude/hooks/` scripts (see Claude Code hooks below), and
`tests/test_packaging.py` guards the licensing metadata — the `pyproject.toml`
`license` fields, the `LICENSE` file, and the `NOTICE` third-party notice —
against drift.

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

## Claude Code hooks

`.claude/settings.json` and `.claude/hooks/` ship
[Claude Code](https://claude.com/claude-code) hooks (committed; the per-developer
`.claude/settings.local.json` is gitignored) that mirror the CI gates locally, so
edits stay green before a push:

- **`post_edit_py.py`** (PostToolUse) — on a `.py` edit, runs `ruff check --fix`
  + `ruff format`, then `ty check`.
- **`pytest_stop.py`** (Stop) — runs `pytest` when the tree has uncommitted `.py`
  changes, with a loop guard so it can't run forever.
- **`guard_paths.py`** (PreToolUse) — blocks direct edits to `uv.lock`,
  `.streamlit/secrets.toml`, and `.git/` internals.

They only affect contributors using Claude Code; the app and CI don't depend on
them. See `CLAUDE.md` for details.

## Notes

- There is **no official Streamlit ↔ Highcharts component** (no `st.highcharts`
  widget) for the `highcharts-core` object model, so the interactive mode uses a
  dependency-free `Chart` → HTML → `st.iframe` bridge.
- In the **interactive** mode, the chart loads Highcharts JS from the CDN
  (`https://code.highcharts.com/`), so the browser needs network access. The
  iframe has a fixed height (it does not auto-grow).
- In **static** mode, the running process must reach the Highcharts export
  server (`export.highcharts.com` by default). To remove that external
  dependency, self-host an export server and pass a `server_instance` to
  `download_chart`.

## Dependencies

Runtime:

- `highcharts-core` — Highcharts for Python charting library (proprietary; see the License section)
- `pandas` — DataFrames feeding the charts
- `streamlit` — app runtime (pinned ≥ 1.57, the version this app is built and CI-tested against)

Dev (in the `dev` dependency group, installed by `uv sync`):

- `pytest` — tests
- `ruff` — linter and formatter
- `ty` — type checker
- `watchdog` — faster, more reliable Streamlit hot-reload

## License

This project's own source code (the Streamlit app and its helpers) is released
under the [MIT License](LICENSE) — you're free to use, modify, and distribute
it.

The MIT license covers **only this project's code**, not the third-party tools
it renders with. Two of its dependencies are proprietary and separately
licensed, and the MIT grant does not extend to them:

- **Highcharts JS** (loaded from the CDN) and the **Highcharts export server**
  are owned by Highsoft — free for personal/non-commercial use; commercial use
  requires a paid Highcharts license.
- **`highcharts-core`** (the Highcharts for Python toolkit) is itself
  proprietary, governed by the Highcharts for Python Toolkit License (which
  presupposes a Highcharts Software license — paid for commercial use, or a
  Personal/Educational license otherwise).

If you fork or deploy this, obtaining the required Highcharts and
Highcharts-for-Python licenses for your usage is your responsibility. Streamlit
(Apache-2.0) and pandas (BSD-3-Clause) are permissively licensed. See the
[`LICENSE`](LICENSE) file for the full MIT text and [`NOTICE`](NOTICE) for the
third-party notice.
