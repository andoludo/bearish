import tempfile
from pathlib import Path

import pytest
import requests_mock

from bearish.database.crud import BearishDb
from bearish.equities import EquityQuery, DailyOhlcv
from bearish.models.base import Equity
from bearish.financials import Financials
from bearish.main import Bearish


@pytest.fixture(scope="session")
def bearish_db() -> BearishDb:
    with tempfile.NamedTemporaryFile(delete=False, suffix="db") as file:
        return BearishDb(database_path=file.name)


@pytest.fixture(scope="session")
def bearish_init(bearish_db: BearishDb) -> Bearish:
    with requests_mock.Mocker() as req:
        url = "http://test.com"
        req.get(
            url, text=Path(__file__).parent.joinpath("data/equities.csv").read_text()
        )
        equity_query = EquityQuery(countries=["China"], exchanges=["SHZ"])
        bearish = Bearish(equities_query=equity_query, bearish_db=bearish_db)
        bearish.initialize(url)
        return bearish


def test_bearish_init(bearish_init: None, bearish_db: BearishDb):
    equity_query = EquityQuery(countries=["China"], exchanges=["SHZ"])
    equities = bearish_db.read_equities(equity_query)
    assert equities
    assert all(isinstance(eq, Equity) for eq in equities)


def test_bearish_update(bearish_init: None, bearish_db: BearishDb):
    equity_query = EquityQuery(symbols=["000002.SZ"])
    bearish = Bearish(equities_query=equity_query, bearish_db=bearish_db)
    bearish.update("full")
    series = bearish.read_series(months=1)
    financials = bearish.read_financials()
    assert series
    assert financials
    assert all(isinstance(serie, DailyOhlcv) for serie in series)
    assert all(isinstance(financial, Financials) for financial in financials)