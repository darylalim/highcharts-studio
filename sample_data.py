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


# Label -> factory. Each label hints at the chart types the dataset suits.
SAMPLES = {
    "Monthly revenue vs cost (line/area/column)": _revenue_vs_cost,
    "Fruit sales (pie/bar/column)": _fruit_sales,
    "Height vs weight (scatter)": _height_vs_weight,
    "Daily temperature (areaspline)": _daily_temperature,
    "Country economics (bubble)": _country_economics,
}
