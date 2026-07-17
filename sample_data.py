"""Built-in sample datasets so the app works with no upload.

Pure pandas — no Streamlit — so it stays independently importable and testable,
like ``highcharts_builder``. Each factory returns a fresh DataFrame.
"""

from __future__ import annotations

import pandas as pd


def _revenue_vs_cost() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "month": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "revenue": [120, 135, 128, 150, 162, 171],
            "cost": [80, 88, 90, 95, 101, 108],
        }
    )


def _fruit_sales() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fruit": ["Apples", "Bananas", "Cherries", "Grapes", "Oranges"],
            "units_sold": [620, 540, 210, 380, 470],
        }
    )


def _height_vs_weight() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "height_cm": [152, 158, 161, 165, 168, 172, 175, 180, 185, 190],
            "weight_kg": [50, 55, 58, 61, 65, 70, 74, 80, 86, 94],
        }
    )


def _daily_temperature() -> pd.DataFrame:
    """Hourly temperature across one day — a smooth rise to an afternoon peak and
    back down overnight. Tailored to areaspline: the rounded rise-then-fall puts a
    curved peak where a straight-segment ``area`` chart would show a sharp elbow,
    so the spline smoothing actually shows."""
    return pd.DataFrame(
        {
            "hour": [f"{h:02d}:00" for h in range(24)],
            "temp_c": [
                12,
                11,
                11,
                10,
                10,
                11,
                12,
                14,
                16,
                18,
                20,
                22,
                23,
                24,
                24,
                23,
                21,
                19,
                17,
                16,
                15,
                14,
                13,
                12,
            ],
        }
    )


def _country_economics() -> pd.DataFrame:
    """GDP per capita vs life expectancy, sized by population — the classic
    Gapminder-style bubble where the marker area carries a third dimension.
    Tailored to bubble: a numeric GDP (X) and life-expectancy (Y) pair plus a
    population column whose wide range (tens to ~1,400 millions) makes the size
    encoding legible."""
    return pd.DataFrame(
        {
            "country": [
                "USA",
                "China",
                "India",
                "Germany",
                "Brazil",
                "Nigeria",
                "Japan",
                "Indonesia",
            ],
            "gdp_per_capita_k": [76.0, 12.6, 2.5, 52.7, 8.9, 2.1, 33.8, 4.8],
            "life_expectancy": [77.5, 78.2, 70.1, 81.2, 73.4, 52.7, 84.0, 71.7],
            "population_m": [335, 1412, 1428, 84, 216, 224, 125, 278],
        }
    )


def _product_ratings() -> pd.DataFrame:
    """Two competing products scored 0–10 across the same attributes — the
    natural radar (spider) chart, where each product is one closed polygon over
    the shared axes and the comparison is the difference in their shapes.
    Tailored to radar: a category axis (attribute) plus two numeric series whose
    values share a common 0–10 range, so the overlaid webs are directly
    comparable (and neither dominates the auto-scaled radial axis)."""
    return pd.DataFrame(
        {
            "attribute": [
                "Design",
                "Performance",
                "Battery",
                "Camera",
                "Price",
                "Support",
            ],
            "Aurora": [9, 7, 6, 8, 5, 7],
            "Zephyr": [6, 9, 8, 5, 8, 6],
        }
    )


def _weekly_activity() -> pd.DataFrame:
    """Website visits by weekday × time-of-day block — the activity matrix a
    heatmap is built for: each (weekday, block) cell's color shows how busy that
    slot is, so the weekday midday peak and the weekend evening shift read at a
    glance. Tailored to the wide-form heatmap: a category column (weekday) plus
    four numeric columns (the time blocks) whose values share one intensity scale,
    so the color axis is directly comparable across every cell."""
    return pd.DataFrame(
        {
            "weekday": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "Night": [12, 10, 11, 13, 18, 26, 22],
            "Morning": [48, 52, 50, 55, 60, 34, 28],
            "Afternoon": [66, 70, 72, 74, 80, 46, 41],
            "Evening": [40, 42, 45, 47, 68, 78, 64],
        }
    )


def _company_market_cap() -> pd.DataFrame:
    """Market capitalization of the largest tech companies — the part-of-whole a
    treemap is built for: each tile's area shows one company's share, and the
    ~10-way split stays readable where a 10-slice pie would be a cluttered ring.
    Tailored to treemap: a single label column (company) + one numeric value
    column (market_cap_b) whose wide range makes the nested-rectangle sizing
    legible."""
    return pd.DataFrame(
        {
            "company": [
                "Apple",
                "Microsoft",
                "Nvidia",
                "Alphabet",
                "Amazon",
                "Meta",
                "TSMC",
                "Broadcom",
                "Tesla",
                "Netflix",
            ],
            "market_cap_b": [3400, 3100, 2900, 2100, 1900, 1300, 950, 780, 720, 380],
        }
    )


def _conversion_funnel() -> pd.DataFrame:
    """A marketing conversion funnel — the part-of-whole *stages* a funnel is built for: each
    band is one step of a purchase journey, sized by how many people reach it, and the strict
    top-to-bottom narrowing IS the story (where a pie would only show each step's share of the
    sum). Tailored to funnel: a single stage-label column (stage) leading the frame — so the app
    opens cleanly on ``line`` with a category X — plus one numeric value column (visitors) whose
    values *decrease* down the funnel. The clean monotone sequence is the demo's job; a missing or
    out-of-order stage is the tests'."""
    return pd.DataFrame(
        {
            "stage": [
                "Visitors",
                "Product views",
                "Added to cart",
                "Checkout started",
                "Purchased",
            ],
            "visitors": [48000, 21500, 9200, 4100, 1600],
        }
    )


def _loyalty_pyramid() -> pd.DataFrame:
    """A customer-loyalty pyramid — funnel's inverted mirror, drawn as pyramid's own series type.
    Like a funnel it leads with its LARGEST stage, but where a funnel puts that stage at the top
    and narrows downward, a Highcharts pyramid draws the first row at the BASE and narrows UPWARD
    to an apex (verified by rendering) — the classic broad-based loyalty pyramid. Tailored to
    pyramid exactly as the funnel sample is to funnel: a stage-label column (tier) first, one
    numeric value column (people) *decreasing* from the broad Audience base to the Advocates apex.
    Reading the two side by side is the fastest way to see the only difference is which way the
    shape points, not the data."""
    return pd.DataFrame(
        {
            "tier": [
                "Audience",
                "Leads",
                "Customers",
                "Repeat buyers",
                "Advocates",
            ],
            "people": [25000, 8000, 3200, 900, 250],
        }
    )


def _energy_flow() -> pd.DataFrame:
    """Primary energy sources feeding electricity generation, which then splits to
    end-use sectors — the multi-level flow a sankey is built for: each link's width
    shows how much energy moves from one stage to the next, and the two hops
    (fuel → Electricity → sector) trace the whole system in one diagram.
    Tailored to sankey: a source and a target column of node *labels* plus a numeric
    weight, balanced so the 150 units generated are the 150 consumed. Unlike every
    other sample — each of which has one row per unique x value — the source labels
    REPEAT, and ``Electricity`` is both a target and a source. That is the from/to
    link shape sankey reads, and it is what makes the second hop appear."""
    return pd.DataFrame(
        {
            "source": [
                "Coal",
                "Natural Gas",
                "Nuclear",
                "Solar",
                "Wind",
                "Hydro",
                "Electricity",
                "Electricity",
                "Electricity",
            ],
            "target": [
                "Electricity",
                "Electricity",
                "Electricity",
                "Electricity",
                "Electricity",
                "Electricity",
                "Residential",
                "Industry",
                "Commercial",
            ],
            "terawatt_hours": [42, 38, 20, 14, 26, 10, 60, 55, 35],
        }
    )


def _regional_migration() -> pd.DataFrame:
    """Population moving between regions over a year — the who-flows-to-whom a dependencywheel is
    built for: nodes sit on a ring and each curved ribbon's width shows how many people moved from
    one region to another, so the whole migration matrix reads in one circle.

    Tailored to dependencywheel, and the deliberate MIRROR of the sankey energy sample above. Both
    read the same {from, to, weight} link shape, but the SHAPE OF THE DATA is opposite, which is the
    whole point of reading them side by side: the energy sample is a layered DAG — fuel flows one
    way into ``Electricity`` and on to a sector, and the source set and the target set barely
    overlap, so it draws cleanly as a left-to-right flow. Here EVERY region is BOTH an origin and a
    destination (North sends to South and East, and receives from South, East and Central), so the
    flow is a symmetric, cyclic matrix with no layers — exactly the graph a straight sankey draws as
    a tangle of back-crossing links and a ring draws as a clean wheel. Ten links, well under the
    label gate, so each ribbon carries its own count.

    Leads with a *label* column (``origin``) — load-bearingly so, like every sample: the app opens
    on ``line`` with the first column as X, and a numeric first column would trip the x-in-y guard
    the moment the dataset is selected. ``people`` is the numeric weight the wheel sizes ribbons by,
    which also gives the app's no-numeric-columns gate something to find."""
    return pd.DataFrame(
        {
            "origin": [
                "North",
                "North",
                "South",
                "South",
                "East",
                "East",
                "West",
                "West",
                "Central",
                "Central",
            ],
            "destination": [
                "South",
                "East",
                "North",
                "Central",
                "West",
                "North",
                "Central",
                "South",
                "North",
                "East",
            ],
            "people": [1200, 800, 950, 700, 600, 450, 500, 400, 650, 550],
        }
    )


def _service_dependencies() -> pd.DataFrame:
    """A microservice call graph — the who-connects-to-whom a networkgraph is built for: each row
    is one dependency edge, and the force layout pulls tightly-coupled services together so the
    clusters (an ``Orders`` hub, an ``Auth`` shared by several callers) fall out of the physics.

    Tailored to networkgraph, and the deliberate MIRROR of the sankey sample above: two columns of
    node *labels* and NO weight, because a networkgraph edge is unweighted. Like sankey the source
    labels REPEAT and many nodes are BOTH a source and a target (``API Gateway`` calls Auth and is
    itself called by Web and Mobile; ``Orders`` sits mid-graph) — which is what makes this a
    connected network rather than a star. Unlike sankey it also contains a CYCLE (``Catalog`` ⇄
    ``Search`` call each other), which a networkgraph draws without complaint where the sunburst
    sample's *tree* could not — the one graph shape no hierarchy can hold.

    The first column is the source, a *label*, so — like every sample and load-bearingly so — the
    app can open it on ``line`` without a numeric first column tripping the x-in-y guard. The
    networkgraph itself reads only the two label columns (an edge is unweighted), but ``calls_per_min``
    is a genuine numeric column carried for the same reason ``_release_plan``'s ``headcount`` is: so
    the dataset stays usable by the value-based types and the app's no-numeric-columns gate has
    something to find. It is per-EDGE traffic, so networkgraph ignores it rather than sizing anything
    by it — the honest place for a magnitude a graph cannot draw."""
    return pd.DataFrame(
        {
            "service": [
                "Web",
                "Mobile",
                "API Gateway",
                "API Gateway",
                "API Gateway",
                "Orders",
                "Orders",
                "Orders",
                "Payments",
                "Inventory",
                "Catalog",
                "Search",
                "Auth",
            ],
            "depends_on": [
                "API Gateway",
                "API Gateway",
                "Auth",
                "Orders",
                "Catalog",
                "Payments",
                "Inventory",
                "Auth",
                "Ledger",
                "Warehouse",
                "Search",
                "Catalog",
                "Sessions",
            ],
            "calls_per_min": [
                1200,
                800,
                1500,
                600,
                900,
                300,
                450,
                600,
                300,
                200,
                700,
                650,
                2100,
            ],
        }
    )


def _response_times() -> pd.DataFrame:
    """Per-service API response times in milliseconds — the per-category *distribution*
    a boxplot is built for: each service's spread of raw observations becomes one box,
    so the reader sees center AND spread at once, and a genuine tail latency reads as an
    outlier dot instead of quietly dragging a mean upward. Tailored to the long/tidy
    boxplot shape, the only one in this file: a category column (``service``) whose
    values REPEAT — one row per observation, ~15 per service — plus one numeric column
    of raw measurements (``response_ms``). ``search`` is right-skewed around a single
    890 ms tail spike, the lone Tukey outlier across the whole frame, so the linked
    outlier series has exactly one point to draw. The boxes appear in first-appearance
    order (auth, search, checkout, profile), which is also roughly increasing latency.
    """
    services = ["auth"] * 15 + ["search"] * 15 + ["checkout"] * 15 + ["profile"] * 15
    response_ms = [
        # auth — fast and tight
        42, 45, 38, 51, 47, 55, 44, 49, 60, 41, 48, 52, 46, 58, 50,
        # search — right-skewed, with the one 890 ms spike that becomes the outlier
        88, 95, 102, 91, 110, 85, 120, 99, 105, 890, 93, 108, 97, 115, 101,
        # checkout — slower and wider, but no tail
        150, 165, 148, 172, 159, 180, 155, 168, 175, 161, 152, 170, 158, 166, 163,
        # profile — slowest, and the widest box
        210, 225, 198, 240, 215, 230, 205, 220, 235, 212, 208, 228, 218, 222, 216,
    ]  # fmt: skip
    return pd.DataFrame({"service": services, "response_ms": response_ms})


def _profit_bridge() -> pd.DataFrame:
    """A quarterly profit bridge — how gross revenue BECOMES net profit, one signed step
    at a time. Tailored to the waterfall shape, the only one in this file whose numeric
    column holds *deltas* rather than levels: every other dataset's values stand on their
    own, while these only mean anything cumulatively, each starting where the last ended.

    The steps mix signs (the point of the type — a same-signed column would just be a
    column chart drawn oddly) and are ordered as a P&L reads: an opening revenue figure,
    then the costs that eat into it, then the one mid-sequence *rise* (``Other income``)
    that proves the up/down coloring is driven by each value's sign rather than by
    position. No total row: the builder appends the closing ``Total`` bar itself, summing
    these to 79.
    """
    return pd.DataFrame(
        {
            "step": [
                "Gross revenue",
                "COGS",
                "Salaries",
                "Marketing",
                "Other income",
                "Tax",
            ],
            "delta": [420.0, -155.0, -120.0, -64.0, 38.0, -40.0],
        }
    )


def _org_headcount() -> pd.DataFrame:
    """Company headcount as an ADJACENCY LIST — one row per node, each naming its parent.

    Tailored to sunburst, and to nothing else in this file, on four counts:

    * It is the only sample whose rows are a HIERARCHY. Sankey's ``_energy_flow`` is the near
      miss worth naming: its rows are edges of a *graph*, and ``Electricity`` is both a source
      and a target — which no tree can be. Here every node has exactly one parent.
    * It is the only sample whose value column is deliberately BLANK on some rows. Everywhere
      else a blank means missing data; here it means *"ask my children"*. Engineering's 80 is
      nowhere in this frame — it is 80 *because its teams are*, and the chart is what does that
      addition. The centre reads a total the builder never computed.
    * Three levels of nesting (division → group → team) plus the synthesized root make FOUR
      rings, which is what makes the colour *inheritance* and the *alternating* sign of the
      ``colorVariation`` visible at all. A two-level tree would show neither.
    * ``Other`` appears TWICE, under two different divisions — the exact case a label-keyed
      node identity would silently MERGE into one 9-person sector under whichever parent won
      (and which Highcharts itself rejects outright, as error #31, "Non-unique point or node
      id"). Nothing *names* ``Other`` as a parent, so the ambiguity never arises and the two
      stay honest 5- and 4-person leaves. It is the sample's whole argument for synthesized
      ids.

    The blank ``reports_to`` cells are the three top-level branches. Headcount sums to 143
    (Engineering 80, Sales 39, Marketing 24).
    """
    return pd.DataFrame(
        {
            "team": [
                "Engineering",  # the three top-level branches (blank parent)
                "Sales",
                "Marketing",
                "Platform",  # under Engineering
                "Product",
                "Backend",  # under Platform
                "Infrastructure",
                "Mobile",  # under Product
                "Web",
                "Enterprise",  # under Sales
                "SMB",
                "Other",
                "Brand",  # under Marketing
                "Growth",
                "Other",  # ...the second one: a different team, the same name
            ],
            "reports_to": [
                None,
                None,
                None,
                "Engineering",
                "Engineering",
                "Platform",
                "Platform",
                "Product",
                "Product",
                "Sales",
                "Sales",
                "Sales",
                "Marketing",
                "Marketing",
                "Marketing",
            ],
            "headcount": [
                # The five internal nodes state no headcount: Highcharts sums it from the
                # leaves below them. Only the ten leaf teams carry a number.
                None,
                None,
                None,
                None,
                None,
                24.0,
                16.0,
                18.0,
                22.0,
                20.0,
                14.0,
                5.0,
                9.0,
                11.0,
                4.0,
            ],
        }
    )


def _release_plan() -> pd.DataFrame:
    """A product release plan as INTERVALS — one row per scheduled bar, each on a workstream
    lane, spanning a start date and an end date.

    Tailored to xrange, and to nothing else in this file, on four counts:

    * It is the only sample whose value columns are COORDINATES rather than magnitudes. Every
      other dataset answers "how much"; these two answer "when". So it is also the only one
      carrying DATES, and they are written as ISO-8601 *strings* on purpose: that is what
      ``pd.read_csv`` hands back for a date column, so the sample exercises the real
      ``_coordinates`` sniff (an object column parsed to a datetime axis) rather than a
      pre-parsed ``datetime64`` a CSV upload would never produce.
    * Its label column REPEATS, like ``_response_times``' does — but for a different reason.
      A boxplot's repeats are observations to be aggregated into one box; here each repeat is
      its own bar, so ``Backend`` and ``Frontend`` each run twice with a GAP between them
      (build, then a later hardening pass). That is what proves the per-lane hue: a lane's two
      bars must come back the same color, or a workstream stops reading as one thing.
    * ``Launch`` is a zero-length row — a MILESTONE, the commonest Gantt row after a task, and
      the one Highcharts draws nothing for unaided. It is here so the sample renders the
      ``minPointLength`` floor rather than leaving it to a test.
    * ``headcount`` is a genuine numeric column, so the dataset is still usable by the other
      chart types (and so the app's no-numeric-columns gate has something to find).
    """
    return pd.DataFrame(
        {
            "workstream": [
                "Discovery",
                "Design",
                "Backend",
                "Frontend",
                "Backend",
                "Frontend",
                "QA",
                "Launch",
            ],
            "start": [
                "2026-01-05",
                "2026-01-26",
                "2026-02-16",
                "2026-03-02",
                "2026-04-27",  # the second Backend bar, after a gap
                "2026-05-04",  # the second Frontend bar, after a gap
                "2026-05-11",
                "2026-06-01",  # the milestone: start == end
            ],
            "end": [
                "2026-01-23",
                "2026-02-20",
                "2026-04-17",
                "2026-04-24",
                "2026-05-08",
                "2026-05-15",
                "2026-05-29",
                "2026-06-01",
            ],
            "headcount": [2, 3, 5, 4, 2, 2, 3, 1],
        }
    )


def _temperature_range() -> pd.DataFrame:
    """A city's monthly record temperatures as RANGES — one row per month, each a record low
    and a record high in °C.

    Tailored to columnrange, and it is the mirror of ``_release_plan`` on the one axis that
    matters: its two value columns are a LOW and a HIGH of the SAME quantity (°C), so they are
    MAGNITUDES, not xrange's coordinates — they answer "how much", never "when", and can never be
    dates. That is the whole difference the type turns on, and reading this sample beside the
    release plan is the fastest way to see it: both draw a bar from a low to a high, but one bar
    spans a temperature and the other a calendar.

    ``record_low`` leads with the category column (``month``) rather than a value, like every
    sample here and for the same load-bearing reason: the app opens on ``line`` with the first
    column as X, so a numeric first column would trip the x-in-y guard the instant the dataset is
    selected. Both value columns are genuine numbers, so the dataset stays usable by the other
    chart types (and the no-numeric-columns gate has something to find). Every ``low`` sits below
    its ``high`` — a clean, honest range — because the type's headline is "a min–max per category"
    and this sample is meant to SHOW that; the missing-slot and inverted-range edge cases are the
    tests' job, not a demo dataset's. One measurement drawn in one hue: a columnrange does not
    colour its bars by category, since the months are positions on an axis, not separate kinds.
    """
    return pd.DataFrame(
        {
            "month": [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ],
            "record_low": [-8, -6, -2, 2, 7, 11, 14, 13, 9, 3, -3, -7],
            "record_high": [14, 16, 22, 27, 31, 34, 37, 36, 32, 26, 19, 15],
        }
    )


def _weekly_bookings() -> pd.DataFrame:
    """Weekly bookings by sales region — four teams, eight weeks of observations.

    Tailored to solidgauge, and to nothing else in this file, on four counts:

    * It is the only sample whose numeric columns are COMPARABLE MEASURES OF ONE THING. Every
      other multi-column dataset mixes units (revenue against cost, GDP against life
      expectancy), and concentric rings sharing ONE dial only mean something when the columns
      share a scale.
    * It is the only sample meant to be read through an AGGREGATION rather than plotted
      directly. Every other dataset's numbers are marks; these are observations that mean
      nothing until they are collapsed — and they collapse six sensible ways: the quarter's
      total (``sum``: north 436, which the dial rounds out to 500, so the headline ring reads
      436 OF 500 rather than being 100% full of itself), a typical week (``mean``), the best
      week (``max``), this week (``last``).
    * ``emea`` goes unreported in two weeks — an ordinary reporting gap. It puts the drop
      INSIDE the aggregate: emea's mean is over six weeks, not eight.
    * ``partner_deals`` is unreported ENTIRELY, and it is the type's headline trap made
      reachable from the app rather than left to a test. ``pd.Series([nan, ...]).sum()`` is
      ``0.0``, so a naive reduction would draw that ring an emphatic, entirely fictional ZERO.
      The builder tests for empty ABOVE the reducer, reads it as no data, and keeps the ring as
      a null — an empty track, named only in the legend. (``float("nan")``, not ``None``: an
      all-``None`` column is OBJECT dtype, so the app's numeric picker could never offer it and
      the trap would be out of reach from the UI.)

    ``week`` is an ordinary category column and the regions ordinary numerics, so the frame is
    still a good citizen for line/column/heatmap/radar — and ``week`` is the one column a gauge
    ignores completely, having no label channel to put it in.
    """
    blank = float("nan")
    return pd.DataFrame(
        {
            "week": ["W01", "W02", "W03", "W04", "W05", "W06", "W07", "W08"],
            "north": [42, 51, 47, 58, 61, 55, 63, 59],  # sum 436 -> a 0..500 dial
            "south": [38, 35, 44, 41, 39, 46, 43, 48],  # sum 334
            "emea": [22, 27, 25, blank, blank, 31, 34, 36],  # sum 175, over SIX weeks
            "partner_deals": [blank] * 8,  # nothing reported: a null ring, not a zero
        }
    )


def _server_utilization() -> pd.DataFrame:
    """Resource utilization across nine hosts, as percentages — the needle gauge's dataset.

    It is `_weekly_bookings`' sibling and deliberately not its clone: both feed the gauge family,
    but they exercise the dial from OPPOSITE ends, and between them they cover the two ways a
    reader can misread one.

    * These columns are PERCENTAGES, so the reduction that means anything is ``mean``, not
      ``sum`` — and a mean of percentages lands the derived dial almost exactly on 0..100, the
      scale a reader already has in their head. (``sum`` on this frame is nonsense on purpose:
      it reads past 600% and the dial dutifully rounds out to 1000, which is the fastest way to
      SEE what the aggregation picker is actually doing to your numbers. The bookings sample
      makes the same point with the opposite default.)
    * The columns are comparable measures of one thing, which is the family's whole
      precondition: needles sharing ONE dial mean nothing when the columns have different units.
    * ``disk_pct`` is the point of the type. It sits far from the other two, so the three needles
      SPREAD across the face instead of bunching — which is what a gauge is for, and what a
      reader cannot get from three near-identical arcs.
    * ``swap_pct`` is unreported entirely — the family's headline trap, kept reachable from the
      app rather than left to a test, exactly as ``partner_deals`` is. ``pd.Series([nan, ...])``
      sums to ``0.0``, the additive identity, so a naive reduction would swing a needle
      confidently to the floor of the dial and CLAIM zero swap where the truth is "nobody said".
      The builder tests for empty above the reducer and keeps the mark as a null: no needle at
      all, named only in the legend. On a needle this matters MORE than on a ring, because a
      needle at zero is indistinguishable from a real reading of zero. (``float("nan")``, not
      ``None``: an all-``None`` column is object dtype, so the app's numeric picker could never
      offer it and the trap would be out of reach from the UI.)

    ``host`` is an ordinary category column, so the frame stays a good citizen for
    line/column/bar/heatmap — and it is the column a gauge ignores completely, having no label
    channel to put it in. It leads the frame deliberately: the app opens on ``line`` with the
    FIRST column as X, and a numeric first column would trip the x-in-y guard the moment this
    dataset was selected.
    """
    blank = float("nan")
    return pd.DataFrame(
        {
            "host": [
                "web-01",
                "web-02",
                "web-03",
                "api-01",
                "api-02",
                "db-01",
                "db-02",
                "cache-01",
                "batch-01",
            ],
            "cpu_pct": [62, 58, 55, 71, 68, 81, 77, 34, 92],  # mean ~66
            "memory_pct": [71, 68, 74, 66, 70, 88, 85, 41, 79],  # mean ~71
            "disk_pct": [45, 47, 44, 38, 40, 73, 76, 22, 51],  # mean ~48 — the spread
            "swap_pct": [blank]
            * 9,  # nothing reported: a null needle, not a confident zero
        }
    )


# Label -> factory. Each label hints at the chart types the dataset suits.
SAMPLES = {
    "Monthly revenue vs cost (line/area/column)": _revenue_vs_cost,
    "Fruit sales (pie/bar/column)": _fruit_sales,
    "Height vs weight (scatter)": _height_vs_weight,
    "Daily temperature (areaspline)": _daily_temperature,
    "Country economics (bubble)": _country_economics,
    "Product ratings (radar)": _product_ratings,
    "Website activity by weekday (heatmap)": _weekly_activity,
    "Company market cap (treemap)": _company_market_cap,
    "Marketing conversion funnel (funnel)": _conversion_funnel,
    "Customer loyalty pyramid (pyramid)": _loyalty_pyramid,
    "Energy flow (sankey)": _energy_flow,
    "Regional migration flows (dependencywheel)": _regional_migration,
    "Service dependencies (networkgraph)": _service_dependencies,
    "Service response times (boxplot)": _response_times,
    "Quarterly profit bridge (waterfall)": _profit_bridge,
    "Company headcount (sunburst)": _org_headcount,
    "Product release plan (xrange)": _release_plan,
    "Monthly temperature range (columnrange)": _temperature_range,
    "Weekly bookings by region (solidgauge)": _weekly_bookings,
    "Server utilization (gauge)": _server_utilization,
}
