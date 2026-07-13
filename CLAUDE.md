# CLAUDE.md

## Project Overview

`highcharts-studio` is a Streamlit application for building data visualizations
with Highcharts. Every chart is produced by the Highcharts for Python toolkit
(`highcharts-core`) — the app uses no native Streamlit charts.

## Structure

- `streamlit_app.py` — the Streamlit UI: data source (sample datasets or CSV
  upload), chart-type/column controls (pills for the Y series, falling back to
  `st.multiselect` on wide CSVs, plus the four type-specific extra column
  selectors — Size (Z) for bubble, Target (to) for sankey, Parent for sunburst, End
  for xrange),
  caching, a KPI metric row (its third metric adapts to the chart type — series
  plotted, or, for the one-series types, the mark count from the builder's
  `count_marks`: cells for a heatmap, tiles for a treemap, flows for a sankey,
  boxes for a boxplot, steps for a waterfall, sectors for a sunburst, bars for an
  xrange — sourced there
  rather than recomputed
  here so it can't drift from what the chart draws; waterfall's and sunburst's are the
  two that *exceed* their drawable mark count, by one, since each appends a mark the
  frame never held (a total bar, a root sector) — not necessarily their row count,
  since an undrawable label drops its row; xrange appends nothing, so its count is
  exactly its surviving rows;
  membership of the `MARK_METRICS` dict is what makes a type count-adaptive, so the
  KPI stays one branch however many such types there are), the
  render-mode
  selector (interactive iframe / static PNG), reading the active light/dark theme
  (`st.context.theme.type`) so the charts render theme-aware, the chart embed,
  and a toggle that reveals the generated Highcharts config (JS).
  The **no-plottable-columns gate** runs *below* the chart-type selectbox and is
  type-aware, which xrange forced: every other type needs a NUMBER, but xrange's
  start/end are coordinates and may be dates — and a date column is object dtype, so
  the canonical Gantt CSV (`task,start,end`, all dates) has *no* numeric columns at
  all and the old `select_dtypes("number")` gate `st.stop()`ped it before the picker
  was even drawn. Xrange's Start/End pickers are likewise sourced from the builder's
  `coordinate_columns`, not from `numeric_cols` (which cannot see a date) nor from
  `df.columns` (which would offer a column of task names the builder can only reject).
- `highcharts_builder.py` — pure, Streamlit-free helpers that turn a DataFrame
  into a Highcharts options `dict`, a `Chart`, and embeddable HTML or PNG bytes,
  plus `explain_export_failure()`, which turns a failed PNG export into a message
  naming the actual cause (it owns the export-server relationship, so it owns the
  diagnosis; duck-typed on `exc.response.status_code` rather than importing
  `requests`, which this project never declares), `explain_tree_error()`, its sunburst
  counterpart — the builder owns the hierarchy, so it owns the diagnosis — which returns
  the very message `build_options` raises for a malformed tree, so the app's warning and
  the exception it stands in for cannot drift apart (needed because the interactive path
  does *not* catch builder errors, and a cyclic CSV is the one such error a user can reach
  just by uploading a file), `explain_xrange_error()`, the same contract for a *column
  pair* rather than a tree. It reports two contradictions — a start/end column that can place a
  bar on no axis, and two that disagree about *which* axis — of which only the **second** is
  reachable from the app, since `coordinate_columns` keeps a column of task names out of the
  pickers entirely; the first is reachable only through the pure builder API. (So xrange adds
  exactly one app-reachable builder error, not two: a *date start beside a numeric end*.)
  Then `coordinate_columns()`, the
  builder's own answer to "which columns can place a bar on an axis" — exported so the
  app's Start/End pickers cannot offer a column the builder would refuse, which is the
  can't-drift rule applied to *which options appear in a widget* — and `count_marks()`, which
  returns how many marks `build_options` will draw (a heatmap's cells, a treemap's
  tiles, a sankey's flows, a boxplot's boxes, a waterfall's steps, a sunburst's sectors, an
  xrange's bars)
  for the app's KPI
  row — reusing the same `_label_ok`/`_plottable` drop predicates so the count can't
  drift from the chart (sunburst and xrange go further and reuse their *whole* build, for
  two different reasons: sunburst's drops are not a per-row mask at all, since a node's fate
  depends on its *ancestors* and its *descendants*; while xrange's drops *look* per-row but
  are read through a **column**-level fact — the axis kind — and `build_options` reaches its
  branch on the `_label_ok`-*filtered* frame while `count_marks` runs on the *raw* one, so a
  predicate-only reuse would sniff a different axis than the chart drew).
  Independently importable and unit-testable.
- `sample_data.py` — pure (Streamlit-free) built-in sample datasets and the
  `SAMPLES` registry the app offers when no CSV is uploaded.
- `tests/test_smoke.py` — builder unit tests (every chart type, the missing-data
  and scatter/bubble edge cases, radar's polar-line shape, heatmap's colorAxis
  value matrix, treemap's value-sized tiles, sankey's node-link flows, boxplot's
  aggregated Tukey distributions, waterfall's appended total and semantic bar
  colors, sunburst's assembled hierarchy (synthesized ids, valueless internal nodes,
  the dropped dangling parent vs. the raised cycle, and the appended root), xrange's
  interval bars (the date-vs-number coordinate sniff and its two silent traps — a numeric
  column reaching a date parser, and an unnormalized epoch view — plus the kept milestone,
  the dropped backwards bar, and the per-lane hue), the brand
  palette, the validation
  guards including bubble's required size column, sankey's required and distinct
  target column, sunburst's required and distinct parent column, xrange's required end
  column (distinct from the *start* column, not from `x_col`), and the
  heatmap/boxplot/waterfall x-in-y rule, and
  an end-to-end pass driving every supported type through `Chart.from_options` /
  `to_js_literal`) and `sample_data` unit tests, plus headless `AppTest`
  interaction tests.
- `tests/test_hooks.py` — unit tests for the `.claude/hooks/` scripts: the pure
  decision functions (path guard, `.py` routing, git-dirty detection) plus a
  black-box check of the exit-code contract for `guard_paths.py` and
  `post_edit_py.py`.
- `tests/test_packaging.py` — unit tests guarding the licensing metadata: the
  `pyproject.toml` SPDX `license`/`license-files` fields, the `LICENSE` file's
  pristine MIT text (nothing appended, so GitHub detects it as MIT), and the
  `NOTICE` third-party notice naming both proprietary layers (Highcharts
  JS/export server and `highcharts-core`), kept in sync with the README
  `## License` section — plus the README's header badges (pinned to the
  `pyproject.toml` license and Python/Streamlit version floors) and its
  `## Contents` table of contents (pinned to the real `##` section headings).
- `.streamlit/config.toml` — project Streamlit theme (brands the app shell in
  both light and dark via `[theme.light]`/`[theme.dark]`, which unlocks the
  in-app light/dark toggle). The chart colors are themed separately (see
  Conventions) since charts render in an iframe the shell theme can't reach.
- `.claude/settings.json` + `.claude/hooks/*.py` — committed Claude Code hooks
  that mirror the CI gates (see Hooks). `.claude/settings.local.json` holds
  per-developer overrides and is gitignored.
- `pyproject.toml` — dependencies + the `dev` group, the project license (MIT,
  via the PEP 639 `license`/`license-files` fields), and the Ruff/ty config (see
  Lint & format, Type check).
- `.github/workflows/ci.yml` — GitHub Actions: three jobs (pytest, Ruff
  lint/format, ty) that `uv sync --locked` then run the same gates the hooks
  mirror, on every push to `main` and every PR.
- `LICENSE` — MIT for this project's own code, kept *pristine* (no text
  appended) so GitHub's license detector classifies the repo as MIT rather than
  "Other".
- `NOTICE` — the third-party notice, split out of `LICENSE` for that reason:
  the two proprietary layers it renders with (Highcharts JS/the export server,
  and the `highcharts-core` wrapper) are separately licensed and not covered by
  the MIT grant. Both files are declared to packaging tools via
  `pyproject.toml`'s `license`/`license-files`; guarded against drift by
  `tests/test_packaging.py`.

## How a chart is built

`highcharts_builder.py` exposes the public helpers the app uses:

```python
# build_options() -> Chart.from_options() -> set container, in one call:
chart = make_chart(df, chart_type, x_col, y_cols, title=title)

# interactive: get_script_tags() + to_js_literal() wrapped as HTML for st.iframe
html = build_chart_html(df, chart_type, x_col, y_cols, height=height, title=title)

# static: rendered server-side to PNG bytes via the export server, for st.image
png = build_chart_png(df, chart_type, x_col, y_cols, title=title)

# ...and, when that raises, why — a build error, an unreachable server, or an HTTP
# answer (a 4xx rejection is worth saying out loud: the server is plainly reachable).
message = explain_export_failure(exc)  # plain markdown; the module stays Streamlit-free
```

All three helpers take an optional `dark=` flag (default `False`) that themes the
chart chrome (background/text/axes/gridlines/tooltip) for dark mode; the app
derives it from `st.context.theme.type` and threads it through the cached
renderers. Bubble charts also take a `size_col=` naming the numeric column that
drives each marker's area (required for `bubble`, raising `ValueError` if
omitted; ignored by the other types), threaded through the same renderers,
sankey charts a `target_col=` naming the destination-node column (required for
`sankey`, and raising `ValueError` if omitted or equal to `x_col`; likewise
ignored by the other types), threaded the same way, sunburst charts a
`parent_col=` naming the parent-label column (required for `sunburst`, raising
`ValueError` if omitted or equal to `x_col` — and, unlike the other two, also raising
when the column it names does not describe a *tree*: see `explain_tree_error`), and
xrange charts an `end_col=` naming the column each bar ends at (required for `xrange`,
raising `ValueError` if omitted or equal to the *start* column — `y_cols[0]`, not
`x_col`, which is the one collision of the four that is not against `x_col` at all — and,
like sunburst, also raising when its columns cannot place a bar on one axis: see
`explain_xrange_error`).

Supported chart types: `line`, `spline`, `area`, `areaspline`, `column`, `bar`,
`pie`, `scatter`, `bubble` (scatter plus a `size_col` marker-size dimension),
`radar` (a polar spider/web line chart — shares the cartesian category-X data
shape, rendered as a `line` with `chart.polar` on polar axes), `heatmap` (a
category-X × category-Y value matrix — the wide-form category-X data
reinterpreted as `[x, y, value]` cells colored by a sequential `colorAxis`, with
`x_col`'s values as the X categories and each `y_cols` column *name* as a Y
category, pulling in the `modules/heatmap` module), `treemap` (nested rectangles
sized by value — the same single-value data shape as `pie`: `x_col` labels each
tile and the first `y_cols` column gives its `value`, but tiles are colored
categorically from the palette via `colorByPoint` and laid out by the
`squarified` algorithm, dropping missing values like pie; pulls in the
`modules/treemap` module), `sankey` (a node-link flow diagram — the only type
that reads the data as *edges of a graph* rather than as series or categories:
each row is one link, from the node named in `x_col` to the node named in
`target_col`, weighted by the first `y_cols` column, encoded as
`{from, to, weight}` dicts. Rows missing any of the three are dropped like pie's
slices; a node that is both a target and a source chains the flow into a second
hop; pulls in the `modules/sankey` module. Its nodes are named by Highcharts'
default node label and each link carries its weight as a *per-link* `dataLabels`
— gated on link count like heatmap's cell labels — because highcharts-core drops
`plotOptions.sankey.dataLabels.nodeFormat` and the `format` that survives there
would label the links with the node format and blank the node names),
`boxplot` (per-category Tukey distributions — the only type whose builder
*aggregates*: every other maps rows 1:1 onto marks, but a box summarizes many rows.
The data is long/tidy — `x_col`'s values *repeat*, one row per observation — and each
distinct `x_col` value becomes one box over that group's raw `y_cols[0]` numbers,
encoded as a positional `[low, q1, median, q3, high]` 5-array matched to
`xAxis.categories` *by position*, since a `{name, low, …}` dict point collapses with
the name in the leading `x` slot. Whiskers follow `matplotlib.cbook.boxplot_stats`:
pandas' default linear quantiles, 1.5×IQR fences with *inclusive* membership (so a
zero-IQR group isn't read as all outliers), and `low`/`high` clamped to `q1`/`q3` at
both ends. Observations are cast to `float64` first (a text column raises `ValueError`,
as `float(v)` does in the pointwise branches) and reduced to the *finite* ones — an
infinity can't size a whisker and would turn the whole box to nulls, since
`iqr = inf - inf = nan`. Observations strictly beyond the fences become a second, linked
scatter series, emitted only when some exist. Groups keep first-appearance order
(`groupby(sort=False)`); a group whose observations are all missing keeps its axis
slot as an `EnforcedNull` box, while a row whose `x_col` is missing names no category
and forms no group. It shares bubble's and radar's `highcharts-more` module, and is
the one mark-styling type with *no* `_themed` hook: `plotOptions.boxplot.fillColor`
and `stemColor` are accepted by `Chart.from_options` and then silently dropped (and
`ExportServer.global_options` is no side door — it is coerced through the same model),
so the box interior can't be set at all. It falls back to Highcharts' own
`var(--highcharts-background-color)`, which the `color-scheme` pin below resolves to
white in both themes, while `colorByPoint` gives each box a palette-hued
border/whisker/median legible against that white), and `waterfall` (a cumulative
"bridge" — the category-x data shape read as signed **deltas** rather than levels, so
each bar floats where the last one ended and the chart shows how a starting value
*becomes* an ending one. `x_col` names each step and the first `y_cols` column gives
its signed change; a missing/non-finite delta keeps its axis slot as an `EnforcedNull`
(the `_num` rule, not pie's drop-the-row), because a null delta reads as "no change" —
Highcharts draws no bar and carries the running total straight through, which is
exactly true. The builder then **appends** a closing `Total` bar (`{"isSum": True}`,
which makes Highcharts sum the preceding deltas itself so the bar reaches down to zero
as a *level* rather than stacking as one more delta) — it is what makes the chart a
bridge rather than a row of floating bars, and it makes waterfall the one type whose
mark count exceeds its row count; it is appended only when there is at least one step
to sum. Bars are colored by **meaning**, not identity — green rise, red fall, brand-blue
total, read straight from `DEFAULT_COLORS` by index rather than from the *overridable*
`colors` list, the `_BOXPLOT_OUTLIER_COLOR` rule for both of its reasons (a short custom
palette can't `IndexError`, and red-means-loss is the chart's semantics, not a series'
arbitrary identity, so a custom palette must not repaint a fall green). The total's
`color` is carried **per point**, which takes the total *off the up/down scale entirely*.
Left alone, Highcharts colors a sum by its OWN sign, exactly as it colors a delta (a
positive total goes green, a negative one red — verified by rendering, not assumed); but
green does not mean the same thing on the two kinds of bar. On a delta it says "this step
added"; on the total it would say only "the end level is above zero", which a bridge that
fell 420 → 79 would earn just as cheerfully. Same hue, two claims. So the total is marked
as the different KIND of bar it is: a **level**, not a change. It labels each bar with
its delta — gated on step count like heatmap's cells and sankey's links — because unlike
column/bar (which carry no labels) a waterfall's bar floats at the running total and
encodes its value as a *length*, not a height above the axis, so no axis can be read
against it. It shares bubble's, radar's and boxplot's `highcharts-more` module, and it is
the one type needing **two** `_themed` hooks — and *neither* is the column/bar case, since
waterfall's border and connectors both default to a fixed `#333333` (measured off the
rendered PNG) rather than the background variable that resolves to white for column/bar,
so its bars are never ringed white. `borderColor`: that crisp definition line on the white
shell becomes a muddy grey ring one shade off the dark background, and buys nothing (a
waterfall's bars never touch), so it is dissolved into the background as pie/treemap/sankey
dissolve their gaps. `lineColor`: the *connector* lines — the only line Highcharts draws
*between* marks, and what makes the chart read as a running total at all — survive on the
dark background only barely, so they are lifted to the axis color), and `sunburst` (a
hierarchy drawn as concentric rings — the only type that reads the frame as an **adjacency
list**: each row is one node, named by `x_col`, placed under the node named in `parent_col`
(a blank/missing/whitespace parent means a top-level branch — the one place in the module
where a missing label is a *statement* rather than an error), and, *if it is a leaf*, sized
by the first `y_cols` column. So it is also the only type whose marks are not in the data:
the tree has to be **assembled** before anything can be drawn, which is what `_sunburst_tree`
does — and, since a node's fate depends on its *ancestors* (a dangling parent, a cycle) and
on its *descendants* (a valueless internal node lives only if a leaf under it does), it is the
one type whose drops are not a per-row mask at all. `count_marks` therefore reuses not the
drop predicates but the *whole build*, which is a stronger form of the can't-drift rule than
any other type gets: the KPI is `len(series[0]["data"])` by construction.

Node ids are **synthesized** (`n0`, `n1`, …), never taken from the labels. A label is not a
key: two rows may legitimately share one — an `Other` bucket under both Sales and Marketing —
and label-as-id would hand Highcharts two points with the same `id`, which is not a silent
mismatch but **error #31, "Non-unique point or node id"**, printed in a red band across the
chart (verified by rendering). Synthesizing makes that unreachable: CSV text lands only in
`name`, so nothing in a hostile file can collide with anything, and the twins stay two honest
sectors rather than merging into one worth a sum nobody asked for. The label-keyed shape's one
real cost is then paid exactly once, and only where it is genuinely unpayable — a duplicate
label that is *used* as a parent names no single node, and the alternatives (merge them, or
pick one and graft a subtree onto the wrong branch) are both silent lies.

That is the type's organizing split, and it is `_sunburst_tree`'s whole design: everything
wrong with an adjacency list is either **missing data**, which has a right answer and is
*dropped* — a dangling parent (with its descendants, transitively: Highcharts does not leave an
unmatched parent alone, it silently *re-parents* the child to the root, promoting an orphaned
grandchild into ring 1 and lying about the data), or a leaf value that can't size an arc — or a
**contradiction**, which has no right drawing and *raises*: a cycle, an ambiguous parent. The
two are told apart by one iterative walk up the parent chain (iterative because a 50,000-deep
chain is valid input and a 50,000-long cycle is reachable input) that simultaneously grounds
each node, drops the unreachable, and raises on a loop. Order is moot, and provably so: no node
in a cycle can ever be dangling, so dropping a dangling row can never break one. The
contradiction comes back as a **returned message**, not a raised one — that is what keeps
`count_marks` *total*, and it matters, because the app's KPI row runs *above* its guards, so a
`count_marks` that raised on a cyclic CSV would blow the page up with a traceback before the
warning explaining it could render.

`_sizable` is `_plottable` widened by one comparison, and it is the type's own predicate for a
reason: Highcharts draws no sector for a **negative** leaf *and* excludes it from its parent's
sum (verified by rendering — a `-400` leaf beside a `500` one drew nothing and left its parent
sized 500, not 100), so keeping the row would make the KPI count a mark the chart never draws.
An arc has no negative length and a part-of-whole has no negative part, so the row is dropped —
pie's and treemap's rule. Zero is *kept*: a real measurement, a zero-width sector, and it
corrupts no sum.

An internal node carries **no value**, and this is not deference to Highcharts but the only
honest option: an explicit parent value *overrides* the children-sum, so emitting a CSV's
subtotal row draws a parent whose arc disagrees with the arcs inside it (verified by rendering —
two branches each declaring `value = 1` drew as equal halves while holding 900 and 100). It
would go wrong even when the subtotal is *right*, the moment one child row is dropped: the
parent would keep claiming the full total with a child missing beneath it. Omitting it makes a
parent's arc always equal what is actually drawn under it — the discipline `count_marks`
enforces on the KPI, applied to the geometry. Its corollary is not a special case but the rule
itself (`keep(n) = the value can size an arc, OR something under n survived`): a node whose only
child was dropped *becomes* a leaf, and then its own value is what sizes it.

A **root** sector is **appended** — waterfall's Total set the precedent for drawing a mark the
frame never held, and this is the second such type, so its count likewise exceeds its row count.
It carries no value (internal by construction, so the centre reads a total Highcharts computes
rather than one the builder asserts) and a color taken **off the categorical scale entirely** —
waterfall's Total argument, transposed and sharper: ring 1 *cycles* the palette, so no palette
entry is guaranteed not to be some branch's hue, and the only way to say "this is not a
category, it is the whole" is a neutral from outside it. (Left unset, Highcharts paints it one
of its own defaults — a cyan in no palette of ours.) It is appended only when at least one node
survives: a lone slate disc labelled `All` is not a chart.

Ring 1 is seeded with a per-**point** `color` from the *overridable* `colors` list — a branch's
hue is its arbitrary identity, like a pie slice's, the opposite of waterfall's semantic
red-means-loss — and every descendant then **inherits** its branch's hue for free, separated
from its siblings by a `levels[].colorVariation` whose sign *alternates* per ring (the variation
applies to the parent's already-varied color, so a fixed `-0.5` walks a deep tree to black). It
has to be seeded per point, because *both* obvious alternatives are traps: the canonical
Highcharts recipe, `levels[].colorByPoint`, is accepted by `Chart.from_options` and then
**silently dropped** (sankey's `nodeFormat` / boxplot's `fillColor` / treemap's `value`-not-`y`
again), while the `colorByPoint` that *does* survive is the series-wide one, which would hand
every point in the flat data array its own hue — deep descendants included — destroying the very
inheritance the scheme rests on. It labels each sector with its **name only** — the one type
that breaks the print-the-value-in-the-mark rule the other five keep — because a sector is a
thin *curved* arc with the text bent along it, so there is room for one short string, and the
name is the only thing identifying a sector (a sunburst has neither axis nor legend) while the
value is already the *angle*. `allowTraversingTree` makes a click re-root the chart on that
branch. It needs **one** `_themed` hook — `borderColor`, the white sector rings that pie,
treemap and sankey each dissolve — and pulls in `modules/sunburst`, and, unlike
bubble/radar/boxplot/waterfall, *not* `highcharts-more`), and `xrange` (a Gantt-style
timeline, and the only type whose mark has **extent** along the x axis rather than sitting at
a point on it. Each row is one bar, on the **lane** named by `x_col` — and here `x_col` is not
an x axis at all: the lanes are the categories of the **Y** axis, so its values *repeat*
(boxplot's long/tidy shape, but a lane holds 0..n bars rather than aggregating into one
mark), and `y` is a *position* into `yAxis.categories` rather than a value (boxplot's
positional trick again). The bar spans from the first `y_cols` column to `end_col`.

Those two are the type's real novelty: they are **coordinates**, not magnitudes. Every other
type's value column answers *how much*; these answer *when*. So the module gains a third
column role beside the LABEL (`_label_ok`, "this names a mark") and the VALUE (`_plottable`,
"this sizes a mark") — the COORDINATE (`_coordinates`, "this positions a mark"), which may be
a **date**. It is sniffed once per column, and the sniff is **dtype-first**, which is not
fastidiousness but the only safe order: `pd.to_datetime(12)` does not fail, it returns
`1970-01-01T00:00:00.000000012`, so a "try dates, fall back to numbers" sniff would silently
move a column of sprint numbers to an instant at the epoch. A numeric dtype is therefore never
shown to a date parser at all; a `datetime64` dtype is a date; and only an **object** column is
a genuine question — answered by counting how many cells each coercion recovers, with the date
parse **pinned to ISO-8601**. That pin is load-bearing too: pandas' default parser is wildly
permissive on free text, and `pd.to_datetime(["Jan","Feb","Mar"])` *succeeds*, returning **year
1 AD** — which is `_revenue_vs_cost`'s `month` column, the app's **landing dataset**, so a
permissive sniff would offer a date axis on the page you see when you open the app. (`utc=True`
for a third reason: `errors="coerce"` is not total without it — a DST-crossing column raises
"Mixed timezones detected" even under `coerce`, and this code runs *above* the app's guards.)
The dates then become epoch **milliseconds** via `_epoch_millis`, which normalizes the
resolution *before* taking the int64 view rather than dividing after it: `.astype("int64")`
reads a datetime column in its OWN resolution, and this project's pandas hands back
`datetime64[us]`, not the `[ns]` an obvious `// 1_000_000` would assume — that divisor renders
`2024-01-05` as `1970-01-20`, every bar in the correct *relative* order at catastrophically
wrong *absolute* dates, drawn confidently, with no error anywhere.

`_spannable` is the module's first **two-argument** predicate, because an interval's validity
is a fact about the **relation** and not about either end — `_sizable` widened to a *pair*
rather than by one comparison. Both ends must be `_plottable` before they are compared, and
the finiteness half is load-bearing: `end >= start` alone accepts `(-inf, 10)`, which would
put a bare `inf` in the emitted JS. Then the comparison decides two *asymmetric* fates. A
**milestone** (`end == start` — a launch date, a deadline, a same-day task, one of the
commonest Gantt rows) is **kept**, exactly as `_sizable` keeps its zero; Highcharts draws
nothing for it unaided (verified by rendering: an empty lane), so it is floored to a visible
sliver with `minPointLength`, which is what makes *counting* it honest rather than dropping it
being necessary. A **backwards** bar (`end < start`) is **dropped**: left in, Highcharts draws
a bar spanning the ENTIRE axis (verified by rendering) — not a visible error but a confident,
plausible lie that reads as the longest task in the project, the xrange counterpart of
sunburst's silent re-parenting. It drops rather than raises for `_sizable`'s reason: there IS
a right drawing (nothing), unlike a cycle, where every alternative is a lie.

The contradictions that *do* raise are **column**-level, decided once, with no per-row right
answer: a start/end column that is neither dates nor numbers, or two that disagree about which.
Returned as a message rather than raised (the `_SUNBURST_CYCLE` rule) so `count_marks` stays
total. Only *one* of the two is reachable from the app — the date-beside-a-number mismatch —
since `coordinate_columns` keeps a text column out of the pickers; the other is reachable only
through the pure builder API.

`_coordinates` therefore has a **fourth** answer, `_COORD_EMPTY`, and it is not a kind but the
absence of one — the fix for a bug the review caught. An unfilled column is missing **data**
(every row drops, the chart comes out empty), and it must not be allowed to masquerade as a
kind, because a kind is a claim about an *axis* and an empty column makes no such claim. The
dtype dispatch cannot tell the difference on its own: a blank CSV column arrives as all-`NaN`
`float64`, so `is_numeric_dtype` says "number" with total confidence — and that phantom number
then collides with a real date partner and raises, telling the user their empty End column
"reads as numbers", which is both false and unactionable. It is not a corner case (it is a
Gantt template whose end dates nobody has filled in yet, straight out of `read_csv`), and the
bug was *asymmetric*: an empty column beside a numeric partner agreed by coincidence and worked,
so only the **date** case — the type's headline use — was broken. Hence the empty test runs
*first*, above the dtype dispatch, and an empty column abstains from the start-vs-end vote
rather than vetoing it. A lane whose every row dropped never enters `yAxis.categories` at all — boxplot keeps
an all-missing group as an `EnforcedNull` box because there the group IS the mark, but a lane
holds 0..n bars, so there is nothing to null out: pie's drop-the-row family, no ghost lane.

Bars are colored **per lane**, seeded per **point** from the *overridable* `colors` — a lane's
hue is its arbitrary identity, like a pie slice's (the opposite of waterfall's semantic
red-means-loss), and every bar in a lane shares it, which is what makes a task's phases read as
one thing. Here the `colorByPoint` trap is the **mirror** of sunburst's: where sunburst's
`levels[].colorByPoint` is silently *dropped*, xrange's series-level one *survives perfectly* —
and is the wrong option, since it would hand every BAR its own hue. It is the one mark-bearing
type that prints **nothing** in the mark and needs no gate constant either: the five that do
print a value in the mark do so because the value can be read against no axis (an angle, an
area, a link's width, a bar floating above an invisible running total), but an xrange bar's two
ends BOTH land on a real, ticked x axis that renders in the Static PNG too — column/bar's case,
not waterfall's — and there is no second identity to print, since the lane name IS the y-axis
category. Its tooltip uses `{point.name}`, which is waterfall's *fix* and xrange's **bug** in
mirror image: `{point.category}` reads the X axis, and an xrange's categories are on the Y, so
it renders the raw x value (a tooltip reading `1767571200000` — verified by rendering). It
needs **one** `_themed` hook, and it joins **column/bar** rather than waterfall — the other
bar-shaped type, which needs the opposite treatment. That was *measured*, not inferred from the
shared bar base class: waterfall is the standing proof the inference is unsound, its border
being a fixed `#333333`, while xrange's default border is pure white (the background variable),
so every bar is ringed white on the dark background until it is dissolved. Pulls in
`modules/xrange`, and, like sunburst, *not* `highcharts-more`).

## Run

```bash
uv run streamlit run streamlit_app.py
```

`.streamlit/config.toml` themes the shell and enables `runOnSave`, so saves
auto-rerun. When a stale chart is suspected, flush the four `@st.cache_data`
caches (the CSV loader plus the three chart renderers) with
`uv run streamlit cache clear`; verify config with `uv run streamlit config show`.
A *blank* chart is usually a network issue instead: interactive mode loads
Highcharts from the CDN (`code.highcharts.com`), static mode from the export
server (`export.highcharts.com`).

## Test

```bash
uv run pytest
```

`tests/test_smoke.py` exercises the pure builder (`build_options`) —
parametrized across every supported chart type, covering missing data
(`EnforcedNull` for the category-x family — cartesian and radar — dropped
points/slices elsewhere) and non-finite data (each type applying that same policy
to an `inf`, swept over `SUPPORTED_TYPES` by asserting no type emits a bare `inf`
into the serialized JS), the numeric vs non-numeric scatter/bubble paths
(bubble adds the `(x, y, size)` triples whose series share one size column, plus
its dimension-naming tooltip), radar's polar-line shape (`chart.type` `line` +
`chart.polar`, sharing the `highcharts-more` module and themed by the same
`_themed` chrome), heatmap's colorAxis value matrix (`[x, y, value]` cells over
two category axes, empty cells kept as `EnforcedNull`, its colorAxis themed for
dark mode and resolving the `modules/heatmap` module), treemap's value-sized tiles
(`{name, value}` leaves colored categorically via `colorByPoint`, missing values
dropped like pie, its tile gaps themed for dark mode and resolving the
`modules/treemap` module), sankey's node-link flows (`{from, to, weight}` link
dicts over two node columns — the `keys`-plus-arrays form highcharts-core
rejects outright — rows missing any of the three dropped, its per-link weight
labels gated on link count, its node/link borders themed for dark mode while the
labels ride Highcharts' `contrast` default, and resolving the `modules/sankey`
module), boxplot's aggregated Tukey distributions (raw observations grouped by a
repeating `x_col` into positional `[low, q1, median, q3, high]` 5-arrays in
first-appearance order; the outliers split into a linked scatter series that is
emitted only when they exist; the `iqr == 0` degeneracies — a one-observation group,
an all-identical group, and one with genuine tails — that the *inclusive* fence
decides; the matplotlib whisker clamp at *both* ends (a skewed group whose `q1` falls
below every in-fence point, and its mirror whose `q3` rises above every one); non-finite
observations dropped and a text column rejected with `ValueError`; an all-missing group
kept as an `EnforcedNull` box while a missing
`x_col` key forms no group; and the `fillColor`/`stemColor` silent drop pinned on the
emitted JS, which is why its box interior stays white and it needs no `_themed` hook),
waterfall's cumulative bridge (the appended `isSum` total — pinned on the emitted JS,
and *absent* when no step survives to sum, so a lone "Total: 0" bar is never drawn;
the semantic up/down/total colors, which a custom `colors` palette must NOT repaint,
and the total's *per-point* color, whose absence would silently paint it with the DOWN
color and read it as a loss whatever its sign; a missing delta keeping its axis slot as
an `EnforcedNull` rather than dropping its row; the in-bar value labels and their
step-count gate on both sides of the boundary; the `{point.category}` tooltip token,
since the positional points would render `{point.name}` blank; and the two dark-mode
hooks, bar borders *and* connector lines),
sunburst's assembled hierarchy (the synthesized ids — pinned by two leaves both named
`Other`, which must stay two sectors worth 100 and 40 rather than merging into one worth
140, the exact corruption label-as-id causes and which Highcharts rejects outright as
error #31; the invariant that every drawn leaf carries a `value` and every internal node
carries none, *even when the CSV states one*, since a stated parent value overrides the
sum; the appended root, its off-palette color that a custom `colors` must NOT repaint,
and its absence when no node survives; the dangling parent dropped *with its descendants*
rather than silently re-parented; the cycle, the self-parent one-node cycle, the
rootless forest that is necessarily a cycle, and the cycle a dangling row must not hide;
the 5,000-long cycle and 5,000-deep chain that pin the walk as iterative; the ambiguous
parent label that raises where an unreferenced duplicate does not; `_sizable` dropping a
negative leaf while keeping a zero; the `_node_key` int-vs-float trap, where a blank
parent cell widens that column to `float64` and a bare `str()` would dangle every row and
empty the chart *silently*; the per-point ring-1 seeding and the `colorByPoint` that must
appear NOWHERE in the emitted JS — dropped from `levels`, and wrong at series level; the
alternating `colorVariation`; the name-only sector labels and their gate; and the one
dark-mode hook),
xrange's interval bars (the **epoch pin** — `2026-01-05` must serialize to exactly
`1767571200000`, asserted across four column shapes (object ISO strings, `datetime64[us]`,
`datetime64[s]`, tz-aware), since the obvious `// 1_000_000` divisor is right for exactly one
of them and renders the rest in 1970; the **epoch trap mirrored** — an int column stays
numeric and gets *no* datetime axis, because `pd.to_datetime(12)` would silently make it the
epoch; the sniff table, including the month-name column that `format="ISO8601"` must reject
*because it is the landing sample's*, and the DST column that raises without `utc=True`; a
build under `warnings.simplefilter("error")`, the only way the ISO-8601 pin is observable; the
kept-and-floored milestone with `minPointLength` pinned on the emitted JS, and the dropped
backwards bar *with its lane gone from the axis*; `_spannable`'s four boundary pairs and the
`-inf`/`+inf` hole that `end >= start` alone would leave; the per-lane hue, a custom palette,
a short one that must cycle rather than `IndexError`, and the `colorByPoint` that must appear
NOWHERE — the mirror of sunburst's, since here the series-level one *survives* and is wrong;
the `{point.name}` tooltip, since `{point.category}` renders the raw epoch; the absent
dataLabels; the **no-drift pin**, a frame whose only garbage cell sits on a row dropped for its
label, which a raw-frame sniff would decide differently from the chart; and the one dark-mode
hook),
the brand palette, the
light/dark theming (dark-mode chrome — including the tooltip and the heatmap
colorAxis — vs. the shared palette), and the validation guards (including the
category-x x-in-y rule, widened to heatmap, boxplot and waterfall, bubble's required
size column, sankey's required, distinct target column, sunburst's required,
distinct parent column, and xrange's required end column, distinct from the *start*
column rather than from `x_col`) —
plus an end-to-end pass driving every supported type through the real
`Chart.from_options` → `to_js_literal` pipeline (so a newly added type is proven
to serialize — bubble, radar, boxplot and waterfall all pulling in the
`highcharts-more` module,
heatmap the `modules/heatmap` module, treemap the `modules/treemap` module,
sankey the `modules/sankey` module, sunburst the `modules/sunburst` module, and xrange the
`modules/xrange` module (the last two alone among the five extra-module types needing *not*
`highcharts-more`) — rather than just
assumed; sankey's node
tooltip is pinned in that serialized JS too, since a top-level `nodeFormat` is
accepted by `Chart.from_options` and then silently dropped, as boxplot's `fillColor`
is and as sunburst's `levels[].colorByPoint` is, and waterfall's `isSum` is pinned
there for the same reason — it is a point key
that *does* survive, which only the emitted JS can show, as sunburst's `id`/`parent`
and `allowTraversingTree` are, and as xrange's `x2` and `minPointLength` are) and the sample
datasets, then drives the full app headless via Streamlit's `AppTest` (switching
controls — including the bubble Size (Z) control, radar, heatmap, treemap,
sankey's Target (to) control, sunburst's Parent control, xrange's End control, and boxplot's
and waterfall's
single-select Y —
revealing the generated config behind its toggle,
the KPI metric row, the wide-CSV
`st.multiselect` fallback, the render-mode selector's two modes, and asserting
the guard messages — including a *cyclic uploaded CSV*, the one builder error a user
can reach just by uploading a file, which must warn and stop rather than render a
traceback, and its xrange counterpart, a date start beside a numeric end; plus the
**type-aware column gate**, driven by an uploaded Gantt CSV with *no numeric columns
whatsoever*, which must plot as an xrange and must still be refused by `line`).

`tests/test_hooks.py` covers the `.claude/hooks/` scripts: the extracted pure
functions (`protected_reason`, `is_python_target`, `has_dirty_python`) directly,
plus a black-box pass that drives `guard_paths.py` / `post_edit_py.py` over stdin
to pin their exit-code contract (2 blocks, 0 allows) without spawning the
toolchain.

`tests/test_packaging.py` guards the licensing metadata so its homes can't
drift apart: the `pyproject.toml` SPDX `license`/`license-files` fields, the
`LICENSE` file (kept pristine MIT so GitHub detects it — re-appending prose is
pinned as a regression), the `NOTICE` third-party notice (which must keep naming
both proprietary layers — Highcharts JS/the export server and `highcharts-core`),
the README `## License` section, its header badges (pinned to the `pyproject.toml`
license and Python/Streamlit version floors), and its `## Contents` list (pinned
to the real `##` headings). It reads the files directly (no build step), the same
mechanical-sync idea as `test_theme_colors_stay_in_sync_with_config`.

## Lint & format

Ruff handles both (config in `pyproject.toml`). CI runs the tests and these
checks on every push to `main` and every PR.

```bash
uv run ruff check --fix . && uv run ruff format .   # fix + format
uv run ruff check . && uv run ruff format --check .  # verify (as CI does)
```

## Type check

[ty](https://docs.astral.sh/ty/) (Astral's type checker, pinned in
`pyproject.toml`) runs in CI. It needs the project venv to resolve imports, so
run it through `uv run`:

```bash
uv run ty check
```

A few highcharts-core stub mismatches (Optional `options`/`chart`,
`to_js_literal` typed `str | None`) are suppressed inline with
`# ty: ignore[rule]`, not by downgrading rules globally — so the rules still
catch the same problems in our own code.

## Hooks

`.claude/settings.json` wires three project hooks (committed; the per-developer
`.claude/settings.local.json` stays gitignored) that mirror the CI gates so edits
stay green before a push. Each is a stdlib-only Python script under
`.claude/hooks/`, run via `uv run --project "$CLAUDE_PROJECT_DIR" python …` so it
executes on the project's pinned 3.12 interpreter — the same one the tests use,
not the machine's system `python3` — and keeps its decision logic in a pure,
importable function that `tests/test_hooks.py` covers. The scripts are themselves held to those gates:
`ruff check .` and `uv run ty check` include `.claude/hooks/` (dot-dirs aren't
excluded), so the tooling that enforces the app enforces the hooks too.

- `post_edit_py.py` (PostToolUse on `Edit`/`Write`/`MultiEdit`) — on a `.py`
  edit, runs `ruff check --fix` + `ruff format` in place, then `ty check`; exits
  2 on type errors so the diagnostics feed back to fix. Mirrors the Ruff and ty
  gates.
- `pytest_stop.py` (Stop) — runs `uv run pytest` when the working tree has
  uncommitted `.py` changes (app, test, or the hook scripts under
  `.claude/hooks/`); exits 2 on a real failure (pytest exit 1/2) to feed the
  output back, treating a tooling/env failure as a no-op, with a
  `stop_hook_active` guard so it can't loop. Mirrors the test gate.
- `guard_paths.py` (PreToolUse) — blocks direct edits to `uv.lock`,
  `.streamlit/secrets.toml`, and `.git/` internals.

Adding or changing a hook triggers Claude Code's one-time hook-review prompt
before it runs.

## Conventions

- When working with Python, invoke the relevant Astral skill (`/astral:uv`,
  `/astral:ty`, `/astral:ruff`) for uv, ty, and ruff to ensure best practices
  are followed.
- Keep chart-building logic (DataFrame → Highcharts) in `highcharts_builder.py`,
  free of Streamlit imports, so it stays unit-testable.
- Keep each hook's decision logic in a pure, importable function in
  `.claude/hooks/` (as the builder is), so `tests/test_hooks.py` can cover it
  without subprocesses; the `main()` wrapper handles the stdin/exit-code plumbing
  and any impure subprocess orchestration (ruff/ty/pytest/git).
- Render every visualization with Highcharts (`highcharts-core`); do not use
  native Streamlit charts.
- Use `EnforcedNull` (from `highcharts_core.constants`) for missing data points
  in dict configs fed to highcharts-core (`Chart.from_options`), not Python
  `None`.
- A **row-less** frame (columns, no rows — a CSV with a header and no data) is a legitimate
  input and must draw an **empty chart, not raise**. Every `Series.map(...)` used as a mask
  must therefore be `.astype(bool)`-cast: `.map()` infers its result dtype from the values it
  produced, and with no rows there are none, so it returns an empty **non-boolean** Series
  (object, or `str` for an Arrow-backed column). That then breaks three different ways —
  a DataFrame indexed by a non-boolean Series is not masked at all but read as a list of
  **column names** (this is what made `build_options` die with a bare `KeyError` in *every*
  type — one shared line, so the count is however many types there are, and a new one
  inherits the bug the day it is added unless the cast is there); `.sum()` of an empty string
  mask is `''`, so `int()` raises `ValueError`; and
  `&` between two of them raises out of the Arrow kernel, while `bool & str` merely *warns*
  today but is deprecated and will raise in pandas 4. The casts live at
  `build_options`' `_label_ok` filter, on all three of `count_marks`' masks, and on
  `_xrange_bars`' own `keep` mask. Sunburst is
  the one type that needs no cast of its own: `_sunburst_tree` reads the frame with a plain
  `zip` rather than a mask, so a row-less frame is simply an empty loop, and its `count_marks`
  branch returns *above* the three masks. It still rides the shared `_label_ok` filter, so it
  is covered by that cast like everything else. Xrange's `count_marks` branch likewise returns
  above the three masks, but `_xrange_bars` re-applies `_label_ok` *itself* — a mask, and so
  a cast — because it must produce byte-identical output from the raw frame `count_marks`
  hands it and the filtered one `build_options` does. A row-less coordinate column is also the
  one case `_coordinates` must NOT call a contradiction: nothing parses, but nothing is
  *present* either, so it is missing data (an empty chart), not a column of the wrong kind. Two sweeps
  pin it (`test_row_less_frame_draws_an_empty_chart_in_every_type` over `SUPPORTED_TYPES`,
  and `test_count_marks_casts_every_mask_not_just_the_label_one`, which promotes warnings to
  errors — the only way the non-label casts are observable at all).
- Treat a **non-finite** number as a missing one. `pd.isna(inf)` is `False`, but an
  infinity can't be serialized: `to_js_literal` emits the bare token `inf`, which is not
  a JavaScript identifier (JS spells it `Infinity`), so the chart call dies with a
  `ReferenceError` and the iframe renders blank; the export server, sent the
  non-standard JSON literal `Infinity`, answers `400`. So each type applies the same
  missing-data policy to a non-finite **value**: the keep-the-slot types go through `_num`
  (gap = `EnforcedNull`), the drop-the-row types through the shared `_plottable` predicate
  (pie, treemap, scatter, bubble, and sankey's *weight*), boxplot drops non-finite
  observations before aggregating — and, because it is the one type that does *arithmetic*
  on the values, then nulls the whole box (an `EnforcedNull`) if that arithmetic overflows
  a finite group into a non-finite quantile/fence — and xrange drops the row via
  `_spannable`, whose `_plottable`-on-both-ends half exists precisely for this: `end >= start`
  alone accepts `(-inf, 10)`, so the comparison is *not* enough on its own and the finiteness
  check is what keeps a bare `inf` out of the emitted JS. The same policy governs the **label**
  column (the one that NAMES a mark — a slice/category/node/box): a missing or non-finite
  label names nothing drawable, so its row is dropped uniformly via `_label_ok`, filtered
  once at the top of `build_options` (except scatter/bubble with a numeric x, where x is a
  coordinate `_plottable` already guards; sankey's second label column, `target_col`, is
  checked in its own branch). This replaced an earlier split where most types kept a
  `"nan"`/`"inf"` label and only sankey/boxplot dropped it. Two sweeps pin it:
  `test_no_supported_type_emits_a_non_finite_js_literal` for the value channel and
  `test_missing_or_non_finite_label_drops_the_row_in_every_type` for the label channel, so
  a new type is covered on both the day it is added. Reachable from a plain CSV: `inf`,
  `Infinity`, `-inf` and `1e400` (which silently overflows), and a blank cell (`nan`).
- `build_chart_html` pins the chart's `color-scheme` to `only light`
  (`_LIGHT_COLOR_SCHEME_CSS`, on the `.highcharts-root` `<svg>`, not `html`: Highcharts
  declares `color-scheme: light dark` on the `.highcharts-container` div between them, and
  since the property inherits, that shadows an `html` rule for the SVG subtree — so the pin
  must sit at or below the container to win). Highcharts ≥ 13 expresses
  its own defaults as `light-dark()` CSS variables, so any color we *don't* set would
  follow the **viewer's browser**, not the `dark` flag: a light-mode chart rendered dark
  on a dark-OS browser, and `boxplot`'s unsettable box fill differed between the iframe
  and the PNG. The export server already rasterizes with the light resolution, so this
  makes the two render modes agree and leaves `_themed` the single source of truth for
  dark mode. Anything a new chart type wants themed must go through `build_options`,
  never through a Highcharts default.
- Theme charts via `highcharts_builder.DEFAULT_COLORS` (applied by
  `build_options` to every chart, so the iframe and PNG paths are themed too),
  keeping its first color in sync with the light-mode `primaryColor` in
  `.streamlit/config.toml`. The palette is shared across light/dark; only the
  chart chrome (background/text/axes/gridlines/tooltip) flips, via
  `build_options(..., dark=...)` / `_DARK_CHROME`. `streamlit_app.py` reads `dark` from
  `st.context.theme.type` and threads it through the cached renderers (so it's
  part of their cache key). The one exception is `heatmap`, which colors its cells
  by a sequential `colorAxis` (`_HEATMAP_GRADIENT`, anchored on
  `DEFAULT_COLORS[0]`; a dark ramp `_HEATMAP_GRADIENT_DARK` flipped in by
  `_themed`) rather than the categorical palette — it still carries `colors` for
  cross-type consistency (the palette tests).
