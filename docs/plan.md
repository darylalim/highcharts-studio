# Feature plan

A working list of features for highcharts-studio. Add to it freely; the structure below is
what makes an entry ready to start from.

## Direction: a lightweight chart editor

The app already has enough chart types (30). What it lacks is the **editing** in "chart
editor": today the only controls on a chart's appearance are its title and height. So the
plan completes one loop and stops there:

```text
data in → pick chart → tweak it → take it out
   ✓          ✓        #5 (+#6) #13, #15, #2  (+ #8: fix the data without leaving the app)
```

Anything that does not serve that loop is deferred or dropped, with the reason kept so it
is not re-proposed without new information.

**Where it ends: 1.0 is the planned set.** When every `planned` item has shipped, the
editor loop is complete and the next release is **1.0**. That gives the plan a finish line,
and the Shipping rule's "while below 1.0" clause (see the [Legend](#legend)) a defined end.
A new item joins the planned set only if 1.0 would be incomplete without it; anything else
waits until after 1.0.

**Kept out on purpose:**

- **No new chart types for now.** Each costs the nine steps in
  [Adding a chart type](../CLAUDE.md#adding-a-chart-type) plus docs, and breadth is not
  what is missing. See [#10](#10-new-chart-types).
- **No free-form colour pickers.** The palette is designed and tested for colour-blind
  readability (`test_no_palette_pair_collapses_under_colour_vision_deficiency`); a per-series
  picker would undo that. If colour choice is ever wanted, offer a few **preset** palettes,
  each passing the same tests.
- **No new runtime dependencies.** The runtime set is exactly `highcharts-core`, `pandas`
  and `streamlit`, and it is already near the floor: Streamlit brings 35 of the 39 runtime
  packages (including `pandas`, `numpy` and `pyarrow`), `highcharts-core` adds 3, and
  `pandas` adds none because Streamlit requires it anyway. Every planned feature is built
  from the standard library or what these three already ship, and a feature that needs a
  new package is dropped or narrowed instead (as Excel upload was, in [#9](#9-delimiter-sniffing)).
  The same applies to **network** dependencies: since [#13](#13-client-side-export) the app
  relies on the Highcharts CDN alone (the export server is gone), and should never add a
  second. Dev tools (`pytest`, `ruff`, `ty`, `watchdog`)
  never ship to users and are outside this rule. Enforced by [#12](#12-pin-the-runtime-dependency-set).

**Client side, in two steps.** The chart is drawn in the browser, and since
[#13](#13-client-side-export) (0.21.0) so are its downloads: nothing goes to a remote
service any more. That was the first step. Running the
whole app in the browser with no server ([#14](#14-spike-run-the-app-in-the-browser-stlite))
is large and waits on a spike, because its first-load download clashes with "lightweight".

### Chart tiers

How well each of the 30 types fits the three directions above: whether the style controls
in [#5](#5-style-controls) do something to it (editor), how many extra Highcharts modules it
loads (embeddable, client side; resolved from `get_script_tags` on 2026-10-07), and whether
an ordinary "category + numbers" CSV drives it. **No type is removed**: every one works and
is tested, and the freeze in [#10](#10-new-chart-types) already stops growth. The tiers decide
**where effort goes first**.

| Tier | Types | Extra modules | Why |
|---|---|---|---|
| **1 · Core** | line, spline, area, areaspline, column, bar, pie, scatter | 0 | Where the style controls apply most (each control still applies per type: no stacking for pie or scatter, no axes for pie). The simplest embed. Any category + numbers CSV. |
| | bubble, radar | 1 (`highcharts-more`) | Still plain CSV columns; most controls apply. |
| **2 · Good fit** | heatmap, treemap, funnel, pyramid, boxplot, waterfall, columnrange, arearange, bullet, dumbbell | 1 each (dumbbell 2) | Common in business use and CSV-friendly, but each answers one question (a profit bridge, a distribution, actual vs target), so only some controls apply. |
| **3 · Weak fit** | sankey, dependencywheel, networkgraph, organization | 1–2 | Node-link data (source → target name columns); layout is automatic, so almost no control applies. |
| | sunburst | 1 | Needs parent/child data, which few CSVs carry. |
| | xrange, timeline | 1 | Need date-coordinate columns: planning charts, outside the typical editor use. |
| | variwide | 1 | Niche: bar width is a second value. |
| | gauge, solidgauge | 1 | A single-number widget rather than a chart, with controls (aggregation, dial) no other type uses. |

The tiers line up with the extra-column kwargs: most Tier 3 types are the ones that needed a
target, parent, end, title or width column, or the gauge's own controls. A type that needs
extra column roles is a type whose data does not come in an ordinary CSV shape.

## Legend

**Status:** `idea` → `planned` → `in progress` → `done`; or `deferred` (fine, not now),
`dropped` (does not fit the direction), `folded` (merged into another entry). When an entry
is done, move its reasoning into [`chart-types.md`](chart-types.md) or
[`decisions.md`](decisions.md) (the docs that record what is true of the code) and shrink
the entry here to one line pointing there.

**Size:** S = an afternoon, no new builder kwarg · M = a new kwarg or a new module ·
L = changes how the app is structured.

**Shipping.** Each planned item is one branch and one release: bump `version` in
`pyproject.toml`, add the `CHANGELOG.md` section, and commit the `uv.lock` line uv rewrites
(step 9 of [Adding a chart type](../CLAUDE.md#adding-a-chart-type) applies to every item, not
only new types). A fix with no new behaviour is a **patch** bump; a feature is a **minor**
bump. While the version is below 1.0, a change that removes public API is also a minor bump,
but its changelog section says **Removed** and names what went, since the builder is
importable on its own ([#13](#13-client-side-export) was the one planned item that did
this). Items may share a release only when they cannot be shipped usefully apart, and the
entry says so.

## Contents

In build order. Numbers are stable IDs, not priorities.

| Order | # | Feature | Size | Status |
|---|---|---|---|---|
| 1st | 20 | [Escape `</script>` in the chart's JS](#20-escape-script-in-the-charts-js) | S | done (0.20.2) |
| 2nd | 22 | [Large datasets (re-scoped: the networkgraph freeze)](#22-large-datasets) | S | done (0.20.3) |
| 3rd | 12 | [Pin the runtime dependency set](#12-pin-the-runtime-dependency-set) | S | done (0.20.4) |
| 4th | 21 | [Pin the Highcharts JS version](#21-pin-the-highcharts-js-version) | S | done (0.20.5) |
| 5th | 19 | [Date the real-world samples](#19-date-the-real-world-samples) | S | done (0.20.6) |
| 6th | 13 | [Client-side export (retire Static PNG mode)](#13-client-side-export) | S–M | done (0.21.0) |
| 7th | 23 | [Host a public demo on Streamlit Community Cloud](#23-host-a-public-demo-on-streamlit-community-cloud) | S | done (0.21.1) |
| 8th | 18 | [A stackable sample](#18-a-stackable-sample) | S | done (0.22.0) |
| 9th | 5 | [Style controls (with the reference line)](#5-style-controls) | M | done (0.23.0) |
| 10th | 17 | [Group the chart-type picker by family](#17-group-the-chart-type-picker-by-family) | M | done (0.24.0) |
| 11th | 15 | [Embeddable outputs: HTML, JS, JSON](#15-embeddable-outputs-html-js-json) | M | done (0.25.0) |
| 12th | 2 | [Export as Python](#2-export-as-python) | S | planned |
| 13th | 8 | [Edit data in place](#8-edit-data-in-place) | S | planned |
| — | 24 | [Group a big pie's tail into "Other"](#24-group-a-big-pies-tail-into-other) | S–M | idea |
| — | 6 | [Reference line](#6-reference-line) | — | folded into #5 |
| — | 1 | [Download the chart as HTML](#1-download-the-chart-as-html) | — | folded into #15 |
| — | 4 | [Date X axis for line-family charts](#4-date-x-axis-for-line-family-charts) | M | deferred |
| — | 9 | [Delimiter sniffing (Excel dropped)](#9-delimiter-sniffing) | S | deferred |
| — | 3 | [Shareable link](#3-shareable-link) | M | deferred |
| — | 7 | [Data prep: aggregate, sort, top-N, filter](#7-data-prep) | M | deferred |
| — | 10 | [New chart types](#10-new-chart-types) | M each | deferred |
| — | 16 | [Switch the app's iframe to the JSON-built JS](#16-switch-the-apps-iframe-to-the-json-built-js) | M | deferred |
| — | 14 | [Spike: run the app in the browser (stlite)](#14-spike-run-the-app-in-the-browser-stlite) | M (spike) | deferred |
| — | 11 | [Compare charts side by side](#11-compare-charts-side-by-side) | L | dropped |

---

## Planned

### 20. Escape `</script>` in the chart's JS

Done in 0.20.2. The reasoning, the tests, and what rendering showed (Highcharts draws label
markup as its own restricted HTML, which #15 inherits) are in
[`decisions.md`](decisions.md#script-in-user-text-an-encoding-not-an-edit).

### 22. Large datasets

Done in 0.20.3, **re-scoped** after rendering. The premise (pie, treemap, funnel and pyramid
draw blank past 1,000 rows, Highcharts' `turboThreshold`) was disproved: since Highcharts 11.4.4
they draw. What rendering found instead was a networkgraph that froze the tab, now refused past
150 nodes. The readability half went to [#24](#24-group-a-big-pies-tail-into-other). The whole
story: [`decisions.md`](decisions.md#large-data-the-turbothreshold-bug-that-was-not-there).

### 12. Pin the runtime dependency set

Done in 0.20.4: `test_runtime_dependencies_are_exactly_the_pinned_set` in
`tests/test_packaging.py` pins the runtime `dependencies` by name, and its comments carry the
reasoning (names only, the `dev` group left free, a duplicated entry caught too).

### 13. Client-side export

Done in 0.21.0: Static PNG mode, the render-mode selector, `build_chart_png` and
`explain_export_failure` are gone; every chart carries Highcharts' ☰ menu, drawing PNG/JPEG/SVG
in the browser with the export-server fallback off. The reasoning, the settings and what
rendering verified: [`decisions.md`](decisions.md#static-png-mode-and-its-retirement).

- **Checked 2026-10-07:** a real PNG and SVG download saves in **Firefox and Safari**, and the
  PNG is dark (tested by hand; Chrome's path was exercised by script).

### 23. Host a public demo on Streamlit Community Cloud

Done in 0.21.1: live at <https://highcharts-studio.streamlit.app>, public and non-commercial. Why
Community Cloud, the two options rejected, the licence condition and what was checked:
[`decisions.md`](decisions.md#hosting-a-public-demo-on-community-cloud).

### 21. Pin the Highcharts JS version

Done in 0.20.5: `HIGHCHARTS_JS_VERSION` (13.1.1, the release already in use) and
`_pin_script_tags` in `highcharts_builder.py`. For #13 and #15: their new modules (`exporting`,
`offline-exporting`, `accessibility`) were checked to load at 13.1.1 from a browser, and they
are pinned automatically, since every script `get_script_tags` emits goes through the rewrite.
The reasoning and the upgrade procedure:
[`decisions.md`](decisions.md#highcharts-js-one-pinned-release).

### 19. Date the real-world samples

Done in 0.20.6: *Company market cap, ~2024 (treemap)* and *Country economics, ~2023 (bubble)*,
with what the figures are (illustrative, and when) in each docstring in `sample_data.py`. Checked
against sources: the market caps match about October 2024; the country figures are a 2022–23
mix. The parentheses constraint turned out to protect nothing yet (no `_pick_*` helper picks
either sample), but the format keeps every label ending in its `(type)` for the day one does.

### 18. A stackable sample

Done in 0.22.0: *Monthly revenue by channel (stacked column/area)* in `sample_data.py`, four
channels that sum to each month's revenue, so #5's stacking control has a sample where the
stacked total means something. Its rationale is in
[`chart-types.md`](chart-types.md#the-sample-datasets).

### 5. Style controls

Done in 0.23.0: `ChartStyle` and `style_controls_for` in `highcharts_builder.py`, and the sidebar's
Style section, for the Tier 1 types. Settled with the user before the code: log scale is disabled
while stacked as well as for Y ≤ 0, the reference line is a fixed value, and pie gets no controls
this pass. Found by rendering and fixed: percent stacking now labels its axis with `%`, and the
reference line's label is nudged inside the plot. The design and its reasons:
[`decisions.md`](decisions.md#style-one-object-not-one-kwarg-per-control). Still open, for Tier 2:
which controls each type should gain, one at a time.

### 17. Group the chart-type picker by family

Done in 0.24.0: `CHART_FAMILIES` and `chart_family` in the builder, family pills (with
`required=True`, which Streamlit 1.65 supports) over a selectbox of the family's types, help per
family, and samples in family order. `test_chart_families_partition_the_supported_types` keeps
every type reachable. The decisions and their reasons:
[`decisions.md`](decisions.md#chart-type-picker-families-then-types).

### 15. Embeddable outputs: HTML, JS, JSON

Done in 0.25.0: `build_chart_exports` (JSON, the JS call, an HTML snippet and a full page) and the
app's Export panel, which replaced the generated-config toggle. Two choices settled with the user
before the code: the JS tab holds the chart call alone (the snippet is the self-contained form),
and the treemap's lost tile border, found while comparing the options dict with the emitted JS, was
fixed first. The Python tab arrives with [#2](#2-export-as-python). The design, the decisions and
what rendering verified:
[`decisions.md`](decisions.md#embeddable-exports-json-first).

### 2. Export as Python

- **What & why:** Add a copyable `make_chart(...)` call that reproduces the current chart
  with the public API, as the Python tab of [#15](#15-embeddable-outputs-html-js-json)'s
  Export panel. This turns the app into a way to *learn* `highcharts-core`, not only to use
  it. (The JSON half of this item moved to #15.)
- **Touches:** a pure `python_snippet(...)` helper in `highcharts_builder.py` (testable:
  `exec` the snippet against the sample frame and compare the options it produces).
- **Decided:** the snippet starts with `df = pd.read_csv("your-file.csv")` rather than
  carrying the data: one shape, short at any data size, and the user has their own CSV. For
  a sample dataset (no file to read), a comment names the sample instead. Settled
  2026-10-07; rejected: inlining samples only (two snippet shapes to build and test) and
  always inlining (long snippets for large uploads, #15's size problem again). Built after
  #5, so the snippet includes `style=ChartStyle(...)` from the start. The `exec` test feeds
  the snippet a `df` rather than a file.
- **Size:** S · **Status:** planned

### 8. Edit data in place

- **What & why:** Swap the read-only `st.dataframe` preview for `st.data_editor`, so a user
  can fix a typo or try a value without re-uploading.
- **Touches:** `streamlit_app.py`. The edited frame must replace `df` *before* the pickers
  and the gate run.
- **Decided:** edit cells only (no adding or deleting rows, the lightweight answer), and
  edits reset when the dataset changes: they belong to the data they were made on.
- **Size:** S · **Status:** planned

## Ideas

### 24. Group a big pie's tail into "Other"

- **What & why:** Split out of [#22](#22-large-datasets). A pie, treemap, funnel or pyramid of
  1,200 rows draws, but cannot be read: the 1,200-slice pie rendered on 2026-10-07 is a dark disc,
  because the slices are so thin that their borders (painted the background colour) cover most of
  the fill. Keep the largest slices and fold the rest into one "Other" point, with a caption saying
  how many were grouped. Funnel and pyramid are ordered stages, not parts to rank, so they may need
  a row cap with a message instead.
- **Why an idea, not planned:** nothing breaks, so 1.0 is not incomplete without it (the bar in
  [Direction](#direction-a-lightweight-chart-editor)).
- **Open questions:** how many slices to keep (a fixed number, or a share of the total)? Should
  `count_marks` report the drawn slices or the rows?
- **Size:** S–M · **Status:** idea

## Folded

### 6. Reference line

Folded into [#5](#5-style-controls) and shipped with it in 0.23.0 as `ChartStyle.reference_line`:
a fixed typed value (decided over mean/median, since "the mean of which series" has no single
answer once two Y columns are selected), drawn dashed in the chrome's text colour.

### 1. Download the chart as HTML

Folded into [#15](#15-embeddable-outputs-html-js-json) and shipped with it in 0.25.0 as the
**HTML page** tab: CDN-linked only, no inlined Highcharts JavaScript.

## Deferred

### 4. Date X axis for line-family charts

- **Why deferred:** a real correctness fix, not an editing feature, so it sits outside the
  editor's loop and can be picked up as a standalone fix at any time.
- **The problem:** `line`/`spline`/`area`/`areaspline`/`column` treat X as **categories**,
  so a time series with uneven dates (a missing week, say) is drawn evenly spaced and
  silently misrepresents time. The fix is `xAxis.type: "datetime"` with `[millis, y]`
  points, reusing `picker_columns` and `_TOOLTIP_DAY`/`_TOOLTIP_INSTANT` from
  xrange/timeline.
- **Open questions when picked up:** Should a date X be sniffed automatically, or a toggle?
  Its sample would lead with a date column, which breaks the
  [first-column rule](chart-types.md#the-sample-datasets).

### 9. Delimiter sniffing

- **Why deferred, and narrowed:** Excel upload is **dropped** (it needs a new `openpyxl`
  dependency, against "lightweight"). Only the cheap half stays: `load_csv` is a bare
  `pd.read_csv(file)`, so a semicolon-delimited CSV (common outside the US) loads as one
  column. `sep=None, engine="python"` sniffs the delimiter, with no new control.
- **Open questions when picked up:** Comma-decimal numbers (`1,5`) still need an explicit
  option; is that worth a widget?

### 3. Shareable link

- **Why deferred:** It only works for sample datasets (an uploaded CSV cannot travel in a
  URL), and seeding the keyed pickers (`_KEYED_PICKERS`) from `st.query_params` before they
  are instantiated is the hardest widget-state work in the app. A lot of cost for the one
  case where the data is already built in. #15 and #2 cover saving a chart.

### 7. Data prep

- **Why deferred:** Grouping, sorting, top-N and filtering move the app toward a BI tool,
  which is a different product. A user can shape the CSV before uploading. If one transform
  is ever worth it, **sort** is the smallest: it helps pie and bar, and it needs no grouping.

### 10. New chart types

- **Why deferred:** a deliberate freeze, explained under [Direction](#direction-a-lightweight-chart-editor).
  If it lifts, these candidates need no new kwarg (the cheapest kind, as `timeline` showed):

| Type | Shape it shares | Notes |
|---|---|---|
| `histogram` | boxplot (aggregates raw rows) | Fills the clearest gap: no distribution chart for a single column. |
| `packedbubble` | pie / treemap (label + value) | Part-of-whole without the angle-reading problem. |
| `wordcloud` | pie (label + weight) | Needs a text-heavy sample. |
| `streamgraph` | cartesian multi-series | Close to `areaspline`; the theme must be checked by rendering. |
| `pareto` | column + derived line | Sorted bars plus a cumulative-% line. |

### 16. Switch the app's iframe to the JSON-built JS

- **Why deferred:** Split out of [#15](#15-embeddable-outputs-html-js-json) to keep that
  item to the exports. Once #15 exists, the app's interactive iframe could draw from the
  same JSON-built JS instead of `to_js_literal`. That would fix both
  [unquoted-string bugs](decisions.md#the-strings-highcharts-core-emits-unquoted) in the app
  itself, so one renderer would serve both the app and the exports.
- **What it costs:** a render check across all 30 types in both browser colour schemes,
  and the docs that describe the bugs as live in the app (`CLAUDE.md`'s "Two string shapes
  the serializer emits UNQUOTED" convention) rewritten to say they are confined to
  `to_js_literal`, which the app would no longer call.
- **Size:** M · **Status:** deferred

### 14. Spike: run the app in the browser (stlite)

- **Why deferred:** Running with no server at all means
  [stlite](https://github.com/whitphx/stlite) (Streamlit on Pyodide, Python in WebAssembly),
  hosted as static files. It keeps the Python code; rewriting the app in JavaScript would
  throw away the builder, the tests and `highcharts-core`, so that is not an option. But
  every visitor would download Pyodide and pandas (tens of MB) before seeing a chart, which
  works against "lightweight". So this is a time-boxed **spike** first, answering four
  questions before anyone commits to it:
  1. **Streamlit version.** stlite bundles its own Streamlit, which can lag the official
     release. Does it support what the app uses (`st.iframe`, `st.pills`,
     `segmented_control(required=)`, bordered `st.metric`, the newer `[theme]` keys)?
  2. **Packages.** Do `highcharts-core`, `esprima` and `validator-collection` install in
     Pyodide (`micropip`), and does `pyarrow` work for `st.dataframe`?
  3. **First load.** How many MB, and how many seconds, until the first chart appears on an
     ordinary connection? Write down the number; it decides the item.
  4. **Hosting.** Which static host (GitHub Pages is the obvious one), and does the CSV
     upload still work with no server?
- **Not affected:** the tests keep running on CPython in CI; only the deployment changes.
- **Depends on:** [#13](#13-client-side-export), now done (0.21.0): with the export server
  gone, nothing in the app needs a server-side network call.
- **Size:** M for the spike; the migration is sized after it · **Status:** deferred

## Dropped

### 11. Compare charts side by side

- **Why dropped:** The largest structural change on the list (the sidebar *is* one chart's
  state, so this needs a list of chart specs in session state and the picker logic made
  re-runnable), and the opposite of lightweight. Exporting (#13, #15, #2) is the lightweight way
  to keep more than one chart.

---

## Your additions

<!-- Add new entries above this line, using the same shape:
### N. Title
- **What & why:**
- **Touches:**
- **Open questions:**
- **Size:** · **Status:** idea
-->
