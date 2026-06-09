"""Smoke tests for the Highcharts builder and the Streamlit app.

Run with: ``uv run pytest``
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from highcharts_builder import build_options  # noqa: E402


def test_build_options_cartesian():
    df = pd.DataFrame({"x": ["a", "b", "c"], "y": [1, 2, 3]})
    opts = build_options(df, "line", "x", ["y"])
    assert opts["chart"]["type"] == "line"
    assert opts["xAxis"]["categories"] == ["a", "b", "c"]
    assert opts["series"][0]["data"] == [1.0, 2.0, 3.0]


def test_build_options_rejects_unsupported_type():
    df = pd.DataFrame({"x": [1], "y": [1]})
    with pytest.raises(ValueError):
        build_options(df, "bogus", "x", ["y"])


def test_build_options_rejects_x_in_y():
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    with pytest.raises(ValueError):
        build_options(df, "line", "y", ["y"])


def test_app_runs_headless():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60)
    at.run()
    assert not at.exception
