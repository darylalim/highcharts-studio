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
  The same applies to **network** dependencies: the app relies on the Highcharts CDN and
  export server today, should never add a third, and [#13](#13-client-side-export) takes it
  down to the CDN alone. Dev tools (`pytest`, `ruff`, `ty`, `watchdog`)
  never ship to users and are outside this rule. Enforced by [#12](#12-pin-the-runtime-dependency-set).

**Client side, in two steps.** The chart is already drawn in the browser in interactive
mode; only Static PNG mode sends it to a remote service (`export.highcharts.com`). Moving
the PNG into the browser ([#13](#13-client-side-export)) is small and planned. Running the
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
importable on its own ([#13](#13-client-side-export) is the one planned item that does
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
| 5th | 19 | [Date the real-world samples](#19-date-the-real-world-samples) | S | planned |
| 6th | 13 | [Client-side export (retire Static PNG mode)](#13-client-side-export) | S–M | planned |
| 7th | 23 | [Host a public demo on Streamlit Community Cloud](#23-host-a-public-demo-on-streamlit-community-cloud) | S | planned |
| 8th | 18 | [A stackable sample](#18-a-stackable-sample) | S | planned |
| 9th | 5 | [Style controls (with the reference line)](#5-style-controls) | M | planned |
| 10th | 17 | [Group the chart-type picker by family](#17-group-the-chart-type-picker-by-family) | M | planned |
| 11th | 15 | [Embeddable outputs: HTML, JS, JSON](#15-embeddable-outputs-html-js-json) | M | planned |
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
- **Checked 2026-10-07:** downloads from inside the iframe are permitted. Streamlit's
  iframe sandbox (in the installed `streamlit` frontend) includes `allow-downloads`, with
  `allow-scripts` and `allow-same-origin`. This was the condition that could have made the
  item unworkable.
- **Decided:** no server-side PNG option is kept for users without JS. The mode is retired
  entirely.
- **Check when building:**
  - That a download from the ☰ menu actually lands in Chrome, Firefox **and Safari**
    (the sandbox permits it; the browsers have to agree).
  - That `offline-exporting` exports all 30 types in the browser, with the fallback switched
    off (`exporting.fallbackToExportServer: false`); otherwise the remote service quietly
    comes back for any type it cannot handle.
- **Shipping:** removes public API (`build_chart_png`, `explain_export_failure`), so its
  changelog section has a **Removed** heading naming both (see Shipping in the Legend).
- **Size:** S–M (mostly deletion, plus a render check) · **Status:** planned

### 23. Host a public demo on Streamlit Community Cloud

- **What & why:** A lightweight editor nobody can reach is half done. Deploy the app as a
  **public, non-commercial demo** on Streamlit Community Cloud and link it from the README.
  Local (`uv run streamlit run streamlit_app.py`) stays the documented way to run it, and
  the only way for anyone who forks it.
- **Decided (2026-10-07):** Community Cloud, non-commercial. It fits with almost no work:
  the app reads no secrets and no environment variables, and its runtime set is three
  packages. The rejected options, so they are not re-proposed without new information:
  - **Local only:** safe, but leaves the editor loop finished with nowhere to use it. It
    stays as the fallback, not the answer.
  - **Static hosting via stlite ([#14](#14-spike-run-the-app-in-the-browser-stlite)):**
    every visitor downloads tens of MB before the first chart, which works against
    "lightweight", and it waits on an unrun spike. If that spike ever shows a fast enough
    first load, it can replace this deployment later; it does not block it.
- **Licence:** Highcharts JS and `highcharts-core` are free for personal and non-commercial
  use, and a public deployment is still a use of them. This demo qualifies only while it
  stays non-commercial (no ads, no paid tier, not a company product). If that changes, the
  deployment comes down until a commercial licence is in place. The README's `## License`
  section and `NOTICE` already put licensing on whoever deploys; the live-demo section says
  the demo is non-commercial.
- **Depends on:** [#13](#13-client-side-export). With Static PNG mode retired, the hosted
  app's only outside dependency is the Highcharts CDN, so a visitor's render no longer
  calls `export.highcharts.com`.
- **Touches:** `README.md` (a live-demo link near the top and a short deploy section), and a
  deploy config only if Community Cloud needs one.
- **Check when building:**
  - Whether Community Cloud installs from `pyproject.toml` + `uv.lock` directly. If it needs
    a `requirements.txt`, that is a second copy of the dependency list:
    [#12](#12-pin-the-runtime-dependency-set) must then pin the two together, or the copy
    drifts.
  - That the deployment runs on Python 3.12 (set in the app's advanced settings), the
    interpreter the tests use.
  - That the interactive chart loads inside Community Cloud's page (the CDN is fetched by
    the viewer's browser, not the server, so this is a browser check).
- **Known limit:** free apps sleep after a period of inactivity, so the first visitor after
  a quiet spell waits for a cold start. Say so in the README rather than work around it.
- **Shipping:** no new app behaviour, so a **patch** bump (see Shipping in the Legend).
- **Size:** S · **Status:** planned

### 21. Pin the Highcharts JS version

Done in 0.20.5: `HIGHCHARTS_JS_VERSION` (13.1.1, the release already in use) and
`_pin_script_tags` in `highcharts_builder.py`. For #13 and #15: their new modules (`exporting`,
`offline-exporting`, `accessibility`) were checked to load at 13.1.1 from a browser, and they
are pinned automatically, since every script `get_script_tags` emits goes through the rewrite.
The reasoning and the upgrade procedure:
[`decisions.md`](decisions.md#highcharts-js-one-pinned-release).

### 19. Date the real-world samples

- **What & why:** 24 of the 26 samples are plainly invented. Two carry **real names with
  undated figures**:
  - *Company market cap (treemap)*: Apple 3400, Microsoft 3100, Nvidia 2900… in $ billions;
  - *Country economics (bubble)*: GDP per capita, life expectancy and population for real
    countries (they look like 2022–23 figures).

  Inside the app that is harmless, but once a chart can be copied onto another page
  ([#15](#15-embeddable-outputs-html-js-json)), its numbers travel with it and can be
  published as if current. Keep the familiar names (they are what makes the two charts
  readable) and say what the figures are: illustrative, and roughly when.
- **Touches:** `sample_data.py` (the two `SAMPLES` labels and docstrings), and any doc that
  names them.
- **Constraint:** the date goes **outside** the parentheses, e.g.
  *Company market cap, ~2024 (treemap)*. The test helper `_pick_sample` finds a type's
  sample by the exact substring `"(treemap)"`, so *(treemap, illustrative ~2024)* would
  break every test that uses it.
- **Check when building:** which year to state for each. Read the figures against a source
  once and write the year they match. "Illustrative" goes in the docstring rather than the
  label, which is narrow.
- **Size:** S · **Status:** planned

### 18. A stackable sample

- **What & why:** #5's main new control is stacking, and no sample can show it honestly.
  The only multi-series Tier 1 sample is *Monthly revenue vs cost*, and stacking it is
  **meaningless**: cost is not a part of revenue, so the stacked total measures nothing (and
  percent stacking is worse). Add a sample whose series **are** parts of a whole, e.g.
  *Monthly revenue by channel*: a `month` column, then 3–4 channels (online, retail,
  wholesale, partner) over 12 months. Stacked, it shows the total; percent-stacked, the mix.
  It is the sample #5 is verified against by rendering, so it comes first.
- **Touches:** `sample_data.py` (a new factory and `SAMPLES` entry, leading with the
  category column per the [first-column rule](chart-types.md#the-sample-datasets)), the
  sample tests, and the sample's rationale in `docs/chart-types.md`.
- **Constraints:**
  - **Added alongside the landing dataset, not replacing it.** Many tests read the first
    sample (`next(iter(SAMPLES.values()))`) and the AppTests expect its `revenue` and `cost`
    columns.
  - **Its label must not capture another type's tests.** `_pick_sample` takes the *first*
    `SAMPLES` key containing `"(column)"`, `"(area)"` and so on, so a label like
    *(column)* would silently become the sample for every column test. Label it
    *(stacked column/area)*, which matches no single type.
- **Decided:** no sample for the log-scale control. Log only helps when values span orders
  of magnitude, and the widest sample today (*Company market cap*) spans about 9×; rather
  than a second sample, #5 tests log scale on made-up data.
- **Size:** S · **Status:** planned

### 5. Style controls

- **What & why:** This is the feature that makes the app an editor. Controls for: Y-axis
  title, X-axis title, legend on/off and position, data labels on/off, stacking
  (`normal`/`percent`) for column/bar/area, a logarithmic Y, and a reference line (from #6).
- **Step zero, a decision:** pass all of these as **one** frozen, hashable `ChartStyle`
  dataclass under a single `style=` kwarg, not one kwarg each. As separate kwargs, every
  control costs a change to each renderer cache wrapper and its call site (three today, two
  after [#13](#13-client-side-export); the kwarg rule in `CLAUDE.md`);
  as one object, the wrappers change once, `_FORWARDED` derives the new name on its own,
  and each later control is one field plus one widget. Write this up in `decisions.md`
  *before* the code, since every future control inherits it.
- **Scope: Tier 1 first.** The controls ship for the [Tier 1](#chart-tiers) types and are
  **hidden** for every other type; Tier 2 types gain them one control at a time, where the
  control means something for that type. A pure `style_controls_for(chart_type)` in the
  builder answers which controls a type takes, so the sidebar and the tests read one table.
- **Requirement: hiding a control must not lose its value.** Streamlit drops the stored
  value of any keyed widget a run does not draw. So: set a Y-axis title on a line chart,
  switch to pie (the control is hidden), switch back, and the title is **gone**. That breaks
  `CLAUDE.md`'s rule that a value may be dropped when it stops being *valid*, never when it
  merely stops being *drawn*. Add the style controls' keys to `_KEYED_PICKERS` so
  `keep_picker_state()` keeps them, and add an AppTest that sets a style, switches to a type
  that hides it and back, and asserts it survived. Verify by breaking it (drop the keys from
  `_KEYED_PICKERS`).
- **Touches:** `highcharts_builder.py` (`ChartStyle`, applied in or beside `_themed`, plus
  `style_controls_for`), the sidebar's Chart section, `_KEYED_PICKERS`, the renderer
  wrappers (once; two of them after [#13](#13-client-side-export) retires the PNG one), the
  kwarg docs in `CLAUDE.md`, and `README.md`'s description of the controls.
- **Decided:**
  - **`style` is not a column kwarg.** It is a setting, like the gauge family's `agg` and
    `dial`, so it gets no row in `CLAUDE.md`'s kwarg table. The tests settle this
    mechanically: they define the column kwargs as `_FORWARDED` minus `("agg", "dial")`, so
    an unexcluded `style` would be counted as a **tenth column kwarg** and fail the docs-count
    tests. Add it to that exclusion, and update `CLAUDE.md`'s line about the gauge family
    taking "the two that are **not** column names" (it becomes three, and no longer
    gauge-only).
  - **Style values go into the exports** ([#15](#15-embeddable-outputs-html-js-json),
    [#2](#2-export-as-python)), since they are part of the chart.
  - **Log scale with values ≤ 0: disable, with the reason.** A log axis cannot show zero or
    negative values, so when the selected Y data has any, the log toggle stays visible but
    **disabled**, with help text saying why ("Y has values ≤ 0"), and re-enables when the
    data allows. Settled 2026-10-07. Rejected: hiding it (the user is not told why, and the
    value needs `_KEYED_PICKERS` to survive) and allowing it with a warning (the chart drops
    the points it cannot show, quietly misrepresenting the data). A disabled widget is still
    drawn, so it keeps its value with no extra code; the builder must still refuse a log
    axis on such data, so a stale `True` can never reach the chart. Test both: the AppTest
    sees the toggle disabled, and the builder ignores or rejects `log=True` on data ≤ 0.
- **Size:** M · **Status:** planned

### 17. Group the chart-type picker by family

- **What & why:** A selectbox of 30 types makes the app look heavier than it is. A
  two-step picker (a **family**, then the **type** within it) shows the common charts first
  without removing any. Six families, every type in exactly one, each family's most common
  type first:

  | Family | Types |
  |---|---|
  | Basic | line, spline, area, areaspline, column, bar, scatter, bubble, radar |
  | Part of whole | pie, treemap, funnel, pyramid |
  | Comparison | waterfall, bullet, dumbbell, columnrange, arearange, heatmap, boxplot, variwide |
  | Flow & hierarchy | sankey, dependencywheel, networkgraph, organization, sunburst |
  | Time | xrange, timeline |
  | Gauge | gauge, solidgauge |

  The app opens on Basic → line, as today.
- **Why after #5:** both need a per-type table in the builder (`style_controls_for`, and
  the family map here), so the second one copies the pattern the first one set.
- **Touches:** `highcharts_builder.py` (a `CHART_FAMILIES` map, pure), `streamlit_app.py`
  (the family pills above the chart-type selectbox, and its help text), the AppTests that
  switch chart type, `CLAUDE.md`'s description of the selector, and `README.md`'s.
- **Tests:**
  - Every supported type is in **exactly one** family, so a future type cannot be left
    unreachable (the same safeguard as the docs-count tests).
  - One `_select_chart_type(app, chart_type)` helper sets the family and then the type, and
    every AppTest that switches type uses it (the `_pick_sample` pattern), so the family step
    is one change rather than one per test.
  - The keyed-picker AppTests must still pass: a family change is a type change, and the X
    and Y pickers must keep their values through it (the widget-identity rules in
    `CLAUDE.md`'s Test section). Verify by breaking it.
- **Decisions:** see [below](#decisions-for-17).
- **Size:** M · **Status:** planned

#### Decisions for #17

Settled on 2026-10-07:

- **Family control: `st.pills`, single select.** One click, it wraps in the narrow sidebar,
  and the app already uses pills for the Y picker. Not `st.segmented_control` (the app uses
  it for two-option choices; six segments crowd the sidebar), and not a selectbox (two
  dropdowns in a row, and a new selectbox above the type selector would shift the 39
  positional `app.selectbox[n]` lookups in the tests). **Check when building:** whether
  `st.pills` takes `required=True` as `segmented_control` does here; if not, handle the
  deselected (`None`) case so the control can never show empty while a chart renders.
- **On a family change, select the family's first type.** This needs no code: the
  chart-type selectbox has no `key=`, so when its options change Streamlit gives it a new
  identity and it resets to the first option. Remembering the last pick per family was
  rejected: it needs new session state that `keep_picker_state()` would also have to cover,
  against the lightweight direction. That is why each family lists its most common type
  first.
- **Six families, not seven.** Heatmap colours a grid of categories by value, which is a
  comparison rather than a distribution; moving it would leave a *Distribution* family with
  only boxplot, so the two merge into *Comparison*. If the freeze in
  [#10](#10-new-chart-types) lifts and `histogram` arrives, *Distribution* can return with
  two members.
- **Help text per family.** The chart-type selectbox's help is one tooltip with 30 bullets
  today; it shows only the selected family's entries instead.
- **Order the samples by family.** The Dataset dropdown lists 26 samples in the order they
  were added. Reorder the `SAMPLES` registry to follow the six families, Basic first, so
  the list reads in the same groups as the picker. *Monthly revenue vs cost* must stay the
  **first** entry: it is the landing dataset, and tests read it as
  `next(iter(SAMPLES.values()))`. A dict reorder, no other code.

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
     `NaN` raises instead of shipping. It also writes `<`, `>` and `&` as `\u003c`,
     `\u003e` and `\u0026`: still valid JSON with the same values, and it can never close a
     `<script>` element on the page it is pasted into (the embed form of
     [#20](#20-escape-script-in-the-charts-js)).
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
     It also carries:
     - a one-line **licence note**: Highcharts is free for non-commercial use, and a
       commercial site needs its own Highcharts licence. `NOTICE` covers this app, not a
       user's page;
     - a **size warning** when the export is large, since the snippet carries every row of
       data inline (a 50,000-row CSV makes a multi-MB paste).
- **Touches:** `highcharts_builder.py` (`build_chart_json`, the snippet builder, and
  `build_chart_html` rebuilt on top of them), `streamlit_app.py` (the Export panel and its
  cached wrappers, forwarded by keyword like the renderer wrappers), tests, `CLAUDE.md`
  (the public API block and the flow diagram), and `README.md` (the Export panel).
- **Tests:**
  - A **sweep** over every supported type: the JSON output passes `json.loads`, and the
    row-less and non-finite frames still serialize. Extend the existing sweeps rather than
    writing per-type tests.
  - The JS output **parses**, for every type: `esprima.parseScript()` (already installed with
    `highcharts-core`, so no new dependency) proves structure rather than matching text, and
    catches the whole unquoted-string class by construction.
  - A `</script>` label stays inside the JSON for every type (the #20 sweep, run on the
    embed outputs).
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

- **CDN version: pinned, in the app and the exports alike**, by
  [#21](#21-pin-the-highcharts-js-version). What the app shows is then exactly what a
  snippet embeds, and a pasted snippet cannot change when Highcharts releases a new major.
- **Background: dark, as the app shows it.** A dark chart reads as a self-contained card on
  a light page, and the "one mode" rule and its palette tests stay as they are. Rejected: a
  light export theme (it partly reverses
  [the light-mode removal](decisions.md#light-mode-and-its-removal) and needs a second set of
  chrome colours that pass the colour-blindness tests), a user toggle (that, plus a control),
  and a transparent background (the chart's light text would be unreadable on a light page).
- **Accessibility module: in embeds only.** Snippets load `modules/accessibility`, through
  the same per-module check as every other module; the app's own preview does not. Embeds
  are where charts reach the public, and without the module Highcharts logs a warning in
  the host page's console.
- **Size warning at 1 MB** of export text. Well past every sample, and around where a pasted
  snippet starts to slow a page or hit a CMS field limit.

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
