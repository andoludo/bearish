import tempfile
from pathlib import Path

import pytest

from bearish.analysis.view import BaseViews, TestView, View
from bearish.database.crud import BearishDb


def test_base_views(bearish_db_with_analysis: BearishDb) -> None:
    """Test the BaseViews class with a simple query."""
    views = BaseViews(
        view_name="test", query="SELECT symbol, name, source FROM analysis"
    )
    with tempfile.TemporaryDirectory() as d:
        views.compute(bearish_db_with_analysis, Path(d))
        views = bearish_db_with_analysis.read_query("SELECT * FROM view")
        assert not views.empty


def test_views(bear_db: BearishDb):
    with tempfile.TemporaryDirectory() as d:
        TestView().compute(bear_db, Path(d))
        query = """
        SELECT * FROM view;
        """
        data = bear_db.read_query(query)
        assert not data.empty


def test_views_plot(bear_db: BearishDb):
    view = View(symbol="NVDA", source="Yfinance", exchange="NMS")
    with tempfile.TemporaryDirectory() as d:
        view.plot(bear_db, Path(d), show=True)
    assert True
