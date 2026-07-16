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

## [0.9.0] - 2026-07-15

### Added

- **`networkgraph` chart type** — a force-directed graph, and sankey's cousin: each
  row is one edge between two node columns. It is the **mirror of the gauge family**.
  Gauge removes the *label* channel (`x_col is None`, its marks are the selected
  columns); networkgraph removes the *value* channel (`y_cols == []`, its marks are
  the edges), so the app draws it with **no Y control at all** — the second
  subtractive-control type, and the counterpart to gauge's absent X. It reuses
  sankey's `target_col` (a link is a link, so there is no new kwarg and the cache
  layer is untouched), rides the shared `_label_ok` filter on its source column, and
  needs a `count_marks` rule and a `MARK_METRICS` entry ("Links") because — unlike
  gauge — its one edge-series would otherwise misreport as a bare `1`.
- **`Service dependencies (networkgraph)` sample** — a microservice call graph whose
  source labels *repeat* and whose nodes are many of them both a source and a target
  (an `API Gateway` hub, a shared `Auth`), so it reads as a connected network rather
  than a star. It carries a `Catalog ⇄ Search` **cycle**, the one graph shape the
  sunburst sample's tree could never hold. Its `calls_per_min` column is a genuine
  numeric column carried for the reason `_release_plan`'s `headcount` is — so the
  dataset stays plottable by the value types and clears the no-numeric-columns gate —
  which networkgraph *ignores*, the honest place for a magnitude a graph can't draw.

### Notes

The type is **unweighted**, and that is the library's decision, not a preference —
each of these was measured on the round-trip or by rendering, never assumed:

- **A per-edge weight is silently dropped.** A `{from, to, weight}` link collapses
  to a `[from, to]` array in the emitted JS, so a numeric weight column (sankey's
  entire reason for being) would drive *nothing*. This repo treats a control that
  does nothing as a lie, so there is no weight column — the Y picker is removed, not
  ignored.
- **A node carries no individual color.** A series `nodes` array and a
  `colorByPoint` are both dropped the same way, so every node is the one brand hue;
  `colorByPoint` is asserted to appear nowhere. A graph's nodes have no categorical
  identity to colour, so this is honest rather than a limitation grudgingly accepted.
- **`enableSimulation` must be `false`.** With it `true` the export server rasterizes
  the graph mid-simulation as an unreadable central knot while the iframe animates it
  loose — the two render modes disagree, the class of bug `_LIGHT_COLOR_SCHEME_CSS`
  exists to close. With it `false` Highcharts settles the layout synchronously and
  both modes draw the same picture. Pinned on the emitted JS.
- **It needs no dark-mode `_themed` hook** (like boxplot, for a kindred reason): its
  node labels ride Highcharts' `contrast` color (white on dark, black on light), its
  nodes carry palette hues, and its links use a grey legible on both backgrounds —
  all verified by rendering a dark PNG. And it resolves `modules/networkgraph.js`
  from `chart.type` alone, and — correcting the common lore — **not**
  `highcharts-more`.

## [0.8.0] - 2026-07-13

### Added

- **`gauge` chart type** — the needle on a dial, and the second member of the
  **gauge family**. It spends the name `0.7.0` was deliberately holding for it:
  `solidgauge` was never given the friendlier `gauge` (which radar's precedent
  would have licensed) because `gauge` in Highcharts is a genuinely different
  series type, with its own `DialOptions`/`PivotOptions`. Both are now called
  what Highcharts calls them, and radar stays the *one* type whose `chart.type`
  is not its own name.
- **`GAUGE_TYPES` is now a family**, `SOLID_GAUGE_TYPES + NEEDLE_GAUGE_TYPES`.
  The tuple was already consulted at exactly the five places where the two types
  are *identical* — the `x_col is None` exemption, the `agg`/`dial` guard,
  `count_marks`' no-rule raise, the label-drop sweep's exclusion, and the
  row-less sweep's null expectation — so splitting it in two while keeping their
  sum under the old name was the whole of the family plumbing. Every one of those
  five sites stayed correct for the needle with **no edit at all**.
- `_dial_from_readings()` — the half of `gauge_dial` that **cannot see a
  DataFrame**. The family's central invariant ("the dial comes from the readings,
  never from the raw columns") stops being a rule two branches must remember and
  becomes a *signature*: a function that cannot see a raw column cannot derive a
  dial from one.
- **`Server utilization (gauge)` sample** — percentages across nine hosts, whose
  `mean` lands the derived dial almost exactly on `0..100`. Carries an entirely
  unreported `swap_pct` column, putting the family's headline trap on a page you
  can reach in two clicks.

### Fixed

- The needle gauge's **staggered needle lengths**. Two columns with *equal*
  readings put two needles at the same angle, and Highcharts draws the later
  series on top — so at one length the second needle covered the first
  completely: three series, two visible needles, with the legend still naming
  three. `marks == series` — the invariant the whole family rests on — was a lie
  *on screen*, in the one place a reader would never think to check. Staggering
  exposes each needle's tip in its own hue.
- **`overshoot`**, which keeps an *overridden* dial honest. `gauge_dial` guarantees
  every reading sits inside the scale it derives, but the app's two Dial inputs
  accept any two numbers — so zoom the scale to `0..50` on a column that sums to
  436 and the needle pegs **exactly on the final tick**, pixel-identical to a true
  reading of 50, with nothing on the chart to contradict it and no tooltip in the
  Static PNG. It was also the one place the two gauges would have *disagreed*: a
  ring in the same state fills its arc and prints `north: 436` in the hub, so its
  reader is told; a needle prints nothing in the mark. Now the needle swings *past*
  the last tick — what a real meter does when it slams its end stop.
- **`_GAUGE_VALUE_FORMAT`**, the family's number format, applied to **both** types.
  A bare `{point.y}` prints the raw double, and the double is what an aggregation
  hands you: the mean of nine integer percentages is `66.44444444444444`, which ran
  off the side of the chart in a 20-character smear. `solidgauge` had the identical
  latent bug — its own sample merely happens to divide evenly (436/8 = 54.5) — and
  it is the one flaw an options-dict assertion can never see, since the number is
  not in the options at all, only the format string is.
- The stale comment in `build_chart_html` claiming a gauge resolves
  `highcharts-more` from its `pane`. True of `solidgauge` (drop the pane there
  and the browser draws an empty SVG while the export server renders perfectly);
  **false** of `gauge`, which resolves the module from `chart.type` alone. The
  comment now names the type it is about, because the wrong half of it is a
  silently blank iframe.

### Notes

Three things the needle does *not* inherit from its sibling, each measured on the
round-trip or by rendering rather than assumed — and each of which would have been
a silent bug had solidgauge's answer been copied on faith:

- **The hue.** On a solid gauge a series-level `color` serializes perfectly and
  reaches *nothing* (the arc reads the point; the legend bullet draws grey and
  needs a `marker.fillColor`). On a needle, `color` reaches *only* the legend —
  the needle itself is **black** unless `dial.backgroundColor` says otherwise.
  Same property, opposite failure. The ring writes its hue to three places, the
  needle to two, and **not one of them is the same place**.
- **The module.** As above: `pane` for one, `chart.type` for the other.
- **The label.** A ring *must* print its readings in the hub — a 360° arc has
  nowhere to put an axis, so its value can be read against nothing, and it pays for
  that with a gate, a measured leading and a per-series offset. A needle points
  **at** an axis, so it prints **nothing in the mark** and needs no gate constant
  either: `xrange`'s rule, reached from `xrange`'s premise. The sibling's label
  machinery is not re-tuned here, it is *deleted*. (It was built the other way
  first, and the renders killed it: the stack, the arc and the subtitle cannot all
  fit at 300px, and both levers that would have bought the room are closed by the
  library — see below.)

Three silent drops found and pinned along the way. `Pane.size` discards a
percentage string (its setter validates `"85%"`, checks it for `%`, then falls off
the end without ever assigning `self._size` — only the numeric branch writes it),
which is what every gauge demo on the internet sets. `yAxis.labels.distance`
rejects `0` with `EmptyValueError` and refuses a negative outright — the same
`allow_empty` bug as `top_width`. And a `yAxis.plotBands` entry keeps
`from`/`to`/`color` but drops `thickness`, `innerRadius` and `outerRadius`; the type
carries no plot bands anyway, since `solidgauge`'s argument against `yAxis.stops`
holds unchanged — a coloured zone is a *judgment*, and the data never said low was
bad.

Between them, those first two are why the needle's **pane carries no geometry at
all** — no `size` *and no `center`*. Without `size`, a hand-placed centre cannot be
made safe: Highcharts reserves no room for the tick labels outside the pane, so
every value trades one chart height for another (at 65% it was clean at 300px and
800px and clipped clean off the canvas at 420). A failure that is not even monotonic
in the height is the tell that it is not a number to be tuned. Highcharts' own
default is correct at every height the app offers, because it is the one placement
that knows what the labels need.

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

[0.9.0]: https://github.com/darylalim/highcharts-studio/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/darylalim/highcharts-studio/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/darylalim/highcharts-studio/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/darylalim/highcharts-studio/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/darylalim/highcharts-studio/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/darylalim/highcharts-studio/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/darylalim/highcharts-studio/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/darylalim/highcharts-studio/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/darylalim/highcharts-studio/releases/tag/v0.1.0
