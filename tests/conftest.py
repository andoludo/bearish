import json
import pickle
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from bearish.database.crud import BearishDb
from bearish.database.scripts.upgrade import upgrade


@pytest.fixture(scope="session")
def bearish_db() -> BearishDb:
    with tempfile.NamedTemporaryFile(delete=False, suffix="db") as file:
        return BearishDb(database_path=file.name)


@pytest.fixture(scope="session")
def equities_path() -> Path:
    return Path(__file__).parent.joinpath("data/equities.csv")


@pytest.fixture(scope="session")
def equities(equities_path: Path) -> pd.DataFrame:
    return pd.read_csv(equities_path)


def root_path() -> Path:
    return Path(__file__).parent.joinpath("data", "sources", "alphavantage")


class FakeFundamentalData:
    def get_company_overview(self, ticker):
        overview_path = root_path() / "company_overview.json"
        return json.loads(overview_path.read_text())

    def get_balance_sheet_annual(self, ticker):
        path = root_path() / "balance_sheet_annual.pkl"
        return pickle.loads(path.read_bytes())

    def get_balance_sheet_quarterly(self, ticker):
        path = root_path() / "balance_sheet_quarterly.pkl"
        return pickle.loads(path.read_bytes())

    def get_cash_flow_annual(self, ticker):
        path = root_path() / "cash_flow_annual.pkl"
        return pickle.loads(path.read_bytes())


class FakeTimeSeries:
    def get_symbol_search(self, ticker):
        # data = TimeSeries(
        #     key=os.environ["ALPHAVANTAGE_API_KEY"]
        # ).get_symbol_search("AAPL")
        # balance_sheet_annual_path = Path(__file__).parent / "symbol_search.pkl"
        # balance_sheet_annual_path.write_bytes(pickle.dumps(data))
        symbol_search_path = root_path() / "symbol_search.pkl"
        return pickle.loads(symbol_search_path.read_bytes())

    def get_daily(self, ticker, outputsize: str = "full"):
        # data = TimeSeries(
        #     key=os.environ["ALPHAVANTAGE_API_KEY"]
        # ).get_daily("AAPL",outputsize=outputsize)
        path = root_path() / "daily_series.pkl"
        # path.write_bytes(pickle.dumps(data))
        return pickle.loads(path.read_bytes())
