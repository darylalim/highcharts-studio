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
  The same applies to **network** dependencies: the app relies on the Highcharts CDN and
  export server today, should never add a third, and [#13](#13-client-side-export) takes it
  down to the CDN alone. Dev tools (`pytest`, `ruff`, `ty`, `watchdog`)
  never ship to users and are outside this rule. Enforced by [#12](#12-pin-the-runtime-dependency-set).

**Client side, in two steps.** The chart is already drawn in the browser in interactive
mode; only Static PNG mode sends it to a remote service (`export.highcharts.com`). Moving
the PNG into the browser ([#13](#13-client-side-export)) is small and planned. Running the
whole app in the browser with no server ([#14](#14-spike-run-the-app-in-the-browser-stlite))
is large and waits on a spike, because its first-load download clashes with "lightweight".

## Legend

**Status:** `idea` → `planned` → `in progress` → `done`; or `deferred` (fine, not now),
`dropped` (does not fit the direction), `folded` (merged into another entry). When an entry
is done, move its reasoning into [`chart-types.md`](chart-types.md) or
[`decisions.md`](decisions.md) (the docs that record what is true of the code) and shrink
the entry here to one line pointing there.

**Size:** S = an afternoon, no new builder kwarg · M = a new kwarg or a new module ·
L = changes how the app is structured.

## Contents

In build order. Numbers are stable IDs, not priorities.

| Order | # | Feature | Size | Status |
|---|---|---|---|---|
| 1st | 12 | [Pin the runtime dependency set](#12-pin-the-runtime-dependency-set) | S | planned |
| 2nd | 13 | [Client-side export (retire Static PNG mode)](#13-client-side-export) | S–M | planned |
| 3rd | 5 | [Style controls (with the reference line)](#5-style-controls) | M | planned |
| 4th | 15 | [Embeddable outputs: HTML, JS, JSON](#15-embeddable-outputs-html-js-json) | M | planned |
| 5th | 2 | [Export as Python](#2-export-as-python) | S | planned |
| 6th | 8 | [Edit data in place](#8-edit-data-in-place) | S | planned |
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

### 12. Pin the runtime dependency set

- **What & why:** Turns the "no new runtime dependencies" rule into a test, so adding a
  package is a deliberate change that has to edit a test, not something that slips in with
  a feature. It goes first because it guards every feature after it.
- **Touches:** `tests/test_packaging.py` only. Read `[project].dependencies` from
  `pyproject.toml` with `tomllib` (standard library), strip each version specifier, and
  assert the names are exactly `{"highcharts-core", "pandas", "streamlit"}`. The failure
  message should point to the Direction section of this file. The `dev` group is
  deliberately not pinned.
- **Verify by breaking it:** add a fake dependency to a copy of `pyproject.toml`, run the
  test alone, confirm it fails on the assertion, restore, and diff (the mutation procedure
  in `CLAUDE.md`'s Run section).
- **Open questions:** Should the version floors be pinned too, or only the names? Names
  only: the floors are already explained in `pyproject.toml`'s comments and move with
  upgrades.
- **Size:** S · **Status:** planned

### 13. Client-side export

- **What & why:** Retire Static PNG mode and its remote service. Load Highcharts'
  `exporting` and `offline-exporting` modules in `build_chart_html`, which adds the chart's
  ☰ menu with PNG / SVG / JPEG downloads generated **in the browser**. This removes:
  - the export server, the last network dependency besides the CDN;
  - its failure paths (unreachable, HTTP 4xx/5xx) and `explain_export_failure`;
  - the interactive-versus-PNG mismatches, including the `CHART_PNG_WIDTH = 800` workaround,
    because there is only one renderer;
  - the render-mode selector, one fewer control.

  It goes before #5 because it deletes code that #5 would otherwise have to thread its
  `style=` through (`build_chart_png` and its cached wrapper).
- **Touches:** `highcharts_builder.py` (module scripts, an `exporting` block in the
  options, `build_chart_png` and `explain_export_failure` removed), `streamlit_app.py` (the
  render-mode selector, the static branch, `cached_chart_png`), the tests that cover static
  mode and the cache layer (`_CACHE_LAYER` drops to two renderer wrappers),
  `CLAUDE.md` (the PNG path in the flow diagram, `CHART_PNG_WIDTH`, the export-server
  conventions), `docs/decisions.md` (an entry for why the mode was retired), and the
  export-server mentions in `NOTICE` and `README.md` (its Static mode description, its
  network-requirements note and its License section). Change `NOTICE` and the README's
  License section **together**: `tests/test_packaging.py` keeps them in sync.
- **Verify by rendering:** the ☰ menu and its dropdown must be themed dark through
  `_themed`, and the **downloaded** PNG must come out dark too: the exporting module
  re-renders the chart for the file, so check the file, not only the screen. Check both
  browser colour schemes (the `color-scheme` pin).
- **Open questions:**
  - The iframe is sandboxed. Do downloads started from inside it work in Chrome, Firefox
    and Safari, or does `st.iframe` need a sandbox permission it does not grant? Test this
    first; if downloads are blocked, the item is not viable as written.
  - Some types load extra modules (sankey, sunburst, gauge and so on). Does
    `offline-exporting` export all 30 types without falling back to the export server?
    The fallback must be switched off (`exporting.fallbackToExportServer: false`), or the
    remote service quietly comes back.
  - Keep a server-side PNG option for users who can't run JS? No: the lightweight answer is
    to retire it entirely.
- **Size:** S–M (mostly deletion, plus a render check) · **Status:** planned

### 5. Style controls

- **What & why:** This is the feature that makes the app an editor. Controls for: Y-axis
  title, X-axis title, legend on/off and position, data labels on/off, stacking
  (`normal`/`percent`) for column/bar/area, a logarithmic Y, and a reference line (from #6).
- **Step zero, a decision:** pass all of these as **one** frozen, hashable `ChartStyle`
  dataclass under a single `style=` kwarg, not one kwarg each. As separate kwargs, every
  control costs three cache wrappers and three call sites (the kwarg rule in `CLAUDE.md`);
  as one object, the wrappers change once, `_FORWARDED` derives the new name on its own,
  and each later control is one field plus one widget. Write this up in `decisions.md`
  *before* the code, since every future control inherits it.
- **Touches:** `highcharts_builder.py` (`ChartStyle`, applied in or beside `_themed`), the
  sidebar's Chart section, the three renderer wrappers (once), the kwarg docs in
  `CLAUDE.md`.
- **Open questions:**
  - Which types each control applies to. Stacking means nothing to a pie, and log scale
    cannot show zero or negative values. Should an inapplicable control be hidden, or shown
    disabled?
  - Does `ChartStyle` count as a tenth row in the kwarg table, or as the gauge family's kind
    of non-column kwarg? The docs-count tests read the builders' signatures, so they will
    ask.
  - Do the style values go into the generated config/export (#2)? They should, since they
    are part of the chart.
- **Size:** M · **Status:** planned

### 15. Embeddable outputs: HTML, JS, JSON

- **What & why:** Let a user take the chart *out* in the three forms other pages use, each
  of which works when pasted somewhere else. Today none of them does:
  - **HTML:** `build_chart_html` returns a full document (`<html>`, `<head>`, `<body>`),
    which works as a standalone file or in an iframe but cannot be pasted into a page.
  - **JS:** `to_js_literal` wraps the call in `document.addEventListener('DOMContentLoaded',
    …)`. Pasted into a page that has already loaded (as most site editors insert content),
    that event has already fired and the chart **never draws**, with no error. Its fixed
    `'hc_chart'` id also collides when one page holds two charts.
  - **JSON:** not produced. `json.dumps(build_options(...))` raises
    `TypeError: EnforcedNullType is not JSON serializable` on any chart with a gap in its
    data (checked with one `NaN`).

  The builder emits **no JavaScript callback functions**, so the options are pure data and
  JSON loses nothing.
- **Design:**
  1. **JSON is the canonical output.** A pure `build_chart_json(...)` serializes the
     options with `EnforcedNull` written as `null` and `allow_nan=False`, so a bare `inf` or
     `NaN` raises instead of shipping.
  2. **JS is built from the JSON**, not from `to_js_literal`: `Highcharts.chart(el, <json>)`.
     JSON is valid JavaScript, so this output cannot hit either of the
     [unquoted-string bugs](decisions.md#the-strings-highcharts-core-emits-unquoted). It
     quotes the text correctly rather than editing it, so it does not break the rule against
     changing what the user typed. It runs immediately, with no `DOMContentLoaded` wrapper.
  3. **HTML has two variants from one function:** a **snippet** (script tags, a `<div>`
     with a unique or user-chosen id, the JS above, and the `color-scheme` pin limited to
     that chart so it cannot restyle the host page) and the **full page** (folded in from
     [#1](#1-download-the-chart-as-html): the same snippet in a document skeleton, for a
     standalone file). CDN-linked only, so both need a network connection to open; an
     inlined-JS variant is out (a large file and a licence question, see the dependency rule
     under [Direction](#direction-a-lightweight-chart-editor)).
  4. **One Export panel in the app** replaces the "Show the generated Highcharts config"
     toggle: tabs for HTML / JS / JSON / Python ([#2](#2-export-as-python)), each an
     `st.code` block (it has a copy button) plus an `st.download_button`. The panel stays
     behind a toggle so nothing is built until asked, the reason the current toggle exists.
- **Touches:** `highcharts_builder.py` (`build_chart_json`, the snippet builder, and
  `build_chart_html` rebuilt on top of them), `streamlit_app.py` (the Export panel and its
  cached wrappers, forwarded by keyword like the renderer wrappers), tests, `CLAUDE.md`
  (the public API block and the flow diagram).
- **Tests:**
  - A **sweep** over every supported type: the JSON output passes `json.loads`, and the
    row-less and non-finite frames still serialize. Extend the existing sweeps rather than
    writing per-type tests.
  - The unquoted-string sweep's two cases, run against the new JS output, must come out
    **quoted**. The test pinning the library bug in `to_js_literal` stays as it is: the bug
    is still there, only this output no longer goes through it.
  - **Verify by rendering:** paste the snippet into a plain page *after* load (inserted by a
    script) and confirm it draws; put two snippets on one page and confirm both draw.
- **Decisions:** see [below](#decisions-for-15).
- **Size:** M · **Status:** planned

#### Decisions for #15

Settled on 2026-10-07:

- **Script tags: check first.** The snippet loads the CDN scripts only if they are
  missing, then draws, so pasting several snippets on one page is safe. The check has to
  be **per module**, not only `window.Highcharts`: a sankey snippet pasted after a line
  snippet finds Highcharts already loaded but still needs `modules/sankey.js`.
- **JSON: standard-library `json`** over the `build_options` dict, with `EnforcedNull`
  written as `null` and `allow_nan=False`. Not `chart.to_json()`. Charts still pass through
  `highcharts-core` (`make_chart` validates them) everywhere else.
- **The app's own iframe stays on `to_js_literal` for now.** Switching it is
  [#16](#16-switch-the-apps-iframe-to-the-json-built-js), deferred, so #15 only changes the
  exports.
- **Container id: generated, overridable.** By default, a stable id derived from the
  options (e.g. `hc-3f9a`), so the same chart always gets the same id; an optional text box
  sets your own to match an existing `<div>`. Two *identical* charts on one page would share
  an id, which is the case the override is for.

### 2. Export as Python

- **What & why:** Add a copyable `make_chart(...)` call that reproduces the current chart
  with the public API, as the Python tab of [#15](#15-embeddable-outputs-html-js-json)'s
  Export panel. This turns the app into a way to *learn* `highcharts-core`, not only to use
  it. (The JSON half of this item moved to #15.)
- **Touches:** a pure `python_snippet(...)` helper in `highcharts_builder.py` (testable:
  `exec` the snippet against the sample frame and compare the options it produces).
- **Open questions:** Building this after #5 means the snippet includes
  `style=ChartStyle(...)` from the start. Should the snippet embed the data, or assume a
  `df` the user already has? Assuming `df` keeps it short; embedding it makes it runnable.
- **Size:** S · **Status:** planned

### 8. Edit data in place

- **What & why:** Swap the read-only `st.dataframe` preview for `st.data_editor`, so a user
  can fix a typo or try a value without re-uploading.
- **Touches:** `streamlit_app.py`. The edited frame must replace `df` *before* the pickers
  and the gate run.
- **Open questions:** Should edits survive a dataset switch (probably not)? Should adding
  and deleting rows be allowed, or only editing cells? Cells only is the lightweight answer.
- **Size:** S · **Status:** planned

## Folded

### 6. Reference line

Folded into [#5](#5-style-controls) as one more `ChartStyle` field: a horizontal line at a
typed value via `yAxis.plotLines`, for cartesian and polar types. Its colour must alias an
existing palette or chrome colour (no new colours). The open question carries over: should
it be a fixed value, or computed (mean/median)? A fixed value is the lightweight answer.

### 1. Download the chart as HTML

Folded into [#15](#15-embeddable-outputs-html-js-json) as its **full page** variant. The
decision made here carries over: CDN-linked only, no inlined Highcharts JavaScript.

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
- **Depends on:** [#13](#13-client-side-export). With the export server gone, nothing in
  the app needs a server-side network call.
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
