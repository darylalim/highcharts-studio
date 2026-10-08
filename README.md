# Highcharts Studio

[![CI](https://github.com/darylalim/highcharts-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/darylalim/highcharts-studio/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Streamlit 1.59+](https://img.shields.io/badge/streamlit-1.59%2B-ff4b4b.svg)](https://streamlit.io)

A [Streamlit](https://streamlit.io) app for building interactive charts with
[Highcharts](https://www.highcharts.com). Load a sample dataset or a CSV, pick one of 30 chart
types, map its columns, and download or embed the result. Every chart is built with
[`highcharts-core`](https://github.com/highcharts-for-python/highcharts-core), the Highcharts for
Python toolkit; the app uses no native Streamlit charts.

**Live demo:** <https://highcharts-studio.streamlit.app> (public and non-commercial; it may take a
moment to wake up after a quiet spell).

## Contents

[Features](#features) · [Chart types](#chart-types) · [Quick start](#quick-start) ·
[Deploy](#deploy) · [Development](#development) · [License](#license)

## Features

- **Data in.** Built-in sample datasets or your own CSV. Map columns with pills, which fall back
  to a multiselect on wide CSVs.
- **Edit in place.** Click a cell in the Source data table to fix a typo or try a value, and the
  chart follows. Cells only (no adding or deleting rows); edits reset when you change dataset.
- **Chart types by family.** Pick a family, then a type within it, so the 30 types never sit in
  one long list. The sample datasets follow the same order.
- **Style controls.** For the basic types: axis titles, legend position, data labels, stacking
  (normal or percent), a log Y axis, and a dashed reference line. A control a type cannot use is
  hidden and keeps its value for when you switch back.
- **Readable at any size.** A pie past 8 slices or a treemap past 20 tiles folds its smallest
  marks into one "Other", with a caption saying how many rows were grouped.
- **KPI row.** Rows, numeric columns, and a third metric that adapts to the chart: series
  plotted, or the mark count (cells, tiles, flows, events, …) for types that draw many marks from
  one series.
- **Downloads.** Each chart's ☰ menu saves PNG, JPEG or SVG, drawn in the browser. No export
  server is contacted.
- **Export.** A toggle opens the Export panel: an HTML snippet to paste into any page, a
  standalone HTML page, the JS call, the JSON options, and the Python `make_chart(...)` call that
  rebuilds the chart. Each has a copy button and a download.
- **One dark theme.** The charts match the app's dark theme, downloads included. The series
  palette (`DEFAULT_COLORS`) is the theme's `chartCategoricalColors`, kept in sync by a test.

## Chart types

| Family | Type | What it shows | Extra input |
| --- | --- | --- | --- |
| Basic | `line`, `spline`, `area`, `areaspline`, `column`, `bar` | One or more Y series over a category X | — |
| Basic | `scatter` | Y against X as points | — |
| Basic | `bubble` | A scatter with a third value sizing each marker | Size (Z) |
| Basic | `radar` | A polar spider line over a category axis | — |
| Part of whole | `pie` | Each label's share of one value column | — |
| Part of whole | `treemap` | Rectangles sized by a value column | — |
| Part of whole | `funnel` | Stages narrowing from top to bottom | — |
| Part of whole | `pyramid` | Stages widening from top to bottom | — |
| Comparison | `waterfall` | A running total of signed changes, closed by a Total bar | — |
| Comparison | `bullet` | A measure bar read against a goal crossbar | Goal |
| Comparison | `dumbbell` | Two linked markers per category: before and after | After |
| Comparison | `columnrange` | Floating bars from a low to a high per category | High |
| Comparison | `arearange` | A filled band from a low to a high per category | High |
| Comparison | `heatmap` | A category × category grid, cells coloured by value | — |
| Comparison | `boxplot` | Per-category distributions from repeated observations | — |
| Comparison | `variwide` | Columns whose width is a second value, so area is the reading | Width |
| Flow & hierarchy | `sankey` | Weighted flows between two node columns | Target |
| Flow & hierarchy | `dependencywheel` | The same weighted flows drawn around a ring | Target |
| Flow & hierarchy | `networkgraph` | A force-directed graph of unweighted links | Target (no Y) |
| Flow & hierarchy | `organization` | An org chart of titled boxes, employee to manager | Manager, Title (no Y) |
| Flow & hierarchy | `sunburst` | A hierarchy as rings, from a parent column and leaf values | Parent |
| Time | `xrange` | A Gantt-style schedule of bars from start to end on named lanes | End |
| Time | `timeline` | Named events on one dated spine | — (Y is the date) |
| Gauge | `gauge` | A needle per column on a tick scale | Aggregation, Dial (no X) |
| Gauge | `solidgauge` | An arc per column | Aggregation, Dial (no X) |

The gauges take no label column: each selected column becomes one mark, reduced to a single
reading by the aggregation you pick (sum, mean, median, min, max or last). The per-type design
notes are in [`docs/chart-types.md`](docs/chart-types.md).

## Quick start

This project uses [uv](https://docs.astral.sh/uv/). No API keys, secrets or environment variables
are needed.

```bash
uv sync
uv run streamlit run streamlit_app.py
```

Then open <http://localhost:8501>. The chart loads Highcharts JS from `code.highcharts.com`, so the
browser needs network access. The release is pinned (`HIGHCHARTS_JS_VERSION` in
`highcharts_builder.py`), so a new Highcharts release cannot change a chart until that constant is
bumped.

## Deploy

The app runs on [Streamlit Community Cloud](https://streamlit.io/cloud) unchanged:

1. Fork or push this repository to GitHub.
2. In Community Cloud, create an app from it with `streamlit_app.py` as the entrypoint.
3. Leave the Python version at **3.12** (the default, and the version the tests run on).

Community Cloud installs from `uv.lock`, so no `requirements.txt` is needed.

**Check the licence first.** Highcharts JS and `highcharts-core` are free for personal and
non-commercial use only, and a public deployment is still a use of them. Deploy publicly only if
your use is non-commercial, or once you hold a commercial Highcharts licence (see
[License](#license)). The same applies to pages you paste an exported chart into.

## Development

`highcharts_builder.py` holds the chart logic as pure, Streamlit-free functions (DataFrame →
Highcharts options → `Chart` → HTML), so it can be tested on its own. `streamlit_app.py` is the
UI, embedding each chart through `st.iframe` since there is no official Streamlit component for
`highcharts-core`. `sample_data.py` holds the sample datasets.

```bash
uv run pytest                                       # tests
uv run ruff check --fix . && uv run ruff format .   # lint + format
uv run ty check                                     # type check
```

GitHub Actions runs all three on every push to `main` and every pull request, and cuts a release
when `version` in `pyproject.toml` is bumped. Committed [Claude Code](https://claude.com/claude-code)
hooks in `.claude/` run the same checks locally. See [`CLAUDE.md`](CLAUDE.md) for the architecture
and conventions.

## License

This project's own code is released under the [MIT License](LICENSE): you're free to use, modify
and distribute it.

The MIT license covers **only this project's code**. Two of the tools it renders with are
proprietary and separately licensed, and the MIT grant does not extend to them:

- **Highcharts JS** (loaded from the CDN, including the exporting modules that draw downloads in
  the browser) is owned by Highsoft. It is free for personal and non-commercial use; commercial
  use requires a paid Highcharts license.
- **`highcharts-core`** (the Highcharts for Python toolkit) is governed by the Highcharts for
  Python Toolkit License, which presupposes a Highcharts Software license: paid for commercial
  use, or a Personal/Educational license otherwise.

If you fork or deploy this, getting the Highcharts and Highcharts for Python licenses your use
needs is your responsibility. Streamlit (Apache-2.0) and pandas (BSD-3-Clause) are permissively
licensed. See [`LICENSE`](LICENSE) for the full MIT text and [`NOTICE`](NOTICE) for the
third-party notice.
