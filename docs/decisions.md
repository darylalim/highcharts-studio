# Decisions

The arguments and incidents behind rules stated tersely elsewhere.

`CLAUDE.md` states the **rule** and the **command**; per-type design detail lives in
[`chart-types.md`](chart-types.md); this file carries the **argument** and the
**incident** — the reasoning that justifies a rule, and the bug that bought it. None of
it is needed resident in a context window to work on the project, but all of it is what
the next decision should be reasoned from. Nothing here is history for its own sake: each
entry exists because a rule elsewhere looks arbitrary without it.

## Contents

[Packaging: the fact with no second home](#packaging-the-fact-with-no-second-home) ·
[CI: one gates job rather than three](#ci-one-gates-job-rather-than-three) ·
[Release: two bumps in one push](#release-two-bumps-in-one-push) ·
[Release: the watermark that failed open](#release-the-watermark-that-failed-open) ·
[Permissions: why each deny rule is spelled the way it is](#permissions-why-each-deny-rule-is-spelled-the-way-it-is) ·
[Prose drift: why cardinals are not swept](#prose-drift-why-cardinals-are-not-swept) ·
[The cache layer that nothing executed](#the-cache-layer-that-nothing-executed) ·
[Keyed widgets: the third way a picker loses its answer](#keyed-widgets-the-third-way-a-picker-loses-its-answer) ·
[Light mode, and its removal](#light-mode-and-its-removal) ·
[The bullet goal that must be `None`](#the-bullet-goal-that-must-be-none) ·
[Row-less frames: three ways a non-boolean mask breaks](#row-less-frames-three-ways-a-non-boolean-mask-breaks) ·
[`color-scheme`: why the pin sits on the SVG](#color-scheme-why-the-pin-sits-on-the-svg) ·
[Palette: the scale that was a palette by accident](#palette-the-scale-that-was-a-palette-by-accident) ·
[The strings highcharts-core emits unquoted](#the-strings-highcharts-core-emits-unquoted) ·
[Tooltip precision: when a channel is a value's only home](#tooltip-precision-when-a-channel-is-a-values-only-home) ·
[`</script>` in user text: an encoding, not an edit](#script-in-user-text-an-encoding-not-an-edit) ·
[Large data: the turboThreshold bug that was not there](#large-data-the-turbothreshold-bug-that-was-not-there) ·
[Highcharts JS: one pinned release](#highcharts-js-one-pinned-release) ·
[Static PNG mode, and its retirement](#static-png-mode-and-its-retirement) ·
[Hosting: a public demo on Community Cloud](#hosting-a-public-demo-on-community-cloud) ·
[Style: one object, not one kwarg per control](#style-one-object-not-one-kwarg-per-control) ·
[Chart-type picker: families, then types](#chart-type-picker-families-then-types) ·
[Embeddable exports: JSON first](#embeddable-exports-json-first) ·
[Export as Python: load, don't inline](#export-as-python-load-dont-inline) ·
[Editing data: the app keeps the edits](#editing-data-the-app-keeps-the-edits)

## Packaging: the fact with no second home

`tests/test_packaging.py` guards the licensing metadata, the README's badges and table of
contents, and `CHANGELOG.md`'s newest entry against `pyproject.toml`'s `version`. That
last guard closed the suite's own blind spot.

`version` was the single packaging fact with **no second home**. Every other fact in the
file was stated twice — the SPDX `license` field against the `LICENSE` text, the `NOTICE`
layers against the README's `## License` section — so any of them could be checked by
comparing the copies. `version` was stated once, so unlike every other it could neither
drift nor be checked. It duly went stale: **five chart types shipped under `0.6.0`**
because nothing asked the number to move.

The fix was to give it a second home rather than to write a smarter test — `CHANGELOG.md`'s
top `## [x.y.z]` heading — which is why a bump that ships without notes now fails the
suite. This is the same mechanical-sync idea as
`test_theme_colors_stay_in_sync_with_config`, and the generalization is the rule the docs
now follow everywhere: **a fact with one home decays silently.**

## CI: one gates job rather than three

The three gate jobs (Ruff, ty, pytest) were collapsed into a single `gates` job that
`uv sync --locked` **once**. The obvious cost of collapsing is that a job stops at its
first failing step, which would make one job strictly *less* informative than three — a
push whose lint failed would say nothing about types or tests.

What buys the informativeness back is the guard on each gate step:

```yaml
if: ${{ !cancelled() && steps.sync.outcome == 'success' }}
```

`!cancelled()` is what makes a step run even though an earlier step failed, so a single
push reports lint **and** type **and** test status rather than only the first to break —
while a failed step still fails the job. The `steps.sync.outcome` half keeps that from
degenerating: if the dependency sync itself failed there is nothing meaningful to run, and
three more red steps would be noise rather than signal.

Ordering is deliberate too: Ruff and ty run before pytest, so a lint or type error reports
in seconds rather than after the suite.

## Release: two bumps in one push

The `release` job cuts a tag and a GitHub release for *every* `CHANGELOG.md` version above
the latest released one, not merely for the current version. That is load-bearing, not
thoroughness.

`0.10.0` and `0.11.0` both reached `main` before either was released. A job that released
only the version currently in `pyproject.toml` would have tagged `0.11.0` and left
`0.10.0` un-released **forever** — the watermark moves past it, so no later push ever
reconsiders it. Releasing everything above the watermark makes the job self-healing
instead: a version missed for any reason ships on the next push.

Each version is tagged at the commit that *declares* it — HEAD for the current one, else
the bump commit located by a `git log -S` pickaxe over `pyproject.toml`, which is why the
checkout is `fetch-depth: 0`. Notes are sliced out of `CHANGELOG.md` verbatim, and only
the highest version gets `--latest`.

The top-level `concurrency` cancels superseded runs for **PRs only**. Main pushes
serialize instead, because a release job killed mid-run can strand a pushed tag with no
release attached to it — a state no later push repairs, since the tag already exists.

## Release: the watermark that failed open

`to-release LATEST_TAG` **raises** on a watermark that is present but is not a changelog
version. It used to fail *open* and return every version in the file, which would
resurrect the deliberately release-less `0.1.0`–`0.6.0` tags as six spurious releases.

The workflow feeds it a watermark only from a `gh` call whose failure is an **error**.
`gh release view` exits 1 both for "no releases yet" and for a transient 5xx, and
swallowing that status made a blip read as the former. The consequence was quiet and
permanent: the "no releases yet" branch releases only the current version, so a 5xx during
a two-bump push drops the intermediate version for good — and the job reports **green**
while doing it.

Both bugs share a shape worth recognizing: an error path that degrades to a *plausible*
answer rather than to a stop. Prefer raising.

## Permissions: why each deny rule is spelled the way it is

`uv.lock`, `.streamlit/secrets.toml` and `.git/` are protected by `permissions.deny` rules
rather than by a `PreToolUse` hook. The permission engine runs **before** any hook and
applies to every path into the filesystem, not just the tools a `matcher` names — so it
also catches a Bash output redirection (`echo … > uv.lock`), which an `Edit|Write|MultiEdit`
matcher never sees. That is strictly stronger than the `guard_paths.py` hook it replaced.

Three details make the three rules a faithful replacement:

- Claude Code consults **only** `Edit(...)` and `Read(...)` path rules, and warns at
  startup on a `Write(...)`/`MultiEdit(...)` path rule it will never check — so the one
  `Edit` rule covers all three edit tools, and writing `Write(uv.lock)` would silently
  protect nothing.
- A **bare filename** follows gitignore semantics: `Edit(uv.lock)` is `Edit(**/uv.lock)`,
  matching at any depth. That reproduces the retired hook's match-by-basename rather than
  pinning one location.
- `Read(...)` also blocks Edit and Write on the same path, so the secrets rule is a
  **`Read`** deny: it keeps the file out of the context window, which a `PreToolUse` hook
  on the edit tools could not do at all.

`.git` is additionally a built-in **protected path** (writes are never auto-approved
outside `bypassPermissions`), but that only *prompts*; the deny rule blocks outright in
every mode, which is why it is still written out rather than left to the default.

## Prose drift: why cardinals are not swept

Bare cardinals ("the four extra column selectors") are the same bug the `the one|only` and
ordinal sweeps exist for — a number in prose is a fact about the code with no second home
— and they have drifted twice: in `chart-types.md` and in `tests/test_smoke.py`'s AppTest
preamble, both saying "the four"/"the three" long after there were nine.

A sweep is nevertheless the wrong instrument for them. Widened to cardinals it turns up
**~59 hits** across the docs and the source against **~1** real one, because almost every
cardinal is structurally fixed — "the two ends of a bar", "the three builders". A signal
rate that low does not survive being run by hand on every added type; it gets skipped, and
a skipped sweep is worse than no sweep because it is still cited.

So the counts that **scale with chart types** are pinned mechanically instead, by the
docs-count tests in `tests/test_smoke.py`. The two consequences for prose are the rule
CLAUDE.md now states: a type-scaled count must appear in a form one of those tests reads,
and new prose about a type-scaled set should prefer a **rule** to a **tally**.

## The cache layer that nothing executed

`cached_chart_html` and `cached_chart_js` (since 0.25.0, `cached_chart_exports`) were covered only *indirectly*. `cached_chart_png`
was, for a long time, executed by **nothing** — the AppTests stay on the network-free
interactive path, so the Static PNG wrapper was never entered by any test at all.

It is now pinned from **two** directions, because the network and the wiring are separable
and only the network was ever worth avoiding:

- **Statically**, by two `ast` tests that read `streamlit_app.py` as source. Static
  because `import streamlit_app` **executes the whole Streamlit script** — and because it
  catches what the keyword form cannot: `goal_col=high_col` type-checks, caches, and
  renders the wrong column while every assertion about *names* passes.
- **Dynamically**, by a test that runs the app with the builder monkeypatched to a recorder,
  so forwarding is observed as **values**. It was written for `cached_chart_png`
  (`test_app_static_png_mode_executes_the_cached_png_wrapper`, selecting Static PNG with no
  export server contacted); since that mode's retirement in 0.21.0 it is
  `test_app_executes_the_cached_html_wrapper_and_forwards_every_kwarg`, on `cached_chart_html`.

That dynamic test clears the `@st.cache_data` caches on the way **out** as well as in.
`monkeypatch` restores the function but not the cached *value*, so a stand-in result left
behind would be served to any later render with the same arguments — which would then pass
**without calling the builder at all**, reintroducing the exact vacuity the test was written
to end.

## Keyed widgets: the third way a picker loses its answer

The X picker and the multi-select Y picker carry a `key=` because their **labels** vary by chart
type ("Category (X) axis" against "Event labels"; "Series (Y) — one or more" against
"Rings (Y) — one or more") while their options do not, and Streamlit folds every command kwarg —
the label included — into a *keyless* widget's element id. Without a key, a relabel re-mints the
widget and discards a selection that was still entirely valid. (The single-select Y — drawn for every type that takes one
value column, xrange and timeline included — is keyless, which is why `_KEYED_PICKERS` names three
keys and not four: `x_col` plus the pills/multiselect pair, which are one control under two
commands.)

The key fixes that one failure, and there are **three**, which is the whole content of this
entry. They are worth enumerating because each has a different cause and a different fix, and
two of them look like the first:

1. **Re-minting.** A label-only change gives a keyless widget a new identity, so the answer is
   gone. Fixed by the `key=` itself. Pinned by the two label-only-switch AppTests.
2. **Filtering.** `multiselect` and `pills` do *not* reset a stored value that is no longer a
   valid option, they filter it to `[]` — so a Dataset switch lands the page on the empty-Y
   guard where the keyless version drew a chart. `selectbox` behaves differently and *resets*,
   which is why only Y carries the reconciliation seed. Pinned by
   `test_app_dataset_switch_reconciles_a_stale_y_selection`.
3. **Garbage collection.** Streamlit discards the session-state entry of any keyed widget a run
   does not **instantiate**. The key survives a rerun; it does not survive a run that never
   reaches the widget. So an early `st.stop()` above the pickers silently forgets them — the
   exact degradation the keys exist to prevent, arriving down a path the key cannot defend.
   Pinned twice, because it is one mode reached through two different stops: the vocabulary
   gate's, and the no-CSV-uploaded one's (see the end of this entry, where the second stop's
   exemption was measured away).

The third was **measured**, not deduced. On the landing dataset: choose X = `cost`, switch to
`timeline` (that frame has no date column, so the vocabulary gate errors and stops), switch back
to `line` — and X comes back at `month`. After `keep_picker_state()`, it comes back at `cost`.

Two things about that measurement are worth keeping. First, it **predates timeline**: xrange's
gate has always stopped above the same two pickers, so this release did not introduce the shape —
the failure has been live since the pickers were **keyed** in `0.18.1`, a keyless widget having
no stored entry to collect. What timeline changed is *reachability*: a frame with no coordinate
column at all is an unusual upload, while a frame with no date column is the app's own landing
dataset, two clicks from a cold start. A latent bug and an everyday
one differ only in the data, which is an argument for fixing the shape rather than the case.
Second, the fix is a **re-assignment of each entry to itself** (`st.session_state[k] =
st.session_state[k]`), the documented way to opt a key out of that cleanup. It reads as a no-op,
so it lives in a named function with the measurement attached rather than inline at the call
site — an inline no-op is what a later "simplification" deletes.

The rule for the next early stop: **a `st.stop()` above a keyed widget is a state deletion, not
a control-flow choice.** This entry granted that rule exactly one exemption, and **the exemption
did not survive being measured**. The no-CSV-uploaded `st.info(...)` + `st.stop()` further up the
sidebar has the identical shape, and it was left alone on the ground that *the user is replacing
the frame, so forgetting a column chosen against the old one is a defensible answer rather than a
loss*. The premise is false at precisely the moment that stop fires: it fires when **no file has
been uploaded**, so there is no new frame and the old one is still on screen the instant the user
goes back. Measured — X = `cost` on the landing dataset, switch Source to Upload CSV, choose
nothing, switch back to the same sample — the columns never moved, nothing was replaced, nothing
needed reconciling, and the answer was deleted anyway. `keep_picker_state()` now runs in front of
that stop too, and `test_app_backing_out_of_an_upload_does_not_forget_the_keyed_pickers` pins it.

The distinction the exemption was drawn on — *"this data cannot do that"* against *"there is no
data yet"* — was the wrong axis, and what shows it is a **third** flow neither of those names.
A **Dataset** switch also loses a selection, and is **not** a bug: X = `cost` on the landing
frame, switch to `Fruit sales`, and the picker comes back at `fruit` (measured). The sharper
rule, and the one to carry forward:

> A selection may be dropped when it **stopped being valid**. It may not be dropped when it
> merely **stopped being rendered**.

The first is **reconciliation**, and it belongs to the widget: `cost` is not a column of the fruit
frame, so the selectbox resets it (`pills`/`multiselect` filter theirs instead, which is failure
mode 2 above and why only Y carries a seed). The second is **garbage collection**, and it is not
an answer to anything — it happens because a run ended early, and it deletes a still-valid
selection exactly as readily as a stale one. The old axis **licensed** the no-CSV stop by calling
it *"there is no data yet"*; the new one refuses it, because "no data yet" describes the **run**
and the rule is about the **value** — and nothing there had invalidated a value.

That is also why preserving state in front of a stop stays safe when a file **is** uploaded and
the frame really does change. `keep_picker_state()` restores only the *stored* value; a column the
new frame does not have is still reset by the picker itself, the same mechanism the Dataset switch
above relies on. Reconciliation is not being suppressed — it is being left to the widget, the only
place that knows the new options.

So there are now **two** stops calling `keep_picker_state()`, and **no exempt early stop is left**:
the no-plottable-columns gate and the no-CSV-uploaded one are the only two `st.stop()`s in
`streamlit_app.py` that sit *above* the pickers, and every other one sits below them, where the run
has already instantiated them and there is nothing to collect. A new stop added above them inherits
the rule rather than an argument for an exception to it.

## Light mode, and its removal

`build_options`, `make_chart`, `build_chart_html` and `build_chart_png` used to take a
`dark=` flag, threaded from `st.context.theme.type` through the cached renderers. It is
gone, along with the light values it selected.

The argument for removing it: adopting the financial-dashboard theme as a single `[theme]`
locked the app to dark, so light mode became **a mode nothing could select**. Its palette
had been tuned against the other one, and the tests asserted its hexes rather than its
legibility — so it was a claim of support the suite could not actually check. Shipping an
unreachable, unverifiable mode is worse than shipping one mode.

What that trades away is **self-correction**: the chart no longer *follows* the shell, it
assumes it. `test_app_theme_is_a_single_mode_with_no_light_dark_toggle` is what makes the
assumption safe — re-adding a `[theme.light]`/`[theme.dark]` subtable is a change nothing
else in the project would object to, and it would silently un-true the assumption every
`_themed` call now makes.

The removal also renamed the constants that had carried a mode in their names
(`_HEATMAP_GRADIENT_DARK` became `_HEATMAP_GRADIENT`), which is worth knowing when reading
older commits or docs.

## The bullet goal that must be `None`

Missing data points in dict configs fed to highcharts-core use `EnforcedNull`. There is
exactly one exception, and it is exactly one slot wide: a bullet point's **goal** — the
second element of its `[measure, goal]` array — must be Python `None`.

The mechanism is why it must not be "fixed" back.
`options/series/data/bullet.py`'s `target` setter runs
`validators.numeric(value, allow_empty=True)`, which admits `None` and rejects
`EnforcedNullType` with `CannotCoerceError`. That is raised at `Chart.from_options` —
**one layer below `build_options`**. So the whole options-dict suite stays **green** while
the chart cannot be built at all, and the app's interactive path (which does not catch
builder errors) shows a bare traceback naming neither `target` nor `bullet`.

It is pinned by a test that drives `make_chart` rather than `build_options`, because that
is the only layer at which the failure is observable — a general lesson for any rule whose
violation surfaces below the function under test.

## Row-less frames: three ways a non-boolean mask breaks

A row-less frame (columns, no rows — a CSV with a header and no data) must draw an empty
chart, not raise. Every `Series.map(...)` used as a mask must therefore be
`.astype(bool)`-cast: `.map()` infers its result dtype from the values it produced, and
with no rows there are none, so it returns an empty **non-boolean** Series.

That breaks three ways, and only the first is obvious:

1. A DataFrame indexed by a non-boolean Series is read as a list of **column names**. This
   is one shared line, so it killed *every* type at once — and a new type inherits the bug
   the day it is added unless the cast is there.
2. `.sum()` of an empty string mask is `''`, so `int()` raises.
3. `&` between two of them raises out of the Arrow kernel, while `bool & str` merely
   *warns* today — deprecated, and it will raise in pandas 4.

The third is why `test_count_marks_casts_every_mask_not_just_the_label_one` promotes
warnings to errors: it is the only way the non-label casts are observable at all today.

## `color-scheme`: why the pin sits on the SVG

`build_chart_html` pins the chart's `color-scheme` to `only light` via
`_LIGHT_COLOR_SCHEME_CSS`, on the `.highcharts-root` `<svg>` — **not** on `html`.

Highcharts declares `color-scheme: light dark` on the `.highcharts-container` div between
them. Since the property inherits, that declaration shadows an `html` rule for the whole
SVG subtree, so a pin on `html` loses. The pin must sit **at or below the container** to
win.

It is needed because Highcharts ≥ 13 expresses its own defaults as `light-dark()` CSS
variables: any color the project does *not* set explicitly would follow the **viewer's
browser** rather than the project's theme. The export server rasterized with the light
resolution, so pinning it made the two render modes agree; since the Static PNG mode's
retirement (0.21.0) the reason that remains is the other half — it leaves `_themed` the single
source of truth for dark mode, and the browser's own export, which re-renders the chart in the
page, inherits it.

The general rule that falls out: anything a new chart type wants themed must go through
`build_options`, never through a Highcharts default.

## Palette: the scale that was a palette by accident

`DEFAULT_COLORS` **is** `.streamlit/config.toml`'s `chartCategoricalColors`, copied by
hand because no theme CSS reaches an iframe or a server-side PNG.

**The first incident, and the guard it left.** The bundled financial-dashboard template
set `grayColor` and `chartCategoricalColors[6]` to the same `#94a3b8`, and
`_DARK_CHROME["muted"]` copies `grayColor` — so a seven-series chart drew its seventh
series in exactly the axis-label colour, at **1.00:1**. The fix was one entry (pink at
index 6, the template's one deviation), but the durable part was
`test_no_series_colour_collides_with_the_chart_chrome`, which asserts *identity* rather
than a contrast floor: a series and a gridline may legitimately sit close, but being the
same string is never a design call.

**The second incident, which that guard could not see.** The rest of the template's scale
stayed. It was the Tailwind **-400 step of eight hues** — harmonious, and a chart palette
only by accident. Every entry sat at L\* 64-81, a 17-point band, so **hue was the only
channel carrying series identity**; when hue collapses, nothing is left. Measured in
CIEDE2000 with dichromacy simulated (Machado-Oliveira-Fernandes 2009, severity 1.0), four
of its 28 pairs fell below ΔE 20 in normal vision — blue/sky **11.7**, red/pink 18.6,
yellow/orange 18.9, blue/violet 19.3 — and six below ΔE 12 under deuteranopia, where
`#60a5fa` and `#a78bfa` came out **0.31 apart**: one colour, for roughly 6% of men, at
slots 0 and 2, which is where a three-series chart puts them.

Every assertion in the suite passed. The hexes differed, none was a chrome value, all
cleared contrast against the background. The identity guard asks whether two roles are
the same *string*; this asks whether two series are the same *colour to a viewer*, and
that question had no second home at all. It does now:
`test_no_palette_pair_collapses_under_colour_vision_deficiency`, over **all** pairs rather
than adjacent ones — of 29 types, treemap, sunburst, networkgraph, scatter and bubble
place marks by data, so no ordering can keep a given pair apart on screen. (Heatmap is
*not* one of them, though an earlier draft of this sentence said so: it colours by
`colorAxis` and never renders a categorical hue at all.)

**What replaced it.** A scale searched under this codebase's own constraints rather than
chosen by eye — because eye is exactly what fails here: every hand-assembled candidate
tried, including one built entirely from recognisable Tailwind steps, scored **worse than
3.0** on the same measure. Trichromatic intuition cannot see the failure mode.

Three findings are worth keeping whichever palette ships next:

- **Slot 0 stays.** It is the most-loaded value in the module — the single-series default,
  `_WATERFALL_SUM_COLOR`, bullet's bar, dumbbell's after-state — and Streamlit's accent
  besides. Freeing it was measured at ~1.1 ΔE of extra separation for a dimmer primary,
  and declined. A palette optimiser told to maximise the worst *pair* will happily pay for
  it by dimming the one value that appears in more charts than the other seven combined.
- **The rise/fall split has only one direction.** Under deuteranopia a green and a red both
  simulate to yellows, so hue cannot separate them and lightness must. The obvious
  aesthetic objection — that on a finance-adjacent tool a loss should not whisper while a
  gain shouts — is *unbuildable*: in sRGB a saturated red that still clears 4.5:1 exists
  only between L\* 57 and 68, while a saturated green reaches 84. A fall cannot be made the
  lighter mark without ceasing to read as red. It buys prominence with **chroma** instead.
- **Sky was doing two jobs.** `#38bdf8` was simultaneously `chartCategoricalColors[5]` and
  `chartSequentialColors[5]` — a categorical *identity* and a heatmap *value* painted the
  same hex. Cyan took the slot; the ramp got its hue back.

**A rationale that was not true of its code.** `_HEATMAP_NULL`'s comment argues an empty
cell takes the gridline slate "so a missing reading reads as 'no cell here' … instead of
as a low value on the ramp". That is a claim about a colour *difference*, and it was never
measured: the ramp's cold end and the null fill were ΔE **8.7** apart, inside the
confusable band. Moving the cold end one stop up the sequential scale
(`#0c4a6e` → `#075985`) puts them at 12.5, and
`test_heatmap_low_end_is_distinguishable_from_an_empty_cell` now asserts it. The general
lesson is the useful one: **a comment that argues from a colour difference should be
pinned by that difference**, or it decays into an intention.

**Verified by rendering, twice, on questions arithmetic could not settle.** Highcharts'
`contrast` keyword picks the ink for in-mark labels on pie, treemap, heatmap and waterfall
by a YIQ threshold — and two careful analyses of the same rule reached *opposite*
conclusions about which ink the palette gets. Drawing eight tiles and asking the DOM what
colour it painted the text settled it in one call: black, on all eight, on both the old
palette and the new. Within the 4.5-12:1 contrast band this is not cosmetic — the dimmest
permitted fill takes black ink at 4.5:1 but **white** ink at only 3.96:1, so a slot that
slips under the threshold loses AA silently.

**The second-mode smell.** A constant that is written at build time and then overwritten
by `_themed` is evidence that a second mode is still hiding in the code.
`_HEATMAP_GRADIENT`, `_HEATMAP_NULL` and `_BULLET_TARGET_COLOR` were each exactly that;
each now holds its final value at its single write. Finding another is a signal to delete
a mode, not to add a branch.

**The crossbar that needs a pair.** `bullet`'s goal crossbar necessarily crosses both the
bar and the background, so a single fixed colour cannot work *in principle* — provably:
the two 3:1 luminance ranges do not overlap. It therefore carries a **fill plus a border**,
one value per surface. The testing lesson is the durable part: a mark whose legibility is
a property of a **pair** needs its test written over the pair. A per-path hex assertion
cannot see the defect, and did not.

## The strings highcharts-core emits unquoted

`to_js_literal` writes some Python strings into the emitted JavaScript **without quotes**.
When it does, the chart call is not valid JavaScript at all: the browser throws a
`SyntaxError` and the iframe renders blank. While the Static PNG mode existed (until 0.21.0)
its PNG came back **perfect**, because that export path never touched this code at all:
`headless_export` built its payload from `options.to_json()`, where a string is a JSON
string and the question of quoting does not arise. So the two render modes disagreed and
only the interactive one was wrong. Today there is one render, and the browser's export
re-renders it, so the bug blanks the chart and its download alike.
No assertion over an options dict can see either of the two cases below; both are only
visible in `Chart.to_js_literal()` output.

**Case one: a format string that looks like an object.** A string that opens with `{` and
closes with `}` is handed to `js_literal_functions.is_js_object`, which calls it a JavaScript
object literal — and writes it through bare — when it carries **at least as many colons as
brace-pairs**. That is the real predicate, read off the source and confirmed by round-trip, and
it is not "a `:` between the braces": a string that has a colon but too few of them falls
through to the library's `esprima` path, which parses `const testName = <the string>` and
returns `False` on anything that is not an `ObjectExpression`. One pair and one colon is the
common case, and the trap. (With **no** colon at all there are three further bare paths, all
verified by round-trip: braces enclosing nothing but whitespace, the substring `new ` anywhere in
the string, and the substring `Object.create(`. So `{point.name} new value {point.y}` is emitted
bare — worth knowing before anyone concludes that a colon is the thing to avoid. None is reachable
today, and for a reason worth keeping true: every format this module builds that both opens `{` and
closes `}` is a fixed token string with no column name interpolated into it, and every format that
does interpolate one ends in markup or a bare word instead — checked across all 30 types.)

```text
xAxis.labels.format = "{value:%b %Y}"                    ->  format: {value:%b %Y}
xAxis.labels.format = "{value}"                          ->  format: '{value}'
dataLabels.format   = "{point.y:.1f}"                    ->  format: {point.y:.1f}
dataLabels.format   = "{point.name}"                     ->  format: '{point.name}'
tooltip.pointFormat = "{point.x:%Y-%m-%d}"               ->  pointFormat: {point.x:%Y-%m-%d}
tooltip.pointFormat = "<b>{point.name}</b><br/>{point.x:%Y-%m-%d}"  ->  quoted
dataLabels.format   = "{point.name}: {point.y}"          ->  quoted   (2 pairs, 1 colon)
dataLabels.format   = "{point.name}: {point.y:.1f}"      ->  format: {point.name}: {point.y:.1f}
```

The rule is a property of the **value**, on **any key and any axis**. This is worth
stating loudly because the project got it wrong in the other direction first: the trap was
found on `xAxis.labels.format` and written up as a fact about that key, with `dataLabels`'
and the series tooltip's `format`/`pointFormat` explicitly *cleared* as "quoted
correctly" — a clearance the table above shows is false for exactly the values that break.
`timeline`'s tooltip is safe only because it opens with `<b>`; an edit that "simplified" it
by dropping the markup would have blanked the chart, and the prose would have said the edit
was fine. The `{point.name}: {point.y}` that pie, funnel and pyramid all share is the
ILLUSTRATION of the counting rule rather than an
exception to it: it opens and closes with braces and carries a colon, and survives on the
arithmetic alone — two brace-pairs against one colon, so `is_js_object` falls through to its
`esprima` path, which refuses to parse it. It escapes by **one colon**, and that is a live margin
rather than a comfortable one: `{point.name}: {point.y:.1f}`, the same format with a precision
added and the most ordinary edit anyone would make to it, is two colons against two pairs and goes
straight through bare (round-tripped, last row of the table above).
`test_no_supported_type_emits_an_unquoted_format_object` was written value-shaped from the
start: it greps every supported type's emitted JS with `[A-Za-z]*[Ff]ormat:\s*\{`, and the
optional prefix and the capital `F` are the point of the pattern rather than tidiness — the key
this module emits on nearly every tooltip is `pointFormat`, which the literal `format: {` does
not match at all. So only the prose
needed correcting — which is the argument for testing the **serializer's output** rather
than the module's intentions, and a standing warning against "simplifying" that regex to match a
prose paraphrase of it, which would reopen exactly the tooltip case this paragraph is about.

**Case two: any string beginning `Date`.** This one is a library bug, not a rule this
module can follow its way around. `highcharts_core/js_literal_functions.py:374` (the pinned
1.11.0) serializes a bare string with the following — quoted verbatim, which is why the
fence below says `text` rather than `python`: the format gate reaches ```python fences in
Markdown, and it must not restyle someone else's source out from under a line number:

```text
if (item.startswith('[') or item.startswith('Date')) and item != 'Date':
    as_str += f"""{item}"""      # emitted UNQUOTED
```

The intent is plainly to pass `Date.UTC(...)` and `[...]` expressions through as code. The
effect is that **any** string beginning `Date`, except exactly `"Date"`, reaches the page
as raw JavaScript. It is reachable from three ordinary channels, each verified against the
pinned `highcharts-core` (1.11.0):

```text
chart title   "Dates that mattered"  ->  text: Dates that mattered
column name   "Date added"           ->  name: Date added,   (and an axis title)
event name    "Dates finalised"      ->  name: Dates finalised
```

It is **case-sensitive**, so `date added` is safe and `Date added` is not, and the exact
string `"Date"` is spared by the `item != 'Date'` clause — so a column named `Date` draws
fine while `Dates` does not, which is not a distinction anyone will guess. It is
pre-existing and affects **all 30 chart types** — the title is a free-text box and a column
name comes from the user's CSV — but `timeline` raises the exposure sharply, because its
required column is semantically a date and `Dates`, `Date added` and `DateTime` are all
natural headers. (`sample_data`'s milestone dataset spells its column lowercase, which is
what keeps the shipped sample out of it.)

**Why it is documented rather than worked around.** Every available fix mutates text the
**user typed**. Quoting it ourselves is not available — the module hands `Chart.from_options`
a dict and the library owns the serialization — so the workaround would have to change the
string: prefix it, rename the column, or slip in a zero-width space to defeat the
`startswith` test. That last one is the tempting one and it is the worst: the space is
invisible in the emitted JS, so it would silently reach the DOM, the axis title, the
tooltip, the PNG and anything a user copies out of them, to defeat a prefix check. A chart
that quietly retitles itself is a worse failure than a chart that does not draw, and it
would also be *permanent*, outliving the upstream fix by however long nobody noticed.
Renaming a user's column is the same offence with a plainer face. So the trade taken is:
**live with the bug, and pin it.**

`test_a_string_beginning_with_date_is_emitted_unquoted_by_the_library` therefore asserts
the bug is **still there**, not that it is fixed. That is the only mechanism by which a
repo that chose to live with something learns that the thing changed: fixed upstream, the
test fails and this section comes out; widened upstream, it fails too. It is the same
"pin the library's behaviour, not our hope for it" move as the silent-drop tests
(sankey's `nodeFormat`, boxplot's `fillColor`, the gauge pane's `size`), pointed at a
serializer instead of a validator.

The general rule that falls out, and the reason this sits in a decisions file rather than
in a comment: **a trap in the serializer belongs to every type, including the ones not yet
written.** Sweep it over `SUPPORTED_TYPES` and assert on the emitted JS, never on the
options dict, and never on the key you happened to hit it through.

## Tooltip precision: when a channel is a value's only home

`timeline`'s tooltip printed a fixed `{point.x:%Y-%m-%d}`. `date_columns` accepts an ISO-8601
column with a **clock time** in it — nothing about `2026-01-12T09:30:00Z` fails the date sniff,
and nothing should — so a deploy log with a start at 09:30 and an end at 17:45 drew two marks at
two distinct coordinates, correctly placed, whose tooltips both read `2026-01-12`. The only
channel that could tell them apart said they were the same thing.

What makes that a defect rather than a rounding is **where else the value appears, which for
this type is nowhere**. A timeline's ticks are months, its marks are points with no extent, its
dataLabels carry the event's *name*, and it has no axis categories and no legend. Most types
state a value more than once — an axis tick, a dataLabel, a category — so a tooltip there is a
convenience, and the handful that do not (bubble's size, variwide's width) get off lightly for a
reason given below. Here the tooltip is the value's only home, and the general rule is the one
this entry is named for: **a channel that is the only home for a value must follow that value's
granularity, because there is no second reading to correct it.** The check is mechanical — for
each value the chart claims to state, count the channels that state it **at the granularity it
has**; at one, formatting stops being cosmetic. That last qualifier is not decoration and was not
in the first draft of this rule: it is what closing the xrange case below turned up, where a
ticked axis states the endpoints *coarser* and so does not count.

Dates are where this bites first, and the reason is worth keeping: a number reaches a tooltip as
itself, while a date reaches it as the **output of a format string** — and a format string is
exactly the place granularity gets thrown away. So the same trap does not lurk in `bubble`'s
`{point.z}` or `variwide`'s width, which are also tooltip-only and also unrepeated elsewhere: no
format string, no decision, nothing discarded.

**The mechanism.** `_timeline_events` now returns a **3-tuple** — `(points, sub_day, problem)`,
`_xrange_bars`' multi-value return the precedent — and `build_options` picks `_TOOLTIP_INSTANT`
(`%Y-%m-%d %H:%M`) or `_TOOLTIP_DAY` (`%Y-%m-%d`) from it. `sub_day` is returned rather than
derived by the caller because it is a **column**-level fact about the coerced values, and the
caller holds only the point dicts, whose `x` is typed `object`. It is computed as
`any(when % _MILLIS_PER_DAY for when, _ in events)`: a date parses to exact midnight UTC, so a
non-zero remainder *is* a time — arithmetic on values already coerced, not a second parse of the
strings. Measured on the round-trip:

```text
["2026-01-05", "2026-02-23"]                    -> {point.x:%Y-%m-%d}
["2026-01-05T00:00:00Z", ...]                   -> {point.x:%Y-%m-%d}
["2026-01-05T00:00:00+05:30", ...]              -> {point.x:%Y-%m-%d %H:%M}
["2026-01-12T09:30:00Z", "2026-01-12T17:45:00Z"] -> {point.x:%Y-%m-%d %H:%M}
["2026-01-05", "2026-02-23T17:45:00Z"]          -> {point.x:%Y-%m-%d %H:%M}
```

Two of those rows are the decision rather than a side effect. The **offset** row reads as an
instant because the question is asked in **UTC**, the frame the marks are actually placed in —
local midnight in `+05:30` is 18:30 the day before on the axis, so a tooltip saying only the
date would name a day the mark is not drawn on. And the **mixed** row widens *every* tooltip,
because `pointFormat` is one string per series: the choice is a column policy, not a per-point
one, and a column with any instant in it is a column whose readings are instants.

**Why not widen unconditionally**, which is the one-line version of this fix and the wrong trade
the other way: a milestone list is the type's commonest input and every one of its tooltips
would then trail a meaningless ` 00:00` — noise on the majority case to serve the minority, and
noise that *looks* like data, since a reader has no way to tell a real midnight from a padded
one. Both directions lose information; only one loses it on the rows that have it.

Two smaller notes. The formats are **named constants**, not literals inside an f-string, because
the pair is a choice and a choice with two spellings in two branches is how they drift apart —
and the branches are now in two *types* rather than two arms of one, which is what the closure
below turned that note from a tidiness into a mechanism.
And both are interpolated into a `pointFormat` that opens with `<b>`, which is what keeps the
widened one out of the unquoted-object trap above — a value that opened `{` and carried two
colons against two brace-pairs would serialize bare and blank the iframe, and
`%Y-%m-%d %H:%M` adds exactly one more colon to a string that is already close to the margin.

**Where the rule pointed next — and now goes.** `xrange` is the same shape one type over, and
saying so is the point of writing the rule down rather than the branch. Its span format already
switched — but on the **axis kind**, dates against numbers, never on granularity — so two same-day
tasks, `09:30 → 17:45` and `18:00 → 19:00`, both came back as `2026-01-12 → 2026-01-12`
(round-tripped through `build_options`). That is worse than coarse: two identical dates is
precisely how a **milestone** reads, the zero-length span xrange deliberately floors to a visible
sliver, so the tooltip did not merely lose the hours, it stated a different kind of event.

This entry first recorded that case as identified and deferred, on scope rather than principle:
the exposure looked lower, since an xrange's two ends land on a real ticked axis (its own entry's
argument for printing nothing in the mark) where a timeline point sits between month ticks, and
the fix would change a shipped type's tooltip. **Both halves of that are now retired, and the
first was wrong on its own terms.** The ticked axis is a second reading of the mark's
*placement*, and the defect was never a placement defect — the coordinates are distinct and the
bars are drawn exactly where they belong (the test asserts the two SPANS are distinct, which is
the half that matters: two bars a reader must tell apart). What has no second reading is
the *endpoint as a value*, which the axis states only to tick resolution — and that is the
**generalization the closure buys**, worth more than the fix: the rule is not *the only channel*
but *the only channel at this granularity*, so a value that appears elsewhere **coarser** is a
value with one home, and "there is an axis" is not a defence. "Lower exposure" was measuring the
wrong quantity. The second half is a real cost and simply not a large one: the changed tooltip
is a **strict refinement** — a whole-day Gantt, which is the shipped sample and the commoner
input, is byte-identical, and only a frame that carries hours sees anything new. A rule that
declines to apply the first time it points somewhere is not a rule; it is the branch it was
written to replace.

**The mechanism, one type over.** `_xrange_bars` returns a **5-tuple**,
`(points, lanes, is_datetime, sub_day, problem)`, and the span interpolates the same
`_TOOLTIP_INSTANT` / `_TOOLTIP_DAY` pair. Every detail above carries over — including the UTC
answer, since a column of `+05:30` midnights widens an xrange's span exactly as it widens a
timeline's tooltip (round-tripped) — and this shape adds one the other cannot have. The flag
is accumulated **in the drawn-bar loop** rather than derived from `points` afterwards, which is
timeline's reason restated — a point's `x` is typed `object`, so the modulo would need a cast the
loop already avoids — and it is accumulated *after* the `_spannable` skip, so a dropped bar's
hours cannot widen a tooltip that will never mention it. It stays a **column policy**: one timed
row among whole-day ones widens every tooltip in the chart (measured), because `pointFormat` is
one string per series. And widening unconditionally is still the wrong trade the other way, so
the day form is pinned as hard as the instant one. The addition is a **third** case the timeline
shape cannot have: on a **numeric** axis the span prints bare coordinates, so there is no
precision to pick, and `sub_day` is reported `False` there (`sub_day and is_datetime`) rather
than as the meaningless remainder of a plain number modulo a day's worth of milliseconds. All
three cases are pinned by `test_xrange_span_keeps_the_time_when_the_data_carries_one` — the
interesting part being that they stay three.

**Two things the closure forced, both worth more than the diff that caused them.** First, the
constants were `_TIMELINE_DAY` / `_TIMELINE_INSTANT` and are now `_TOOLTIP_DAY` /
`_TOOLTIP_INSTANT`: they were named for the type that introduced them, and xrange — the very next
thing the rule touched — picks from the same pair, so a **type name on a shared constant is
already a lie**. The
next type the rule reaches would either rename it or, worse, copy it. Second, `explain_xrange_error`
read `_xrange_bars(...)[3]` for its `problem`, and inserting `sub_day` at slot 3 quietly moved
`problem` to slot 4: the read stopped meaning "the reason these columns can't share an axis" and
started meaning "is this a date axis", **without changing**. Here `ty` caught it, because the
function is annotated `-> str | None` and a `bool` is not — but that defence is a coincidence of
the two types rather than a property of the read, and it disappears the moment a future slot is
also `str | None`. It is now a full named unpack, which breaks at the read whatever the types are.
The general form: **a positional index into a tuple that can grow is a silent rename**, and the
only reliable objection to it is a name.

Last, the **way it was found**, which is the transferable part. This type had been verified by
rendering repeatedly — the spine hue, the sorted order, the dataLabel stagger, the 600px
truncation were all decided by looking at pictures. None of those pictures could have shown
this, because every frame rendered had day granularity: rendering only ever checks the data you
rendered. It took a **review** asking what `date_columns` admits that the samples do not. When a
picker is deliberately widened past the shipped samples — as this one is, to `_COORD_EMPTY` and
to full ISO-8601 — the admitted-but-never-rendered cases are exactly where the next defect is.

## `</script>` in user text: an encoding, not an edit

`build_chart_html` puts the chart's JS inside a `<script>` element, and the HTML parser ends
that element at the first `</script` it sees, case-insensitively, **even inside a JS string**.
The JS carries user text in strings (labels, column names, the title), so a CSV label
`</script><b>x</b>` closed the chart's script early: checked on 2026-10-07, a page with that
label and that title had 4 closing tags for 3 script elements, and the chart did not draw.
Inside the app's sandboxed iframe that only broke the uploader's own chart. On a page someone
else embeds (plan #15's exports) it would be a script-injection hole, which is why it was fixed
before anything else.

`_escape_for_script_element` replaces every `</` with `<\/` and every `<!--` with `<\!--`. The
second is the other way in: `<!--` can switch the parser into a mode where a later `<script`
hides the real close. **Why this is not editing what the user typed:** inside a JS string `\/`
*is* `/` and `\!` *is* `!`, so the string the chart receives is byte-for-byte the original.
That holds only because every `</` and `<!--` in `to_js_literal` output sits inside a string:
the builder emits data, never a JS function. If a type ever emits a callback (a `formatter`, say)
that is no longer guaranteed, and the escape must be re-argued. Matching on `</` alone covers
`</SCRIPT` and every other spelling for free.

`test_user_text_cannot_close_the_charts_script_element` sweeps every supported type with the
payload in the title (the gauge family has no label channel) and in the label. It asserts the
document closes no more script elements than a clean build does, that no `<!--` reaches it, and
— with `esprima`, already installed with `highcharts-core` — that the escaped JS parses and its
title string decodes back to exactly what was typed. That last check is what proves the escape
touched nothing outside a string. Both halves were verified by breaking them: without the `</`
escape all 30 types fail on the tag count; without the `<!--` one, all 30 fail on the comment.

**What rendering showed, which the plan did not expect.** The chart now draws, but the label is
not shown as literal text: Highcharts treats label and title text as its own restricted HTML.
`<b>x</b>` draws a bold **x**, and `<script>` and `<!--` are stripped, so `<!--<script>` draws
as an empty label. That is Highcharts' display, not this escape (the JS string is the original,
and the test proves it), and it was true before the fix for any label with markup in it. It is
not changed here, because changing it means rewriting what the user typed; it matters again for
#15, whose embeds inherit it.

**Known limit:** a label that also *starts* with `Date` hits the library's
[unquoted-string bug](#the-strings-highcharts-core-emits-unquoted) first: it is emitted as code,
not as a string, and is broken before this escape applies.

## Large data: the turboThreshold bug that was not there

Plan item #22 started from a reading of Highcharts' `turboThreshold` (default 1,000): past that
many points a series may hold only numbers or arrays, and a series of point **objects** is
refused with error #12 and drawn blank. The builder never sets it, and built from a 1,200-row
frame **11** types emit point objects past the limit: pie, treemap, funnel, pyramid, sankey,
dependencywheel, networkgraph, organization, sunburst, xrange and timeline. So every one of them
looked like a silent blank chart waiting for the first big CSV.

**Rendering said otherwise** (2026-10-07, Highcharts 13.1.1 from the CDN). All of them drew every
point, with no console error, and so did the export server's PNG. The library's own source
explains it: past the threshold, data that is not numbers or arrays now sets `runTurbo = false`
and falls back to the ordinary per-point path, and its docs say the refuse-and-blank behaviour
ended after **11.4.3**. So the premise was true once and is not now. Two consequences:

- **No sweep pins "no series carries more than 1,000 point objects".** It was the plan's test,
  and it would have pinned a rule nothing enforces: it would have gone green after a fix to a
  problem that does not exist.
- **The version decides whether the bug exists,** which is why plan item #21 (pin the Highcharts
  JS version) must pin **11.4.4 or later**. An older pin would bring the blank charts back for
  all 11 types at once.

**What rendering found instead** was two real problems, neither of them `turboThreshold`:

- **A networkgraph freezes the tab.** At 1,240 nodes the layout hung the browser outright. The
  type now refuses past `_NETWORKGRAPH_MAX_NODES` with a message; the measurements and the limit
  are in [its entry](chart-types.md). It is a **size** limit, which makes
  `explain_networkgraph_error` the first of the `explain_*` family that explains something other
  than a contradiction.
- **A big pie draws but cannot be read.** At 1,200 slices it is a dark disc: the slices are so
  thin that their borders, painted the background colour, cover most of the fill. That is
  readability, not breakage, so it was split out as an idea (plan #24, group the tail into
  "Other") rather than fixed as a bug.

One practical note for the next person who reads Highcharts' source: `code.highcharts.com` answers
`403 Missing Referer` to a request without a `Referer` header, which is why scripted fetches of it
fail. The same files are published on npm, so
`https://cdn.jsdelivr.net/npm/highcharts@<version>/highcharts.src.js` serves the source.

## Highcharts JS: one pinned release

The Python side of the app is pinned and CI-tested; until 0.20.5 the JavaScript that draws every
chart was not. highcharts-core's `get_script_tags` emits **unversioned** CDN URLs
(`https://code.highcharts.com/highcharts.js`), and those serve whatever Highcharts released last.
So a new Highcharts major could change every chart with no change in this repo, and one already
had: Highcharts 13's `light-dark()` defaults are the reason `_LIGHT_COLOR_SCHEME_CSS` exists.

`_pin_script_tags` rewrites every script to the CDN's versioned path,
`https://code.highcharts.com/<HIGHCHARTS_JS_VERSION>/…`, after `_order_script_tags` has put the
modules in order. Three choices in it are deliberate:

- **One version for everything.** highcharts.js and every module (17 distinct URLs across the 30
  types) load the same release. A module from one release beside a core from another is a mix
  Highcharts does not promise to support, and the failure would be a blank iframe.
- **It raises on a URL it does not recognise** — one off the CDN, or already versioned — instead
  of passing it through. A URL that slipped past would load "latest" silently, and the same check
  catches the day highcharts-core changes its URL format and the rewrite would quietly no-op.
- **The pinned version was the one already in use.** 13.1.1 was what the unversioned URLs served
  on 2026-10-07, confirmed in the browser for all 30 types, so pinning changed no chart. It also
  sets a floor: **11.4.4**, below which 11 types draw blank past 1,000 points
  ([Large data](#large-data-the-turbothreshold-bug-that-was-not-there)), pinned by
  `test_pinned_highcharts_version_is_at_or_above_the_turbo_threshold_floor`.

**Upgrading** is now a deliberate change, like a Python dependency upgrade: bump
`HIGHCHARTS_JS_VERSION`, render-check (every type loads the new release and draws; the
`color-scheme` pin holds), and ship. Check the versioned URLs from a **browser**: the CDN answers
`403 Missing Referer` to a request without a `Referer` header, so a script cannot settle whether a
module exists at a version.

When this was written the export server (the Static PNG path) ran its own Highcharts, which the
pin did not reach. Plan #13 retired that path in 0.21.0, so the pin now covers every chart the
app draws, downloads included.

## Static PNG mode, and its retirement

Until 0.21.0 the app had two render modes: **Interactive** (the iframe) and **Static PNG**, which
sent the chart to `export.highcharts.com` and showed the image with a download button. It was
retired (plan #13) because everything it cost was paid by every user:

- **A remote service** on every static render, and the app's only server-side network call.
- **Three failure modes** with no fix inside the app — the request never sent (a build error),
  sent and unanswered (unreachable server), answered with an error (4xx/5xx) — and
  `explain_export_failure` to tell them apart.
- **Two renderers that disagreed.** The server built from `options.to_json()` and loaded every
  module, so a whole class of interactive-only bugs (unquoted strings, a missing or misordered
  module, a solid gauge without its pane) hid behind a perfect PNG; and it laid the chart out at
  600px unless told otherwise, which is why `CHART_PNG_WIDTH = 800` existed.
- **One more control**, the Mode selector, which changed how the chart was drawn but not what.

**What replaced it.** Every chart carries Highcharts' ☰ export menu (`_EXPORTING`, applied by
`_themed`), from `modules/exporting` + `modules/offline-exporting`, which `get_script_tags` pulls
in on its own once the options carry an `exporting` block — so `_pin_script_tags` versions them
like any other module. The settings that carry the design:

- `fallbackToExportServer: false`. Left on, an export the browser cannot do is quietly sent to
  the server this removed. Off, a failure reports instead.
- **Three menu items**, PNG/JPEG/SVG. The default menu also offers PDF, which needs
  `exporting.libURL` to load jsPDF, and that option has had no default since Highcharts 13; with
  the fallback off it could only fail.
- `sourceWidth: 800`. The browser's export falls back to 600px exactly as the server did (the
  embed's container is `width:100%`, so there is no pixel width to read): the first render came
  out 1200x960. 800 is the retired `CHART_PNG_WIDTH`, for the same truncation reason.
- `scale: 2`, so a PNG/JPEG is 1600x960 at the default height.

**Verified by rendering, 2026-10-07** (Chrome, Highcharts 13.1.1): all 30 types exported PNG and
SVG through `exporting.exportChart()` — the menu's own entry point, which merges the chart's
`exporting` options (a direct `localExport` call skips that merge and exports at scale 1) — each
PNG 1600x960 with the dark background in its corner pixel, no export error, and **zero** requests
to `export.highcharts.com`. The menu and the ☰ button render dark, and the boxplot, heatmap and
xrange exports were compared by eye with the on-screen charts. The downloads were intercepted in
the page rather than saved.

**A serializer finding.** The menu and button default to `var(--highcharts-background-color)`,
which the `color-scheme` pin resolves to white, so they are themed in `navigation` like the rest
of the chrome. The button's **hover** fill cannot be: highcharts-core types
`navigation.buttonOptions.theme.states` with the *series* state model, which has no `fill`, and
emits the hover dict as a JS string Highcharts ignores. So that one value is CSS,
`_EXPORT_BUTTON_CSS` in `build_chart_html` — the only chart chrome themed outside the options,
and safe because the button never appears in an exported image.

**What it traded away.** A PNG that needed no client-side JavaScript, and the export server's
independent rendering as an accidental parity check — though that check mostly *hid* bugs rather
than catching them, since it was the half that worked.

**The cache layer.** `_CACHE_LAYER` is down to two renderer wrappers. The dynamic forwarding test
moved from `cached_chart_png` to `cached_chart_html`
([the cache layer](#the-cache-layer-that-nothing-executed)), and `_forwarded_arguments` now
excludes `container_id` by name: it used to fall out of the builders' intersection only because
`build_chart_png` had no container.

**Checked across browsers (2026-10-07):** Chrome's code path was exercised by script, with each
download intercepted rather than saved. Real downloads were then tested by hand in **Firefox and
Safari**: PNG and SVG both save from inside Streamlit's sandboxed iframe, and the PNG is dark.
That was the condition that could have made the change unshippable, since the ☰ menu is now the
only way to download a chart.

## Hosting: a public demo on Community Cloud

The app is deployed at <https://highcharts-studio.streamlit.app> (2026-10-07), a **public,
non-commercial** demo on Streamlit Community Cloud. Running it locally stays the documented way to
use it, and the only way for anyone who forks it. A lightweight editor nobody can reach is half
done, which is why hosting joined the 1.0 set at all.

**Why Community Cloud.** It needed almost nothing from the app: no secrets, no environment
variables, a three-package runtime set, and since 0.21.0 no server-side network call (the export
server is gone; the Highcharts CDN is fetched by the viewer's browser). It installs from
**`uv.lock`**, the first file in its search order, so there is no `requirements.txt` to keep in step
with `pyproject.toml`, and its default Python is 3.12, the interpreter the tests use. Not
documented: which uv command it runs, so the `dev` group (pytest, Ruff, ty) may be installed too,
which costs only build time.

**The two options rejected**, so they are not re-proposed without new information:

- **Local only:** safe, but it left the editor finished with nowhere to use it.
- **Static hosting via stlite** (plan #14): every visitor would download tens of MB before the first
  chart, and it waits on an unrun spike. If that spike shows a fast enough first load, it can replace
  this deployment; it does not block it.

**The licence condition.** Highcharts JS and `highcharts-core` are free for personal and
non-commercial use, and a public deployment is still a use of them. The demo qualifies only while it
stays non-commercial (no ads, no paid tier, not a company product). If that changes, the deployment
comes down until a commercial licence is in place.

**Checked on the live app:** a chart draws and a ☰ download works, and the app loads in a signed-out
private window. That last check matters because the owner is always signed in to their own apps: an
anonymous request from a script is redirected to Community Cloud's login, which looks the same for
a private app as for a public one, so only a signed-out browser can tell them apart.

**Known limit:** free apps sleep after a period without visitors, so the first visit after a quiet
spell waits for a cold start. The README says so rather than working around it.

## Style: one object, not one kwarg per control

Written before the code (plan #5), because every style control after the first inherits it.

**The decision.** The style controls (axis titles, legend, data labels, stacking, log Y, a
reference line) reach the builder as **one** frozen, hashable `ChartStyle` dataclass under a
single `style=` kwarg, not as one kwarg each. A kwarg is the expensive unit in this codebase: each
new one is a parameter on every renderer, a forward in each `@st.cache_data` wrapper, a keyword at
each call site, and a place for a transposition (`goal_col=high_col`) that type-checks, caches and
renders the wrong thing. As one object, the wrappers change **once**, `_FORWARDED` derives the new
name on its own, and every later control is one field plus one widget. Frozen and hashable because
it is part of the cache key.

**`style` is a setting, not a column.** Like the gauge family's `agg` and `dial`, it names no
column, so it has no row in `CLAUDE.md`'s kwarg table and is excluded from the column-kwarg count
by name.

**Defaults reproduce today's chart.** `ChartStyle()` and `style=None` both build the exact options
the app built before the controls existed, so no existing chart, test or sample changed when they
arrived.

**The builder owns the rules, the sidebar reads them.** `style_controls_for(chart_type)` answers
which controls a type takes, and the sidebar draws exactly those, so the two cannot disagree. The
builder **ignores** a field the type does not take rather than raising: a hidden control keeps its
value (below), and a kept value must never reach a chart it does not belong to. The first pass
covers the Tier 1 types and no others; pie, which has no axes and always labels its slices, gets
none. Other types gain controls one at a time, where a control means something for that type.

**A hidden control keeps its value.** Streamlit discards the stored value of a keyed widget a run
does not draw, so a Y-axis title set on a line chart would be gone after a visit to pie. That breaks
the rule that a value may be dropped when it stops being **valid**, never when it merely stops being
**drawn**. The controls a type hides are re-assigned to themselves each run, the documented opt-out
the X and Y pickers already use.

**Log Y is disabled, with the reason, when it cannot be honest.** A log axis cannot show zero or
negative values, and a stacked chart fills down to zero (percent stacking also fixes the axis at
0–100%). So the toggle stays visible but disabled, saying why, when the selected Y data has a value
≤ 0 or stacking is on, and the builder ignores `log_y` in both cases so a stale `True` never draws.
Rejected: hiding it (the user is not told why), and allowing it with a warning (Highcharts drops the
points it cannot place, quietly misrepresenting the data).

**The reference line is a fixed value.** One number, drawn as a horizontal line on the Y axis.
Rejected: a computed mean or median, because "the mean of which series" has no single answer once
two Y columns are selected. Its colour aliases an existing chrome colour; no new colour is invented.

## Chart-type picker: families, then types

A selectbox of 30 types made the app look heavier than it is, so plan #17 split it into two steps:
a **family**, then a **type** within it. Every type stays reachable; the common ones come first.
`CHART_FAMILIES` in the builder is the single table (six families, each type in exactly one, each
family's most common type first), pinned by `test_chart_families_partition_the_supported_types`.
Settled on 2026-10-07, before the code (the `required=True` check came back yes: Streamlit 1.65's
`st.pills` takes it):

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

**Found while building.** The family control is a **pills** widget, drawn above the Y pills, so
every test that read `app.pills[0]` (33 of them) would have silently meant the family control. They
read `_y_pills(app)` now, and every type switch in the AppTests goes through
`_select_chart_type(app, chart_type)`, which sets the family first, so the family step is one
function rather than an edit per test.

## Embeddable exports: JSON first

Plan #15 lets a chart leave the app in the forms other pages take. Before it, none worked when
pasted elsewhere: `build_chart_html` returns a whole document; `to_js_literal` wraps its call in
`DOMContentLoaded`, which a page that has already loaded never fires again (so the chart silently
never draws) and uses a fixed `'hc_chart'` id; and `json.dumps(build_options(...))` raised on any
chart with a gap, because `EnforcedNull` is not JSON.

**JSON is the canonical form.** `_options_json` serializes the options dict with the standard
library: `EnforcedNull` becomes `null`, `allow_nan=False` makes a stray NaN or infinity raise
instead of shipping, and `<`, `>`, `&` become `\u003c`, `\u003e`, `\u0026`, the same values once
parsed but unable to close a `<script>` element (#20's escape, for embeds). The builder emits no
JavaScript functions, so JSON loses nothing. The JS is `Highcharts.chart(id, <json>);`, built from
it, so it is immune to both of the strings highcharts-core emits unquoted.

**The snippet's loader** adds each pinned module only if the page lacks it, in order, so several
snippets share one page: a tag another snippet is still loading is waited on, a tag the host page
wrote itself counts as loaded, and a page that already has Highcharts is not given a second copy.
It runs immediately. Its styles (the `color-scheme` pin and the ☰ button's hover) are scoped to its
own id. Rendered on 2026-10-07: two snippets (a line and a sankey) on one page; the same two
inserted by a script **after** load, which also exercised the wait (each module loaded once); a
host page that already loads Highcharts; and the full page. All drew. The first attempt at the
after-load page failed in the HARNESS, not the snippet: it embedded the snippets with `json.dumps`
inside its own `<script>`, and the snippet's `</script>` closed it — #20's bug, in the test page.

**A bug it surfaced in the app.** Comparing the options dict with what highcharts-core keeps, for
every type, found one key the core drops: `plotOptions.treemap.borderColor`, which `_themed` set so
the tile gaps would match the dark background. The app had drawn light gaps all along, while the
dict, and the test asserting on it, said otherwise. It is now set per level (`levels`), which
survives; and `test_no_option_the_builder_sets_is_silently_dropped` runs the same comparison over
every type, failing on any new dropped key until it is fixed or listed with a reason.

**Settled on 2026-10-07, before the code:**

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

## Export as Python: load, don't inline

Plan #2 gives the Export panel a fifth tab: the `make_chart(...)` call that rebuilds the chart, so
the app doubles as a way to learn the API. `python_snippet` builds it from the column NAMES alone,
so it needs no data and no cache.

**The data is loaded, not inlined** (settled 2026-10-07): `pd.read_csv("<the uploaded file's
name>")`, or, for one of the app's samples, `SAMPLES["<label>"]()`, which names the sample and runs
as is in this repo. One shape, short at any data size; the user already has their file. Rejected:
inlining the samples only (two shapes to build and test) and always inlining (a large upload makes
a long snippet, #15's size problem again). The plan said a comment would name a sample; loading it
by its label does that and also runs, so the snippet keeps one comment, pointing at `read_csv` for
the user's own data.

**The smallest call.** A keyword is written only when it differs from its default, and the style
only with the fields the type takes (`style_controls_for`) set away from their defaults, so a
hidden control's kept value never leaks into the code. Strings are written with `json.dumps`,
whose escapes are valid Python and whose double quotes match Ruff; lines stay within Ruff's 88.

**Pinned by running it.** For every type, the snippet is executed with `pd.read_csv` returning the
test frame, and must emit exactly the JS a direct `make_chart` call emits, with a title and that
type's style set. That is the only test that can tell the snippet from a plausible-looking one.

## Editing data: the app keeps the edits

Plan #8 made the Source data table editable (`st.data_editor`, cells only), so a typo can be fixed
or a value tried without re-uploading. Settled before the code: cells only, no added or deleted
rows (the lightweight answer); and edits reset when the dataset changes, since they belong to the
data they were made on.

**The edits must reach the chart before the sidebar runs.** The table is drawn in the main panel,
after the pickers and gates have read `df`. A data editor's edits are in session state before it
is drawn again, so they can be applied straight after the data loads.

**The first design kept them in the editor's widget state, and rendering showed why that fails.**
A gate that stops ABOVE the table (timeline's, on data with no date column) means the editor is
not drawn, so Streamlit discards its state. Re-assigning its key at the stop, the fix the X and Y
pickers use, did keep the edit in session state, but a data editor cannot be RESTORED from session
state: the chart still showed the edit while the redrawn table showed the original value. Every
AppTest passed, because an edit AppTest sets through session state is plain state that is never
discarded. Only a real edit in the running app showed it.

**So the app keeps its own store** (`_CELL_EDITS`: the dataset's identity and its edits). On every
run it merges the editor's latest edits into the store (`merge_cell_edits`), applies the store
before the pickers read `df` (`apply_cell_edits`), and draws the editor over the EDITED frame.
That last step is safe because edits are absolute cell values, so applying one twice changes
nothing. After any stop, the table redraws showing exactly what the chart uses. Rendered on
2026-10-07: a cleared cell drew as a gap; it survived a visit to timeline's stopping gate in both
the table and the chart; and it was gone after a round trip through another dataset.

**Columns are rebuilt, not assigned cell by cell.** Measured on pandas 3.0.6: assigning `5.5` into
an int64 column RAISES `TypeError` (while `None` there quietly upcasts to float). Rebuilding each
edited column from Python values lets its dtype follow the values instead: int edits keep it int,
a decimal makes it float, and a cleared cell is a gap, as a blank CSV cell is.

**A tooling note from the same session:** a Streamlit dev server left running while tests rewrote
the source files (the mutation checks) can half-reload its modules and fail every run with an
import error, which looks exactly like an app that ignores input. Restart the server after
mutation testing, as `CLAUDE.md`'s Run section already advises for stale state.
