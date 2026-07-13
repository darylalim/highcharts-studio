# Highcharts Studio

[![CI](https://github.com/darylalim/highcharts-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/darylalim/highcharts-studio/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Streamlit 1.57+](https://img.shields.io/badge/streamlit-1.57%2B-ff4b4b.svg)](https://streamlit.io)

A [Streamlit](https://streamlit.io) application for building data visualizations
with [Highcharts](https://github.com/highcharts-for-python) — **every chart is
produced by `highcharts-core`** (the Highcharts for Python toolkit), with no
native Streamlit charts.

## Contents

[Setup](#setup) · [Run](#run) · [What it does](#what-it-does) · [Files](#files) ·
[Test](#test) · [Lint &amp; format](#lint--format) · [Type check](#type-check) ·
[CI](#ci) · [Claude Code hooks](#claude-code-hooks) · [Notes](#notes) ·
[Dependencies](#dependencies) · [License](#license)

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
- An at-a-glance KPI row (rows, numeric columns, and a chart-type-adaptive third
  metric — series plotted, or cells for a heatmap, tiles for a treemap, flows
  for a sankey, boxes for a boxplot, steps for a waterfall, sectors for a
  sunburst, and bars for an xrange; a gauge needs no entry of its own, since its
  marks *are* its series — one ring per column — so "series plotted" is already
  literally the ring count) above
  the chart
  — with the chart type shown as a badge above the chart rather than a metric in
  the row — a side-by-side source-data preview, and a toggle that reveals the
  generated Highcharts config (the `to_js_literal()` output). The Y-series picker
  uses compact pills, falling back to `st.multiselect` for wide CSVs.
- Supported chart types: `line`, `spline`, `area`, `areaspline`, `column`,
  `bar`, `pie`, `scatter`, `bubble` (scatter plus a size column that drives
  each marker's area), `radar` (a polar spider/web line chart over a
  category axis), `heatmap` (a category × category grid whose cell colors,
  on a sequential color axis, show the values), `treemap` (nested
  rectangles whose area, sized by a value column, shows each label's share),
  `sankey` (a flow diagram: each row is a link between two node columns,
  whose width is a value column), `boxplot` (per-category distributions: a
  category column whose values repeat, one row per observation, plus a column of
  raw measurements — each category becomes a Tukey box, with outliers as dots),
  `waterfall` (a cumulative bridge: a step-label column plus a column of
  signed *deltas*, so each bar floats where the last one ended, showing how a
  starting value becomes an ending one — rises green, falls red, and a closing
  **Total** bar added for you), `sunburst` (a hierarchy as concentric rings:
  one row per node, a **Parent** column naming each node's parent — blank means a
  top-level branch — and a column of *leaf* values. A parent's arc is the **sum** of
  its children's, so a node with children needs no value of its own; a centre
  sector is added for you; and clicking a sector zooms into that branch),
  `xrange` (a Gantt-style timeline, and the only type whose marks have *extent*
  rather than sitting at a point: one row per bar, a **Lane** column naming each
  task — it may repeat, so a lane can hold several bars — plus a **Start** and an
  **End** column. Those two are *coordinates*, so they may be dates (ISO-8601) or
  plain numbers, but both the same kind; a zero-length bar is a **milestone** and
  still draws, while a backwards one is dropped), and `solidgauge` (concentric rings on
  one shared dial — an "activity gauge", and the only type with **no X column at
  all**: a gauge has no labels, only readings. Each selected column becomes one
  ring, showing that column **collapsed to a single number** by the aggregation you
  pick — sum / mean / median / min / max / last — so it is the only type whose marks
  are not in the data but *reduced* from it. The dial is derived from those readings
  and can be overridden; a column with nothing in it keeps its ring, empty, rather
  than being drawn as a fictional zero).

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
| `tests/test_packaging.py` | Unit tests guarding the licensing metadata (pyproject `license` fields, the `LICENSE` file, and the `NOTICE` third-party notice) — plus the README's own header badges and `## Contents` list — against drift. |
| `.claude/settings.json`, `.claude/hooks/` | Committed Claude Code hooks that mirror the CI gates (see Claude Code hooks below). |
| `.github/workflows/ci.yml` | GitHub Actions: pytest, Ruff lint/format, and ty on every push to `main` and every PR. |
| `LICENSE` | MIT license for this project's own code (kept pristine so GitHub detects it as MIT). |
| `NOTICE` | Third-party notice for the proprietary Highcharts JS / export server and `highcharts-core` dependencies, split out of `LICENSE`. |

## Test

```bash
uv run pytest
```

Three suites (see [`CLAUDE.md`](CLAUDE.md) for the full breakdown):

- **`tests/test_smoke.py`** — the pure builder (every chart type, the
  missing-data and scatter/bubble edge cases, radar's polar-line shape, heatmap's
  colorAxis value matrix, treemap's value-sized tiles, sankey's node-link flows,
  boxplot's aggregated Tukey distributions (including the `iqr == 0` degeneracies
  and the `fillColor` silent drop), waterfall's appended `isSum` total and its
  semantic up/down/total bar colors, sunburst's assembled hierarchy (synthesized
  node ids, so two leaves named the same stay two sectors rather than colliding;
  valueless internal nodes, so Highcharts' sum is authoritative; a dropped dangling
  parent vs. a raised cycle; and the appended root), xrange's interval bars (the
  date-vs-number column sniff and its two traps — a numeric column must never reach
  a date parser, since `pd.to_datetime(12)` silently yields the epoch, and a date
  column's epoch millis must be unit-normalized before the int64 view, or every bar
  lands in 1970; the kept milestone and the dropped backwards bar; and the per-lane
  hue), gauge's reduced rings (the empty-column trap — `pd.Series([nan, ...]).sum()`
  is `0.0`, so a naive reduction draws a fictional zero where the truth is "no data";
  the dial derived from the *readings* rather than the raw column, without which a
  `sum` pins every ring; `threshold: 0`, without which the bigger loss draws the
  shorter arc; and the three levels a ring's hue has to be written to, since a
  point-level radius and a series-level color are each silently dropped),
  the brand palette, the
  light/dark theming including the dark-mode tooltip and the heatmap colorAxis, and
  the validation guards — plus an end-to-end pass driving every supported type
  through the real `Chart.from_options` → `to_js_literal` pipeline) and the sample
  datasets, plus a headless `AppTest` pass that drives the full app (switching
  controls including the bubble Size (Z), sankey Target (to), sunburst Parent and
  xrange End
  selectors, gauge's aggregation picker and its two Dial inputs — whose defaults are
  seeded *from the builder*, and which deliberately reset when the data or the
  reduction changes, because a scale carried over from either is a silent lie —
  radar,
  heatmap, treemap, boxplot, and waterfall, the
  config toggle, the KPI row, the wide-CSV `st.multiselect` fallback, both render
  modes, and the guard messages).
- **`tests/test_hooks.py`** — the `.claude/hooks/` scripts (see
  [Claude Code hooks](#claude-code-hooks)).
- **`tests/test_packaging.py`** — the licensing metadata (`pyproject.toml`
  `license` fields, the `LICENSE` file, and the `NOTICE` third-party notice) plus
  the README's own header badges and `## Contents` list, guarded against drift.

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
- Highcharts ≥ 13 expresses its default colors as `light-dark()` CSS variables, which
  would resolve against the **viewer's browser** rather than the app's theme. The
  generated HTML therefore pins the chart's `color-scheme` to `only light`, so those
  defaults resolve exactly as the export server resolves them and the two render modes
  agree. All theming flows through `build_options(..., dark=...)` instead.
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
