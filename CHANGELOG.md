# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) — while
`0.x`, a minor bump is any new capability and a patch is a fix.

`0.7.0` is the first version cut as a release. Everything below it is
**reconstructed from git history**: the version in `pyproject.toml` was bumped by
hand, but nothing pinned it, tagged it, or wrote it down, so those entries are
read back off the commits rather than quoted from notes taken at the time.

Their `v0.1.0`–`v0.6.0` tags were **backfilled** on 2026-07-13 (the tag objects
say so, and their creation dates give them away). A tag here asserts only the one
checkable fact — that the commit it points at declares that version in
`pyproject.toml` — and not that a release was cut at the time, because none was.
They exist so the compare links below resolve to something structural rather than
to hand-typed SHAs.

Two consequences of the un-gated bumping are visible in the dates below, and are
worth stating rather than tidying away:

- **The bump often trailed the feature.** `0.2.0` was cut *for* areaspline and
  `0.3.0` *for* bubble, but by then both had already landed — so each range
  actually contains the *next* thing.
- **`0.6.0` ran long.** Five chart types (sankey, boxplot, waterfall, sunburst,
  xrange) plus the repo-wide missing-data hardening all shipped while the
  version sat still, because no gate asked it to move. Anyone who checked out at
  `xrange` got a tree calling itself `0.6.0`, so that is what this file says.
  `tests/test_packaging.py::test_changelog_documents_the_current_version` now
  pins `pyproject.toml`'s version to the top entry here, which is the gate that
  was missing.

Dates are the last commit at that version — the point it stopped being current.

## [0.7.0] - 2026-07-13

### Added

- **`solidgauge` chart type** — concentric activity-gauge rings on one shared
  dial. The first type with **no label channel at all**: its marks are the
  *selected columns themselves*, each reduced to a single number, so `x_col`
  names nothing and is `None` (widening it to `str | None` across the public
  signatures, and making every *other* type raise when it is omitted). The
  second aggregating type after `boxplot`, and the first whose row count has no
  bearing on its mark count.
- `agg=` — the reduction each ring applies to its column, one of the exported
  `GAUGE_AGGREGATIONS` (`sum`, `mean`, `median`, `min`, `max`, `last`), surfaced
  in the app as an aggregation picker sourced from that same tuple.
- `gauge_dial()` and `dial=` — the ring scale, **derived from the readings, not
  from the raw columns**. Under `sum` a reading can exceed every observation in
  its own column, so a dial derived from the column would pin every ring past
  its own end. The app *seeds* its Dial min/max inputs from this same call, which
  is the can't-drift rule applied for the first time to a widget's **value**
  rather than to its options.
- `explain_gauge_error()` — the third of the `explain_*` family, and the first
  that reads no DataFrame at all: a dial whose maximum does not sit above its
  minimum is a contradiction about two numbers the user typed.

### Fixed

- An **empty column no longer reports a total of zero**. `pd.Series([], dtype="float64").sum()`
  is `0.0` — the additive *identity* — so under `sum` an unfilled column would
  have drawn a confident ring at the dial's floor claiming "the total is zero"
  where the truth is "there is no data". Only `sum` lies (the other five
  reductions give `NaN`), which would have made it look like a rounding quirk.
  The empty test now runs *above* the reducer, and the ring is kept as a null and
  named in the legend — the one type whose legend is not redundant, because it is
  the only thing that names an empty ring.
- `threshold: 0`, without which Highcharts sweeps each arc from the axis
  *minimum* and **inverts an all-negative dial** — a −40 drawing a longer arc
  than a −155.

### Changed

- The app **removes** the X selectbox for gauge — the first *subtractive* control
  change, since a control that does nothing is a lie in the UI.
- Named `solidgauge` (Highcharts' own name), not the friendlier `gauge`, which
  is a *different* Highcharts chart (a needle on a dial) whose name is left free.

## [0.6.0] - 2026-07-12

The long one: the bump ships `treemap`, and then five more chart types land
behind it without the version moving.

### Added

- **`treemap`** — nested rectangles sized by value, laid out `squarified` and
  colored categorically, with the value printed in each tile so the static PNG
  shows numbers and not just relative areas.
- **`sankey`** — node-link flows sized by weight, the first type to read the
  frame as a **graph** rather than a table: each row is one link, from `x_col`'s
  node to a new `target_col`'s node.
- **`boxplot`** — per-category Tukey distributions, and the first builder that
  **aggregates** (every other type maps rows 1:1 onto marks). Whiskers follow
  `matplotlib.cbook.boxplot_stats`, with *inclusive* 1.5×IQR fences so a
  zero-IQR group isn't read as all outliers.
- **`waterfall`** — a cumulative bridge, the category-x shape read as signed
  *deltas*, with the builder **appending** the closing Total bar itself. The
  first type whose mark count exceeds its row count. Bars are colored by
  *meaning* (green rise, red fall, brand-blue total), so a custom palette cannot
  repaint a loss green.
- **`sunburst`** — a hierarchy as concentric rings, the first type to read the
  frame as an **adjacency list** and the first whose marks must be *assembled*
  rather than read. Node ids are synthesized rather than taken from labels (a
  duplicate label is Highcharts error #31); an internal node carries no value (a
  stated parent value would override the children-sum); a dangling parent is
  dropped *with its descendants* rather than silently re-parented; a cycle
  raises.
- **`xrange`** — a Gantt-style timeline, the first type whose marks have
  **extent** along an axis. Its start/end columns are **coordinates, not
  magnitudes**, so they may be dates — sniffed dtype-first, because
  `pd.to_datetime(12)` silently returns an instant at the epoch.
- `count_marks()` — returns exactly how many marks `build_options` will draw, so
  the app's KPI row can source its counts from the builder rather than
  recomputing them and drifting.
- `explain_export_failure()` — a failed static-PNG render now names its actual
  cause: a build error before any request, an unreachable server, or an HTTP
  answer (a 4xx especially, since the server is plainly reachable).
- `explain_tree_error()` and `explain_xrange_error()` — the same contract for a
  malformed hierarchy and for a contradictory column pair.

### Fixed

- **A non-finite value is now treated as missing in every chart type.**
  `pd.isna(inf)` is `False`, so an infinity slipped through both missing-data
  policies: `to_js_literal` renders it as the bare token `inf`, which is not a
  JavaScript identifier, so the interactive iframe died with a `ReferenceError`
  and rendered blank — while the export server, handed the non-standard literal
  `Infinity`, answered `400`, which the app then misreported as an unreachable
  server. Reachable from a plain CSV (`inf`, `Infinity`, `-inf`, `1e400`).
- **The missing-data policy now governs label columns too.** It had covered only
  value columns, so most types rendered a mark literally named `nan` — reachable
  from one blank cell in a text column.
- **A row-less frame draws an empty chart instead of raising.** A header-only CSV
  parses to columns-with-no-rows, and `Series.map()` infers its dtype from the
  values it produced — with no rows there are none, so it returns an empty
  *non-boolean* Series, and the DataFrame was then read as a *list of column
  names* rather than masked. `build_options` died with a bare `KeyError` in every
  single type.
- **A boxplot group whose statistics overflow** to a non-finite quantile is
  nulled: with a spread near the double range, `iqr = q3 - q1` overflows to `inf`
  from *finite* CSV input.
- **Both render modes now agree on color.** Highcharts ≥ 13 expresses its
  defaults as `light-dark()` CSS variables, so every color not set explicitly
  resolved against the **viewer's browser** rather than the `dark` flag — a
  light-mode chart of any type painted itself dark on a dark-OS browser.
  `build_chart_html` now pins `color-scheme: only light`, leaving `_themed` the
  single source of truth for dark mode.
- Column/bar borders and the heatmap colorAxis legend are themed for dark mode;
  they had fallen through to a light-background default that ringed every bar
  white.

## [0.5.0] - 2026-07-05

### Added

- **`heatmap` chart type** — a category × category value matrix, and the first
  type colored by **value** (a sequential `colorAxis`) rather than by the
  categorical palette. `x_col`'s values are the X categories and each selected
  column *name* is a Y category; empty cells stay `EnforcedNull` so the grid
  keeps its alignment.
- A tooltip naming both category axes, in-cell value labels for grids of ≤ 50
  cells, a vertical colorAxis legend, and a **Cells** KPI replacing "Series
  plotted", which had misreported the single-series grid.

### Changed

- `X_IN_Y_GUARD_TYPES` names the guard set shared by the builder and the UI (it
  had been a duplicated expression in two files), and `_category_labels` folds
  the thrice-repeated x-category stringify.

## [0.4.0] - 2026-07-05

### Added

- **`radar` chart type** — a polar spider/web line chart, reusing the cartesian
  category-X data shape on polar axes (a `line` series with `chart.polar`).

### Fixed

- Dropped radar's `pane: {size: "85%"}`. highcharts-core silently discards
  *percentage* pane sizes, so it never serialized — a latent silent-drop trap,
  and 85% is already the default.

## [0.3.0] - 2026-07-05

### Fixed

- **The default-Y reset regression.** The dynamic default (skip the X column) fed
  the *identity* of the keyless Y widget, so changing X re-minted the widget and
  silently discarded a multi-series selection.
- The bubble tooltip is hardened: column names are brace-stripped (so Highcharts
  won't parse `weight {kg}` as a token) and HTML-escaped (tooltips render HTML).

## [0.2.0] - 2026-07-05

### Added

- **`bubble` chart type** — scatter plus a marker-size dimension, via a required
  `size_col`. A size-aware tooltip names all three dimensions rather than
  emitting a bare x/y/z.

### Changed

- The end-to-end serialization pass widened from the cartesian types to **every**
  supported type, closing a real gap: the pie and scatter branches hardcode their
  `chart.type` literal and had never been driven through the real serializer.

## [0.1.0] - 2026-07-04

The initial app. The repository is repurposed from a collection of Highcharts
demo notebooks (archived at the `notebooks-archive` tag) into a Streamlit studio.

### Added

- **The app** — `streamlit_app.py` (UI, controls, caching) over a pure,
  Streamlit-free `highcharts_builder.py` (DataFrame → Highcharts options dict →
  `Chart` → embeddable HTML or PNG bytes), with built-in samples in
  `sample_data.py`. Every chart is produced by `highcharts-core`; no native
  Streamlit charts.
- **Eight chart types**: `line`, `spline`, `area`, `areaspline`, `column`, `bar`,
  `pie`, `scatter`.
- **Two render modes** — an interactive iframe (Highcharts from the CDN) and a
  static PNG (rendered server-side by the export server).
- **Light/dark theming** — split `[theme.light]`/`[theme.dark]` themes unlock
  Streamlit's in-app toggle, and a `dark` flag read from `st.context.theme.type`
  threads through the builder and into the cached renderers' keys. Only the chart
  chrome flips; the palette is shared, so a series keeps its color across a
  toggle.
- **A KPI metric row**, a chart-type help tooltip, and the generated Highcharts
  config behind a toggle.
- An `st.multiselect` fallback for wide CSV uploads, since `st.pills` is bounded
  at about five options.
- **The toolchain**: GitHub Actions CI (pytest, Ruff, ty), and Claude Code hooks
  under `.claude/hooks/` that mirror those same gates locally.
- **MIT licensing** with a separate `NOTICE` for the two proprietary layers
  (Highcharts JS / the export server, and the `highcharts-core` wrapper), so
  `LICENSE` stays pristine and GitHub detects the repo as MIT.

### Changed

- The interactive click-events render mode (a Streamlit Custom Component v2) was
  added and then **removed** again within this range; the render selector settled
  at two modes.
- The project was renamed twice on its way to `highcharts-studio`.

[0.7.0]: https://github.com/darylalim/highcharts-studio/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/darylalim/highcharts-studio/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/darylalim/highcharts-studio/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/darylalim/highcharts-studio/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/darylalim/highcharts-studio/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/darylalim/highcharts-studio/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/darylalim/highcharts-studio/releases/tag/v0.1.0
