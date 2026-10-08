# CLAUDE.md

## Contents

[Project Overview](#project-overview) · [Quick start](#quick-start) ·
[Structure](#structure) · [Chart types](#chart-types) ·
[Adding a chart type](#adding-a-chart-type) · [Run](#run) · [Test](#test) ·
[Lint & format](#lint--format) · [Type check](#type-check) ·
[Release](#release) · [Hooks](#hooks) · [Conventions](#conventions)

Four docs, four jobs. **This file** carries the commands, the file map, and the rules
that apply to every type at once. [`docs/chart-types.md`](docs/chart-types.md) carries the
per-type design record — why each type is built the way it is, what the library silently
drops, and which calls were settled by rendering; it is long, so read the section you need
([How a chart is built](docs/chart-types.md#how-a-chart-is-built) plus the entry for the
nearest existing type) rather than the whole file.
[`docs/decisions.md`](docs/decisions.md) carries the argument and the incident behind
rules stated tersely here. [`docs/plan.md`](docs/plan.md) carries what is **not built
yet** — the feature backlog, one entry per feature with its status. It states intentions,
not facts the code must match, so a finished entry's reasoning moves into the docs above and
the entry shrinks to a pointer.

## Project Overview

`highcharts-studio` is a Streamlit application for building data visualizations
with Highcharts. Every chart is produced by the Highcharts for Python toolkit
(`highcharts-core`) — the app uses no native Streamlit charts.

One direction of flow, and every change lands somewhere on it:

```text
sample_data.py / CSV upload
  -> streamlit_app.py        widgets, guards, @st.cache_data wrappers, KPI row
  -> build_options()         DataFrame -> Highcharts options dict  (Streamlit-free)
  -> Chart.from_options()    via make_chart()
  -> build_chart_html()      iframe, Highcharts from the CDN; its ☰ menu draws
                             PNG/JPEG/SVG downloads in the browser
  -> build_chart_exports()   the Export panel: JSON (stdlib json over the options dict),
                             the JS call, an HTML snippet and a full page
```

## Quick start

```bash
uv sync                                   # Python 3.12; installs the dev group too
uv run streamlit run streamlit_app.py     # the app
uv run pytest && uv run ruff check . && uv run ty check   # the three gates
```

**No environment variables, no secrets, and no API keys are required.** The app reads
nothing from `st.secrets` or `os.environ`; `.streamlit/secrets.toml` appears only as a
`permissions.deny` rule, guarding a file this project does not use. The one network
dependency is an unauthenticated CDN, `code.highcharts.com`, fetched by the viewer's browser;
downloads are drawn in the browser too, so the app never contacts `export.highcharts.com`.

## Structure

- `streamlit_app.py` — the Streamlit UI: data source (sample datasets or CSV upload, editable
  cell by cell in the Source data table, see [Test](#test)),
  a two-step chart-type picker (family pills, then a selectbox of that family's types, both
  read from the builder's `CHART_FAMILIES`; the selectbox's help shows only that family's
  types), column controls (pills for the Y series, falling back to `st.multiselect` on
  wide CSVs, plus one extra column selector per extra column kwarg), the `@st.cache_data`
  wrappers, a KPI metric row (its third metric adapts via `MARK_METRICS` — see
  [Chart types](#chart-types)), the chart embed (its ☰ menu downloads PNG/JPEG/SVG, drawn in
  the browser; there is no render-mode selector since the Static PNG mode was retired, see
  [Conventions](#conventions)), and the **Export** panel behind a toggle (HTML snippet, HTML
  page, JS and JSON tabs from `build_chart_exports`, and a Python tab from `python_snippet`,
  each with a download). The
  **no-plottable-columns gate** runs *below* the chart-type selectbox and is
  **type-aware**: xrange's start/end are coordinates and may be dates, and a date column
  is object dtype, so a canonical Gantt CSV has no numeric columns at all and a
  `select_dtypes("number")` gate would `st.stop()` it before the picker was drawn. It is a
  **table** — `vocabularies`, one row per column vocabulary, each carrying the family
  constant, the source list, and the two messages (the frame has no such column / none is
  selected): `XRANGE_TYPES` needs a coordinate, `TIMELINE_TYPES` needs a **date** (a stricter
  rule, not the same exemption — a frame of pure numbers passes xrange's row and must fail
  timeline's, or the landing dataset would sail through and land the Date picker on
  `revenue`), `UNWEIGHTED_NODE_LINK_TYPES` carries `None` for **exempt**, and every other type
  falls through to the numeric default. A row is what makes adding a type **one** edit: the
  hand-written arms it replaced needed two — its own arm, plus a `not in` clause on the numeric
  one — and forgetting the second was silent, the type passing its own arm and then being
  refused by the numeric one with the wrong message. The **single-select Y picker's source** is
  that same row (`y_source`), not a second three-way branch beside it, so "the picker can never
  offer a column the builder would refuse" is one site rather than two agreeing (the multi-select
  branch takes the table's default list, `numeric_cols`, which is the same list by another name); the
  empty-selection warning is the row's message too, since "numeric" is plainly wrong for both
  types whose Y is a **coordinate**. Both source lists come from **one** `picker_columns(df)`
  call rather than two helpers that each re-sniff every column. And `keep_picker_state()` runs
  in front of the gate's `st.stop()`: Streamlit garbage-collects the session-state entry of any
  keyed widget a run does not instantiate, and this gate stops *above* the keyed X and Y
  pickers ([the measurement](docs/decisions.md#keyed-widgets-the-third-way-a-picker-loses-its-answer)).
- `highcharts_builder.py` — pure, Streamlit-free helpers that turn a DataFrame into a
  Highcharts options `dict`, a `Chart`, and embeddable HTML. Independently
  importable and unit-testable. It also owns three things that would otherwise drift from
  it: the **diagnosis** of its own failures (`explain_tree_error`, `explain_xrange_error`,
  `explain_gauge_error`, `explain_networkgraph_error` — so a message can't drift from the error
  it stands in for), the **options** its widgets
  offer (`picker_columns` — one sniff of the frame answering both coordinate pickers at once,
  with `coordinate_columns` / `date_columns` as thin wrappers over its two halves — the app
  reads the pair, and the wrappers stay for the pure-API caller and their own tests. What the one
  sniff makes structural is that both lists answer the same question once; "every date column is a
  coordinate column" is one membership test apart against named kind tuples — and the subset itself pinned by `test_picker_columns_answers_both_pickers_from_one_sniff`, since `_DATE_KINDS` is a second literal rather than something derived from `_COORDINATE_KINDS` — plus `GAUGE_AGGREGATIONS` and `gauge_dial`), and
  `count_marks`, which reuses the same drop predicates — or, for sunburst, xrange and
  timeline, the whole build — so the KPI can't drift from the chart. Timeline adds **no**
  `explain_*` of its own, and that is the design: `date_columns` narrows its picker to
  columns that already pass, so its one contradiction is **unreachable** from the app rather
  than explained after the fact — which is strictly better, and the reason the list above
  gained an *options* entry instead of a *diagnosis* one.
- `sample_data.py` — pure (Streamlit-free) built-in sample datasets and the `SAMPLES`
  registry the app offers when no CSV is uploaded. Every sample **but one** leads with a
  **category column**, and that is load-bearing rather than tidy: the app opens on `line`
  with the first column as X, so a numeric first column trips the x-in-y guard the moment
  the dataset is selected. The exception is the scatter sample (`Height vs weight`,
  leading with the int64 `height_cm`), which does exactly that — it is the standing
  counterexample, not a shape to copy. Samples are otherwise designed as **mirrors** —
  the columnrange, arearange, bullet, variwide and dumbbell samples all carry two
  magnitude columns and mean something different by them, so reading them side by side
  shows that "two magnitude columns" is a data *shape*, not a chart. The timeline sample
  mirrors the xrange one on the **other** axis, and for the same purpose: both carry dates
  and neither carries a magnitude, but a release plan's rows have EXTENT (two coordinates,
  so the mark is a bar) and a milestone list has none (one, so the mark is a point) — the
  difference is in the data, not in the drawing. The stackable sample (`Monthly revenue by
  channel`) mirrors the landing dataset the same way: both are multi-series, but only its
  series are **parts of one whole**, which is the property that makes a stacked total mean
  something. Per-sample rationale:
  [`docs/chart-types.md`](docs/chart-types.md#the-sample-datasets).
- `tests/test_smoke.py` — builder unit tests (every chart type, the missing-data and edge
  cases, the validation guards, and an end-to-end pass driving every supported type
  through `Chart.from_options` / `to_js_literal`) and `sample_data` unit tests, plus
  headless `AppTest` interaction tests. Prefer finding a widget by **label** — positional
  indices (`app.selectbox[1]`) are still the majority idiom in the older AppTests and are
  fragile: one selectbox added above shifts every index at once. There is one
  `_pick_*_sample` helper per type that needs a non-landing dataset, each sharing
  `_pick_sample(app, chart_type)` as its body while keeping its own name and its own
  argument for why that type needs a dedicated sample. Every AppTest that switches chart type
  goes through `_select_chart_type(app, chart_type)`, which sets the family and then the type,
  and every Y-pills assertion reads `_y_pills(app)`: the family control is a pills widget too,
  drawn above the Y pills, so a bare `app.pills[0]` would silently mean the family.
- `tests/test_hooks.py` — unit tests for the `.claude/hooks/` scripts: the pure decision
  functions (`is_python_target`, `has_dirty_python`) plus a black-box check of
  `post_edit_py.py`'s exit-code contract (0 lets the edit through) without spawning the
  toolchain.
- `tests/test_release.py` — unit tests for `.github/scripts/release.py` (CI's release
  tooling, the `test_hooks.py` sibling): the pure functions that read the version, list
  the changelog's versions, slice a `CHANGELOG.md` section out *verbatim*, and decide
  which versions sit above the latest-release watermark. It also pins `main()`'s CLI
  contract, since the workflow parses its stdout: `version` prints *only* the version, bad
  args exit 2 writing nothing to stdout — so a stray print can't corrupt a tag name.
- `tests/test_packaging.py` — guards the licensing metadata (the `pyproject.toml` SPDX
  `license`/`license-files` fields, `LICENSE`'s pristine MIT text, `NOTICE`'s two
  proprietary layers kept in sync with the README's `## License` section), the README's
  header badges and `## Contents` table of contents, and `CHANGELOG.md`'s newest entry
  pinned to `pyproject.toml`'s `version` — the guard that closed the suite's own
  [blind spot](docs/decisions.md#packaging-the-fact-with-no-second-home) — and the runtime
  `dependencies` pinned **by name** to `highcharts-core`, `pandas` and `streamlit`, so a new
  runtime package fails the suite until `_RUNTIME_DEPENDENCIES` is edited on purpose (the
  `dev` group and the version floors are deliberately not pinned). Reads the files
  directly, no build step.
- `.streamlit/config.toml` — project Streamlit theme: **Studio Slate**, the bundled
  financial-dashboard template's chrome and typography kept, its categorical scale
  replaced by one designed for this app (see Conventions), as a **single `[theme]`**
  (plus `[theme.sidebar]`). That shape is the
  decision, not an omission: defining both `[theme.light]` and `[theme.dark]` is what
  unlocks the in-app light/dark toggle, so a lone `[theme]` locks the app to one mode,
  here **dark**. Pinned by `test_app_theme_is_a_single_mode_with_no_light_dark_toggle`,
  because re-adding a subtable is a change nothing else would object to. Chart colors are
  themed separately (see Conventions) since no theme CSS reaches an iframe.
- `.claude/settings.json` + `.claude/hooks/*.py` — committed Claude Code hooks that mirror
  the CI gates, plus the `permissions.deny` rules that protect `uv.lock`,
  `.streamlit/secrets.toml` and `.git/` (see [Hooks](#hooks)).
  `.claude/settings.local.json` holds per-developer overrides and is gitignored.
- `pyproject.toml` — dependencies + the `dev` group, the project license (MIT, via the
  PEP 639 `license`/`license-files` fields), and the Ruff/ty config.
- `.github/workflows/ci.yml` — GitHub Actions, two jobs. A `gates` job that
  `uv sync --locked` **once**, then runs the three checks the hooks mirror (Ruff
  lint/format, ty, pytest) as separate steps on every push to `main` and every PR — each
  guarded so that one failing step does not skip the rest, and Ruff/ty ahead of pytest so
  a lint or type error reports in seconds. Then a `release` job that `needs` it, runs on a
  push to `main` only, and — under a job-scoped `contents: write` over the top-level
  read-only token — cuts a `v{version}` tag + GitHub release for **every** `CHANGELOG.md`
  version above the latest released one (the watermark), marking only the highest
  `--latest`. Idempotent, so it stays silent on pushes that don't bump. Why
  [one job rather than three](docs/decisions.md#ci-one-gates-job-rather-than-three), and
  why [every version rather than the current one](docs/decisions.md#release-two-bumps-in-one-push)
  (plus the pickaxe, `fetch-depth: 0`, and `concurrency` cancelling PRs only).
- `.github/scripts/release.py` — the pure, stdlib-only reader CI's `release` job calls:
  `version`, `notes VERSION` (raising if the section is absent or empty so a release is
  never cut blank), and `to-release LATEST_TAG` (oldest-first, and **raising** rather than
  failing open on a watermark it does not recognize —
  [why](docs/decisions.md#release-the-watermark-that-failed-open)). It only *reads* facts
  already pinned by `test_changelog_documents_the_current_version`, which reuses this
  module's `changelog_versions` rather than re-encoding the heading regex, so the notes
  cannot drift from the changelog. Pure logic + a thin `main()`, the `.claude/hooks/`
  pattern applied to release tooling; the impure parts stay in the workflow.
- `LICENSE` / `NOTICE` — MIT for this project's own code, kept *pristine* (no text
  appended) so GitHub's detector classifies the repo as MIT; the third-party notice is
  split out because the two proprietary layers the app renders with (Highcharts JS, and the
  `highcharts-core` wrapper) are separately licensed and not
  covered by the MIT grant. Both are declared via `pyproject.toml`'s
  `license`/`license-files` and guarded by `tests/test_packaging.py`.
- `CHANGELOG.md` — the release notes, newest first (Keep a Changelog format). Its top
  `## [x.y.z]` heading is `version`'s **second home**, so a bump that ships without notes
  fails the suite. Everything below `0.7.0` is *reconstructed from git history*, which is
  why the file says so.
- `docs/chart-types.md` — the per-type design record. See [Chart types](#chart-types).
- `docs/decisions.md` — the argument and the incident behind rules stated tersely here.
- `docs/plan.md` — the feature backlog and its direction (`idea` → `planned` → `in progress`
  → `done`, or `deferred`/`dropped` with the reason kept).
  Intentions only; nothing in it is a fact the code must match.

## Chart types

30 supported types. The public API:

```python
# build_options() -> Chart.from_options() -> set container, in one call:
chart = make_chart(df, chart_type, x_col, y_cols, title=title)

# interactive: get_script_tags() + to_js_literal() wrapped as HTML for st.iframe
html = build_chart_html(df, chart_type, x_col, y_cols, height=height, title=title)

# downloads: none — every chart carries Highcharts' ☰ menu (`_EXPORTING`), which draws
# PNG/JPEG/SVG in the browser with the export-server fallback off

# embeds: the chart for other pages, all four forms from one build_options call
exports = build_chart_exports(df, chart_type, x_col, y_cols, container_id=None)
exports.json, exports.js, exports.html_snippet, exports.html_page

# the Python that rebuilds it: a make_chart(...) call, loading the data rather than inlining it
code = python_snippet(chart_type, x_col, y_cols, csv_name="data.csv", style=style)
```

The exports are serialized by the standard library's `json`, not `to_js_literal`, so they are
immune to both strings highcharts-core emits unquoted, and `<`, `>`, `&` are written as `\u003c`
etc. so user text cannot close the `<script>` a snippet is pasted into. The app's own iframe still
uses `to_js_literal` (switching it is plan #16).
`test_no_option_the_builder_sets_is_silently_dropped` keeps the two paths from drawing different
charts: it fails on any key the builder sets that highcharts-core drops on the way to the JS, which
is how the treemap tile border went unapplied until 0.25.0.

Neither takes a mode flag: `_themed` applies the dark chrome unconditionally, because
`.streamlit/config.toml` is a single `[theme]` and every viewer therefore gets the dark
shell. The chart no longer *follows* the shell, it assumes it — which is why
`test_app_theme_is_a_single_mode_with_no_light_dark_toggle` is load-bearing. The removed
`dark=` flag and what its removal traded away:
[`docs/decisions.md`](docs/decisions.md#light-mode-and-its-removal).

Beyond `x_col`/`y_cols`, a type may take one of **9 extra column kwargs**, and which types
share one is a deliberate claim — *a link is a link, but a goal is not a high*. Reusing a
kwarg leaves the cache layer untouched; a new one costs a wrapper and a call site per
renderer, and that cost is paid whenever the **role** differs even though the dtype and
picker source match. It costs no test edit: `_FORWARDED` is **derived** from the builders'
signatures, so the cache-layer checks pick a new kwarg up automatically — but the kwarg
**table below** is pinned by name, so a new row is not optional. Each row's middle cell is
the widget's label *verbatim*, parenthetical included.

The **cheapest** answer is still a type that needs no kwarg at all, and `timeline` is the
standing proof one exists: it spends `x_col` on the event's name and `y_cols[0]` on its
date, so a whole new type landed with this table untouched. That is checkable rather than
asserted — `test_claude_md_states_the_real_extra_column_kwarg_count`,
`test_claude_md_kwarg_table_names_every_extra_column_kwarg` and
`test_forwarded_arguments_derivation_is_not_vacuous` all read the builders' own signatures,
so a tenth kwarg would fail them; all three stayed green through that change, **unedited**.

| Kwarg | Control label | Types |
|---|---|---|
| `size_col` | Size (Z) | bubble |
| `target_col` | Target (to) / Manager (to) | sankey, dependencywheel, networkgraph, organization |
| `parent_col` | Parent (blank = top level) | sunburst |
| `end_col` | End | xrange (a **coordinate**, may be a date) |
| `high_col` | High (top) | columnrange, arearange (a **magnitude**) |
| `title_col` | Title | organization |
| `goal_col` | Goal (target) | bullet (a **reference**, not a far end) |
| `width_col` | Width | variwide (the mark's **other dimension**) |
| `after_col` | After | dumbbell (the same quantity **later** — the one ORDERED pair) |

Three kwargs are **settings**, not column names, so none has a row in the table above (the
tests exclude them by name, in `_SETTING_KWARGS`). The gauge family (`solidgauge`, `gauge`)
takes two of them: `agg=` (one of `GAUGE_AGGREGATIONS`) and `dial=` an explicit `(min, max)`,
derived from the **readings** by `gauge_dial` when `None`. The third is `style=`, one frozen
`ChartStyle` carrying the sidebar's style controls (axis titles, legend, data labels, stacking,
log Y, a reference line); a type takes only the fields `style_controls_for` lists, and the
builder ignores the rest. One object rather than one kwarg per control, so a new control is a
field and a widget, not a new kwarg
([why](docs/decisions.md#style-one-object-not-one-kwarg-per-control)). The gauge family is why
`x_col` is `str | None` on every
builder signature — the family has no label channel, so every *other* type raises when
`x_col` is omitted. The two **unweighted node-link types** (`networkgraph`,
`organization`) are its mirror, taking an **empty** `y_cols`.

The KPI's third metric adapts by `MARK_METRICS` membership, so the KPI stays one branch
however many such types there are. The table is pinned to the dict by
`test_claude_md_mark_metrics_table_matches_the_app`, so a new entry fails the suite until
it is documented:

| Noun | Types |
|---|---|
| Cells / Tiles / Stages | heatmap · treemap · funnel, pyramid |
| Flows / Links / Reports | sankey, dependencywheel · networkgraph · organization |
| Boxes / Steps / Sectors | boxplot · waterfall · sunburst |
| Bars / Ranges / Points | xrange, variwide · columnrange · arearange |
| Measures / Changes / Events | bullet · dumbbell · timeline |

Absent types report "Series plotted". Gauge's absence is a *decision*: its marks **are**
its series, so an entry would restate `len(y_cols)` — the can't-drift rule run backwards.

Timeline sits in the **last** row rather than beside xrange in the fourth, and the row it
joins is the argument. Column *role* would put it with xrange — both spend `y_cols[0]` on a
coordinate — but the table groups by what the **noun** does, and xrange's "Bars" names the
shape drawn. A timeline draws three things per event (a marker, a label, the connector
between them) and counts none of them, exactly as a dumbbell draws three per category and
counts none: so "Events", like "Changes" and "Measures", names the **reading** because there
is no single shape left to name.

**Everything else about a type — its null policy, its `_themed` hooks, its module
resolution, its tooltip token, its guards, and the argument for each — is in
[`docs/chart-types.md`](docs/chart-types.md).** Those arguments are load-bearing, not
history: they are what the next type will be reasoned from.

## Adding a chart type

The project's dominant task, and the one that touches the most files. In order:

1. **Read** [How a chart is built](docs/chart-types.md#how-a-chart-is-built) and the entry
   for the nearest existing type — the shape it shares is usually the whole design.
2. **Build**: add the branch in `highcharts_builder.py`, applying the type's missing-data
   policy to values *and* labels, and `.astype(bool)`-casting every mask (see
   [Conventions](#conventions)).
3. **Theme**: add a `_themed` hook if the type needs one, and **verify by rendering** —
   never infer it from a base class.
4. **Count**: add a `count_marks` rule, and a `MARK_METRICS` entry when the mark count
   differs from `len(y_cols)`; add the row to the table above (the test requires it).
5. **Sample**: add a dataset to `sample_data.py` leading with a category column, and a
   `_pick_*_sample` helper if the landing dataset can't drive it.
6. **Wire**: place the type in one family of `CHART_FAMILIES` (the picker reaches a type only
   through its family; `test_chart_families_partition_the_supported_types` fails until it is
   placed), add its help bullet to `_TYPE_HELP` in `streamlit_app.py`, a `vocabularies` row if the type reads a
   column vocabulary other than `numeric_cols` (the row carries its Y source and both of its
   messages, so this is the one edit a coordinate type cannot half-do), any extra column widget, and
   forward it through both **renderer** cache wrappers **by keyword, under its own
   name** (and through `cached_count_marks` too, if `count_marks` reads it). A new
   kwarg also needs a row in the kwarg table above.
7. **Test**: extend the three [sweeps](#test) rather than writing a per-type test, and
   **verify the new test by breaking the code**.
8. **Sweep the prose**: run both `grep` sweeps in [Conventions](#conventions) over
   `CLAUDE.md` and `docs/chart-types.md`, and fix what they find — including drift you
   did not cause.
9. **Ship**: bump `version` in `pyproject.toml`, add the `CHANGELOG.md` section, and
   commit the `uv.lock` line uv rewrites.

## Run

```bash
uv run streamlit run streamlit_app.py
```

`.streamlit/config.toml` themes the shell and enables `runOnSave`, so saves auto-rerun.
Verify config with `uv run streamlit config show`.

When a stale chart is suspected, **restart the server** — that is what actually clears the
`@st.cache_data` caches (the CSV loader plus one per renderer). They are plain in-memory
caches, so `uv run streamlit cache clear` will *not* flush them: it exits 0 having cleared
only the on-disk persisted cache, and its own source says so. A `runOnSave` rerun does not
clear them either. In-process, `st.cache_data.clear()` or the app menu's **Clear cache**
does the job.

A *blank* chart is usually a network issue instead: the chart loads Highcharts from the CDN
(`code.highcharts.com`, at the pinned `HIGHCHARTS_JS_VERSION`).

**Verify by rendering** (the methodology this project cites everywhere — a new type's
`_themed` hook, null/edge-case geometry, and chart↔download parity are *decided by
looking*, never inferred from a base class): render one chart to a file with
`build_chart_html(df, type, …)`, serve it over `http://localhost`
(`python3 -m http.server PORT --directory <dir>` in the background — `file://` is blocked
by the Claude-in-Chrome extension), then screenshot it. Check it in both **browser** color
schemes: the chart is always dark, so a difference between them is a bug in the
`color-scheme` pin, not a theme. Run scratchpad scripts with
`PYTHONPATH=<repo> uv run python …` — the script's own dir, not the cwd, is on `sys.path`,
so a bare `import highcharts_builder` fails otherwise.

**Verify a new test by breaking the code** — the mutation counterpart to the above, and
the "a vacuous pass is worse than no test" rule turned into a procedure. Copy the source,
make the one edit the test claims to catch (delete the `_themed` hook, flip the null
policy, swap the two slots of a point array, revert a call site to positional), run *that
test alone*, restore, and diff to confirm the source came back byte-identical. A test that
stays green is pinning nothing. Read the failure, not just the exit code: a mutant caught
by `SyntaxError` rather than by the intended assertion is still a hole. It has already
caught a dark-mode test asserting `"#f1f5f9" in js` — that is `_DARK_CHROME["text"]`,
which `_themed` writes to the title, both axis labels and the tooltip on *every* chart, so
the test passed with the hook it existed for deleted outright.

## Test

```bash
uv run pytest
```

`tests/test_smoke.py` exercises the pure builder (`build_options`) parametrized across
every supported chart type, then drives the full app headless via Streamlit's `AppTest`
(switching controls, revealing the generated config, the KPI metric row, the wide-CSV
`st.multiselect` fallback, the absence of a render-mode control, and the guard messages).
Per-type test inventory:
[`docs/chart-types.md`](docs/chart-types.md#the-test-suite-type-by-type).

Three **sweeps** are what cover a newly added type on the day it is added, rather than
whenever someone remembers — prefer extending a sweep to writing a per-type test:

- `test_no_supported_type_emits_a_non_finite_js_literal` — the value channel.
- `test_missing_or_non_finite_label_drops_the_row_in_every_type` — the label channel.
  The gauge family is *excluded* (keyed on `GAUGE_TYPES`): it would pass **vacuously**,
  reading as a pin on a policy the family deliberately does not have.
- `test_row_less_frame_draws_an_empty_chart_in_every_type`, with
  `test_count_marks_casts_every_mask_not_just_the_label_one` (which promotes warnings to
  errors — the only way the non-label casts are observable at all).

The app's **cache layer** is the part the ordinary AppTests barely reach, so it is pinned
from **two** directions: **statically**, by two `ast` tests that read `streamlit_app.py` as
source (each **renderer** wrapper in `_CACHE_LAYER` forwards every column/policy argument
under its **own** name, and every call site passes them by keyword); and **dynamically**, by
`test_app_executes_the_cached_html_wrapper_and_forwards_every_kwarg`, which runs the app with
`build_chart_html` monkeypatched to a recorder. The set of arguments both layers check is
**derived** from the builders' signatures (`_forwarded_arguments`, which excludes
`container_id` by name), not hand-listed, so a new kwarg is covered the day it is added.
There is a further cached wrapper, `cached_count_marks`, deliberately outside `_CACHE_LAYER`:
`_FORWARDED` is derived from the *builders*, so it names `size_col`/`goal_col`/`agg`/`dial` and
the rest — kwargs `count_marks` does not take. It forwards the three columns it actually reads.
Why static, and why that test clears the caches on the way *out*:
[`docs/decisions.md`](docs/decisions.md#the-cache-layer-that-nothing-executed).

**Widget identity** is pinned the same way, and for the same reason — nothing else would
notice its removal. Streamlit folds every command kwarg into a *keyless* widget's element id,
the **label included**, so the X and Y pickers (whose labels vary by chart type while their
options do not) carry a `key=` and would silently reset without one. Five picker AppTests hold that
down, over **three distinct failure modes**: two that a selection survives a label-only
chart-type switch (X, and Y) — re-minting; one that a Dataset switch **reconciles** a stale Y
instead of landing on the empty-Y guard — filtering; and **two** that a stop *above* the pickers
does not forget them — **garbage collection**, which a `key=` alone cannot fix, since Streamlit
drops the stored value of any keyed widget a run never instantiates.
`keep_picker_state()` (naming the keys in `_KEYED_PICKERS`: the X and Y pickers' and the
style controls') re-assigns each entry to
itself in front of such a stop, which is the documented opt-out; it reads like a no-op and is
not one. The fifth test adds **no fourth mode** — it is garbage collection again, reached through
the *other* early stop (backing out of an upload that was never made), because the mode belongs to
the **stop** rather than to the gate: both stops above the pickers now call
`keep_picker_state()` and none is exempt. Note the two widget families differ and the code differs
with them — `selectbox` *resets* an invalid stored value on its own (so X needs no
reconciliation), while `multiselect`/`pills` *filter* theirs to `[]` (so Y does). The rule that
separates a correct loss from a bug: a selection may be dropped when it stopped being **valid**
(the widget reconciles it), never when it merely stopped being **rendered**. Verify any change
here by breaking it; all five mutations are one-liners (the last two: delete either
`keep_picker_state()` call).

The **data editor** (the editable Source data table) is the case garbage collection cannot be
patched around, so its edits do not live in widget state at all. A gate that stops above the table
discards the editor's state, and a data editor cannot be restored from session state, so
re-assigning its key at the stop (the pickers' fix) kept the edit for the CHART while the redrawn
table showed the original: worse than losing it, and seen only by rendering. The app keeps its own
store (`_CELL_EDITS`, one dataset at a time), merges the editor's latest edits into it on every
run (`merge_cell_edits`), applies them before the pickers read `df` (`apply_cell_edits`), and draws
the editor over the EDITED frame, which is safe because edits are absolute cell values. AppTest
cannot type into a data editor; the tests set its session state once, which the store then keeps.

The **style controls** meet garbage collection twice, and each has its own AppTest. A stop above
them is the pickers' case, closed by listing their keys in `_KEYED_PICKERS`. The new one is a
control the chart type simply **hides** (pie draws none): no stop is involved, so
`keep_hidden_style_state()` re-assigns only the hidden keys on every run. Only the hidden ones,
because re-assigning a key whose widget is drawn later in the same run counts as setting it
through the Session State API. The widgets use their natural defaults (empty, off, the first
option) for the same reason: Streamlit only objects to an explicit default on a widget whose
value was set through the API, and those defaults never count as explicit.

## Lint & format

Ruff does both; config is in `pyproject.toml`. (CI and the hooks run these same
gates — see Structure's `ci.yml` bullet and Hooks.)

```bash
uv run ruff check --fix . && uv run ruff format .   # fix + format
uv run ruff check . && uv run ruff format --check .  # verify (as CI does)
```

Note `ruff format` also formats ```python fences in Markdown, so `CLAUDE.md`, `README.md`,
`CHANGELOG.md` and `docs/*.md` are in scope for the format gate even though the hooks
(which route on `.py`) ignore them.

## Type check

[ty](https://docs.astral.sh/ty/) (Astral's type checker, pinned in
`pyproject.toml`) needs the project venv to resolve imports, so run it through
`uv run`:

```bash
uv run ty check
```

A few highcharts-core stub mismatches (Optional `options`/`chart`,
`to_js_literal` typed `str | None`) are suppressed inline with
`# ty: ignore[rule]`, not by downgrading rules globally — so the rules still
catch the same problems in our own code.

## Release

Releases are cut by CI, never by hand. To ship a version, bump `version` in
`pyproject.toml` **and** add a matching `## [x.y.z]` section to `CHANGELOG.md`
(pinned together by `test_changelog_documents_the_current_version`, so a bump
without notes fails the suite). On the next push to `main`, the `release` job in
`ci.yml` cuts the annotated tag + GitHub release from that section — for every
version above the latest release, so two bumps in one push both ship — and marks
only the highest `--latest`. It is idempotent (a push that doesn't bump the
version cuts nothing), so do not tag or `gh release create` by hand.

Bumping `version` also makes the next `uv run` rewrite `uv.lock`'s own
`highcharts-studio` version line; commit that with the bump. The `Edit(uv.lock)` deny rule
blocks *manual* edits to the lockfile, but uv's own re-sync is expected, not a stray
change.

## Hooks

`.claude/settings.json` wires two project hooks (committed; the per-developer
`.claude/settings.local.json` stays gitignored) that mirror the CI gates so edits
stay green before a push. Each is a stdlib-only Python script under
`.claude/hooks/`, run via `uv run --project "$CLAUDE_PROJECT_DIR" python …` so it
executes on the project's pinned 3.12 interpreter — the same one the tests use,
not the machine's system `python3` — and keeps its decision logic in a pure,
importable function that `tests/test_hooks.py` covers. The scripts are themselves held
to those gates: `ruff check .` and `uv run ty check` include `.claude/hooks/` (dot-dirs
aren't excluded), so the tooling that enforces the app enforces the hooks too.

- `post_edit_py.py` (PostToolUse on `Edit`/`Write`/`MultiEdit`) — on a `.py`
  edit, runs `ruff check --fix` + `ruff format` in place, then `ty check`; exits
  2 on type errors so the diagnostics feed back to fix. Mirrors the Ruff and ty
  gates. Gotcha: since this runs `ruff check --fix` after **every** `.py` edit, add a
  new import and its first use in the **same** edit (or the use first) — split across
  two edits, the fix prunes the not-yet-used import and the next `ty` pass fails on the
  now-undefined name. `Edit` replaces exactly one region, so when the import and its first
  use are far apart (an import block at the top, a use 200 lines down) *no* pair of Edits
  can satisfy this — land both with a single `Write`, or a one-shot script that does the
  two replacements in one pass.
- `pytest_stop.py` (Stop) — runs `uv run pytest` when the working tree has
  uncommitted `.py` changes (app, test, or the hook scripts under
  `.claude/hooks/`); exits 2 on a real failure (pytest exit 1/2) to feed the
  output back, treating a tooling/env failure as a no-op, with a
  `stop_hook_active` guard so it can't loop. Mirrors the test gate. Note it routes on
  `.py`, so a docs-only change does **not** trigger it — run `uv run pytest` yourself after
  editing `CLAUDE.md`, which the suite parses.

There is deliberately **no PreToolUse path guard**. `uv.lock`, `.streamlit/secrets.toml`
and `.git/` are protected by `permissions.deny` rules in the same `settings.json` instead,
which is strictly stronger: the permission engine runs **before** any hook and applies to
every path into the filesystem, not just the tools a `matcher` names — so it also catches
a Bash output redirection (`echo … > uv.lock`), which an `Edit|Write|MultiEdit` matcher
never sees. Why each of the three rules is spelled the way it is:
[`docs/decisions.md`](docs/decisions.md#permissions-why-each-deny-rule-is-spelled-the-way-it-is).

Adding or changing a hook triggers Claude Code's one-time hook-review prompt
before it runs.

## Conventions

Each rule below is stated with its mechanism. The per-type worked examples are in
[`docs/chart-types.md`](docs/chart-types.md) (see its Appendix for these same
conventions in their original, fully-enumerated form); the argument behind each is in
[`docs/decisions.md`](docs/decisions.md).

- **Astral tooling.** When working with Python, invoke the relevant Astral skill
  (`/astral:uv`, `/astral:ty`, `/astral:ruff`) for uv, ty, and ruff to ensure best
  practices are followed.
- **Streamlit-free builder.** Keep chart-building logic (DataFrame → Highcharts) in
  `highcharts_builder.py`, free of Streamlit imports, so it stays unit-testable.
- **Pure decision functions.** Keep each hook's decision logic in a pure, importable
  function in `.claude/hooks/` (as the builder is), so `tests/test_hooks.py` can cover it
  without subprocesses; the `main()` wrapper handles the stdin/exit-code plumbing and any
  impure subprocess orchestration (ruff/ty/pytest/git). `.github/scripts/release.py`
  follows the same split for CI, tested by `tests/test_release.py`; both load their script
  by file path via `tests/conftest.py`'s `load_script`.
- **Validate CI bash before pushing.** The `release` job in `ci.yml` carries real bash:
  `shellcheck -s bash` the extracted `run:` block and structure-check the file with
  `uv run --with pyyaml` (neither is a project dep). Exercise the script on the
  interpreter the job uses:
  `uv run --no-project --python 3.12 python .github/scripts/release.py to-release vX.Y.Z`.
- **Adding a chart type falsifies prose nobody edited.** The docs are dense with
  uniqueness claims, and each is a claim about *every other type* — including ones that
  don't exist yet — so a new type can make a sentence false in a passage no diff touched,
  locally correct on both sides, with only the *pair* contradicting. Nothing mechanical
  can see it. **Closing a recorded open case does the same thing** — the trigger is a new
  *instance of a property*, which a fix produces as readily as a new type does: applying the
  tooltip-granularity rule to `xrange` added no type and still falsified "that matters **here and
  nowhere else in the app**" — while the superlative beside it, scoped to a timeline's own
  channels, survived untouched. So sweep after either, over **both `CLAUDE.md` and
  `docs/chart-types.md`** (and the builder's own comments, which carry the same claims):

  ```bash
  grep -noE 'the [*_`]*(one|only)[*_`]* [a-zA-Z*`_.]+ [a-zA-Z*`_.]+' CLAUDE.md docs/chart-types.md
  grep -noE 'the [*_`]*(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)' \
      CLAUDE.md docs/chart-types.md
  ```

  The emphasis class before the claim word (``[*_`]*``) is load-bearing rather than
  defensive: these docs **bold the very word the claim rests on** ("the **ninth** column
  kwarg", "the **only** type whose marks are not in the data"), so without it both sweeps
  skipped precisely the emphasized hits — the strongest claims in the file, and therefore
  the ones most worth checking. Every real ordinal claim above `sixth` in
  `docs/chart-types.md` — they cluster in the kwarg numbering, which is the one place a
  high ordinal is *used* — was invisible to the sweep that was supposed to find it.

  Check each hit against the code, and read the **paragraph** out from it rather than the
  matched line: neither regex can match a stale *cardinal* or a stale *name*, and both of
  the ones fixed in 0.20.0 were found sitting beside a hit rather than at one. The sweep catches
  **pre-existing** drift too, not only what you just added — fix what it finds, not only
  what your diff caused. Note the second regex is itself a tally that goes stale: each new
  type can push an ordinal past the end of the alternation, so extend it rather than
  assuming it still covers the top of the range (`eleventh` became reachable with the
  gauge family's two policy kwargs, which sit above the nine column ones).

  Bare **cardinals** are deliberately *not* swept — the signal rate is far too low to
  survive being run by hand
  ([why](docs/decisions.md#prose-drift-why-cardinals-are-not-swept)). Counts that scale
  with chart types are pinned mechanically instead, by the docs-count tests in
  `tests/test_smoke.py`: the supported-type count in both docs, the extra-column kwarg
  count, the kwarg table checked **by name** (so a rename cannot pass by keeping the total
  the same), and the `MARK_METRICS` table. Two consequences for prose: a count that scales
  needs no sweep but **must** appear in a form one of those tests reads, and new prose
  about a type-scaled set should prefer a **rule** ("one selector per extra column kwarg")
  to a **tally** — a rule cannot go stale.
- **Highcharts only.** Render every visualization with `highcharts-core`; do not use
  native Streamlit charts.
- **Null policy.** Use `EnforcedNull` (from `highcharts_core.constants`) for missing data
  points in dict configs fed to highcharts-core, **not** Python `None`. **There is exactly
  ONE exception, and it is exactly one slot wide: a bullet point's GOAL — the second
  element of its `[measure, goal]` array — must be Python `None`.** Do not "fix" it back;
  it raises one layer *below* `build_options`, so the options-dict suite stays green while
  the chart cannot be built at all
  ([mechanism](docs/decisions.md#the-bullet-goal-that-must-be-none)). Pinned by a test that
  drives `make_chart` rather than `build_options` — the only layer at which the failure is
  observable.
- **Row-less frames.** A frame with columns and no rows (a CSV with a header and no data)
  is a legitimate input and must draw an **empty chart, not raise**. Every
  `Series.map(...)` used as a mask must therefore be `.astype(bool)`-cast: `.map()` infers
  its result dtype from the values it produced, and with no rows there are none, so it
  returns an empty **non-boolean** Series. A DataFrame indexed by one is read as a list of
  **column names** — one shared line, so this killed *every* type at once, and a new type
  inherits the bug the day it is added unless the cast is there
  ([the other two failure modes](docs/decisions.md#row-less-frames-three-ways-a-non-boolean-mask-breaks)).
- **Non-finite is missing.** `pd.isna(inf)` is `False`, but an infinity can't be
  serialized: `to_js_literal` emits the bare token `inf`, which is not a JavaScript
  identifier (JS spells it `Infinity`), so the chart call dies with a `ReferenceError` and
  the iframe renders blank (the retired export server, sent the non-standard JSON literal
  `Infinity`, answered `400`). Each type applies its own missing-data policy to a non-finite
  **value** — keep-the-slot types via `_num`, drop-the-row types via `_plottable`, the
  aggregating types via `_finite_values` — and the same policy governs the **label** column
  via `_label_ok`. Reachable from a plain CSV: `inf`, `Infinity`, `-inf` and `1e400` (which
  silently overflows), and a blank cell (`nan`). One trap is pandas', not Highcharts': an
  **empty** column sums to `0.0`, the additive **identity** — a confident claim of "the
  total is zero" where the truth is "there is no data" — so `_gauge_value` tests for empty
  **above** the reducer. Only `sum` lies, which makes it worse rather than better.
- **Two string shapes the serializer emits UNQUOTED**, and both blank the **iframe** — and
  its download, which re-renders it in the browser (the retired export server, built from JSON,
  rendered them perfectly, which is how they hid). No options-dict test can see it, so
  assert on `to_js_literal()` output, never on the dict. (1) A value that opens `{`, closes `}`
  and carries **at least as many colons as brace-pairs** is written as a bare JS object on **any
  key and any axis** —
  `{"format": "{value:%b %Y}"}` becomes `format: {value:%b %Y}`. It is a property of the VALUE:
  `dataLabels.format` and a series `pointFormat` are **not** exempt, and the timeline and xrange
  tooltips — the two interpolating `_TOOLTIP_INSTANT`/`_TOOLTIP_DAY` — are
  safe only because they open with `<b>`. Read that narrowly: stripping the whole
  `<b>{point.name}</b><br/>` prefix removes the brace-pair that SUPPLIED the margin, so under it
  every form of both types goes bare — the widened precision introduces no new margin of its own,
  since each added colon arrives inside an added brace-pair (the `{point.name}: {point.y}` pie,
  funnel and pyramid
  share is safe only because it is one colon short of its two brace-pairs — add a `:.1f` and it
  goes through bare). Swept by
  `test_no_supported_type_emits_an_unquoted_format_object`, whose pattern is
  `[A-Za-z]*[Ff]ormat:\s*\{` and must stay so: the literal `format: {` misses `pointFormat`.
  (2) Any string beginning `Date`
  except exactly `"Date"` is emitted as raw JS — a **library bug**, reachable from a chart title,
  a column name or a point label, deliberately **not** worked around (every fix would mutate text
  the user typed) and pinned as still-present by
  `test_a_string_beginning_with_date_is_emitted_unquoted_by_the_library`
  ([the reproduction and the trade](docs/decisions.md#the-strings-highcharts-core-emits-unquoted)).
- **Never rely on a Highcharts default.** `build_chart_html` pins the chart's
  `color-scheme` to `only light` (`_LIGHT_COLOR_SCHEME_CSS`, on the `.highcharts-root`
  `<svg>`, **not** `html` —
  [why the pin must sit that low](docs/decisions.md#color-scheme-why-the-pin-sits-on-the-svg)).
  Highcharts ≥ 13 expresses its own defaults as `light-dark()` CSS variables, so any color
  the project does *not* set would follow the **viewer's browser**; the pin leaves `_themed` the
  single source of truth for the dark chrome. Anything a new chart type wants themed must go
  through `build_options`. Export has defaults of its own, and the same rule applies to them:
  `_EXPORTING` sets `sourceWidth: 800` because the browser's export otherwise lays the chart out
  at **600px** (the embed's `width:100%` gives it no pixel width to read), as the retired export
  server did. Highcharts lays out text at the width it is given and **truncates** labels at 600
  ("Incorporat"), which no rescaling undoes; it bites every type and bites hardest where a label
  IS the mark's identity. The menu's chrome is themed in `_themed` too, except the ☰ button's
  hover fill, which options cannot express and `_EXPORT_BUTTON_CSS` sets
  ([why](docs/decisions.md#static-png-mode-and-its-retirement)). The **Highcharts release itself** is the largest default
  of all: highcharts-core emits unversioned CDN URLs, which serve whatever Highcharts released
  last, so `_pin_script_tags` rewrites every script to `HIGHCHARTS_JS_VERSION` (and raises on a
  URL it cannot pin, rather than let one module load a different release). An upgrade is a
  deliberate edit: bump the constant, render-check, ship. Never pin below **11.4.4**
  ([why](docs/decisions.md#highcharts-js-one-pinned-release)).
- **Chart colors.** Theme via `highcharts_builder.DEFAULT_COLORS` (applied by
  `build_options` to every chart, so its downloads are themed too). It **is**
  `.streamlit/config.toml`'s `chartCategoricalColors`, copied by hand because no theme CSS
  reaches an iframe; `_DARK_CHROME`'s `bg`/`text`/`muted`/`grid` are
  likewise its `backgroundColor`/`textColor`/`grayColor`/`borderColor`, and
  `_HEATMAP_GRADIENT`'s two endpoints come off its `chartSequentialColors`. All of it is
  guarded by `test_theme_colors_stay_in_sync_with_config`, so the copy fails the suite
  rather than drifting. The categorical scale is **designed, not inherited** — the chrome
  came from the upstream template and the palette no longer does, because a template's
  palette is a chart palette only by accident
  ([why, and what it measured](docs/decisions.md#palette-the-scale-that-was-a-palette-by-accident)).
  Two guards hold it: nothing may **be** a chrome colour
  (`test_no_series_colour_collides_with_the_chart_chrome`, identity), and no two entries
  may **read as** one colour, dichromacy included
  (`test_no_palette_pair_collapses_under_colour_vision_deficiency`, CIEDE2000). The second
  is the one the first could not express, and the template's blue and violet failed it at
  **0.31** while passing everything else in the suite. The
  palette's **order** is load-bearing beyond its hues — `_WATERFALL_*` and
  `_BOXPLOT_OUTLIER_COLOR` index into it, so a reshuffle repaints "a rise" and "a loss".
  Its **lightness** is load-bearing too, and only in one direction: under deuteranopia a
  green and a red both simulate to yellows, so the rise/fall pair is separated by L\*
  rather than hue — and a saturated red tops out at L\* 68 while a green reaches 84, so the
  rise is necessarily the lighter mark. The fall buys prominence with **chroma** instead.
  There is one mode, and a constant written at build time then overwritten by `_themed` is
  the smell that a second one is still hiding. Two marks sit outside the categorical
  palette: `heatmap` colors its cells by a sequential `colorAxis`, and `bullet`'s goal
  crossbar carries a **fill plus a border** — one value per surface, because it crosses
  both the bar and the background and no single colour can be legible on both. A mark whose
  legibility is a property of a PAIR needs its test written over the pair; a per-path hex
  assertion cannot see it, and did not. Invent no new colors: alias existing ones
  (`_NEEDLE_PIVOT_COLOR = _SUNBURST_ROOT_COLOR`) so paired values cannot drift.
