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
    "Energy flow (sankey)": _energy_flow,
    "Service response times (boxplot)": _response_times,
}
