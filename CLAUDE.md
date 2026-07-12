# CLAUDE.md

## Project Overview

`highcharts-studio` is a Streamlit application for building data visualizations
with Highcharts. Every chart is produced by the Highcharts for Python toolkit
(`highcharts-core`) — the app uses no native Streamlit charts.

## Structure

- `streamlit_app.py` — the Streamlit UI: data source (sample datasets or CSV
  upload), chart-type/column controls (pills for the Y series, falling back to
  `st.multiselect` on wide CSVs, plus the two type-specific extra column
  selectors — Size (Z) for bubble, Target (to) for sankey),
  caching, a KPI metric row (its third metric adapts to the chart type — series
  plotted, or, for the one-series types, the mark count from the builder's
  `count_marks`: cells for a heatmap, tiles for a treemap, flows for a sankey,
  boxes for a boxplot, steps for a waterfall — sourced there rather than recomputed
  here so it can't drift from what the chart draws; waterfall's is the one that
  *exceeds* its drawable step count, by one, since the total bar is appended by the
  builder — not necessarily its row count, since an undrawable label drops its step;
  membership of the `MARK_METRICS` dict is what makes a type count-adaptive, so the
  KPI stays one branch however many such types there are), the
  render-mode
  selector (interactive iframe / static PNG), reading the active light/dark theme
  (`st.context.theme.type`) so the charts render theme-aware, the chart embed,
  and a toggle that reveals the generated Highcharts config (JS).
- `highcharts_builder.py` — pure, Streamlit-free helpers that turn a DataFrame
  into a Highcharts options `dict`, a `Chart`, and embeddable HTML or PNG bytes,
  plus `explain_export_failure()`, which turns a failed PNG export into a message
  naming the actual cause (it owns the export-server relationship, so it owns the
  diagnosis; duck-typed on `exc.response.status_code` rather than importing
  `requests`, which this project never declares), and `count_marks()`, which
  returns how many marks `build_options` will draw (a heatmap's cells, a treemap's
  tiles, a sankey's flows, a boxplot's boxes, a waterfall's steps) for the app's KPI
  row — reusing the same `_label_ok`/`_plottable` drop predicates so the count can't
  drift from the chart. Independently importable and unit-testable.
- `sample_data.py` — pure (Streamlit-free) built-in sample datasets and the
  `SAMPLES` registry the app offers when no CSV is uploaded.
- `tests/test_smoke.py` — builder unit tests (every chart type, the missing-data
  and scatter/bubble edge cases, radar's polar-line shape, heatmap's colorAxis
  value matrix, treemap's value-sized tiles, sankey's node-link flows, boxplot's
  aggregated Tukey distributions, waterfall's appended total and semantic bar
  colors, the brand
  palette, the validation
  guards including bubble's required size column, sankey's required and distinct
  target column, and the heatmap/boxplot/waterfall x-in-y rule, and
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
omitted; ignored by the other types), threaded through the same renderers, and
sankey charts a `target_col=` naming the destination-node column (required for
`sankey`, and raising `ValueError` if omitted or equal to `x_col`; likewise
ignored by the other types), threaded the same way.

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
dark background only barely, so they are lifted to the axis color).

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
the brand palette, the
light/dark theming (dark-mode chrome — including the tooltip and the heatmap
colorAxis — vs. the shared palette), and the validation guards (including the
category-x x-in-y rule, widened to heatmap, boxplot and waterfall, bubble's required
size column, and sankey's required, distinct target column) —
plus an end-to-end pass driving every supported type through the real
`Chart.from_options` → `to_js_literal` pipeline (so a newly added type is proven
to serialize — bubble, radar, boxplot and waterfall all pulling in the
`highcharts-more` module,
heatmap the `modules/heatmap` module, treemap the `modules/treemap` module, and
sankey the `modules/sankey` module — rather than just assumed; sankey's node
tooltip is pinned in that serialized JS too, since a top-level `nodeFormat` is
accepted by `Chart.from_options` and then silently dropped, as boxplot's `fillColor`
is, and waterfall's `isSum` is pinned there for the same reason — it is a point key
that *does* survive, which only the emitted JS can show) and the sample
datasets, then drives the full app headless via Streamlit's `AppTest` (switching
controls — including the bubble Size (Z) control, radar, heatmap, treemap,
sankey's Target (to) control, and boxplot's and waterfall's single-select Y —
revealing the generated config behind its toggle,
the KPI metric row, the wide-CSV
`st.multiselect` fallback, the render-mode selector's two modes, and asserting
the guard messages).

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
  **column names** (this is what made `build_options` die with a bare `KeyError` in all
  15 types); `.sum()` of an empty string mask is `''`, so `int()` raises `ValueError`; and
  `&` between two of them raises out of the Arrow kernel, while `bool & str` merely *warns*
  today but is deprecated and will raise in pandas 4. The casts live at
  `build_options`' `_label_ok` filter and on all three of `count_marks`' masks. Two sweeps
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
  (pie, treemap, scatter, bubble, and sankey's *weight*), and boxplot drops non-finite
  observations before aggregating — and, because it is the one type that does *arithmetic*
  on the values, then nulls the whole box (an `EnforcedNull`) if that arithmetic overflows
  a finite group into a non-finite quantile/fence. The same policy governs the **label**
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
