import json
import pickle
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import requests_mock

from bearish.database.crud import BearishDb
from bearish.main import Bearish
from bearish.models.query.query import AssetQuery
from bearish.sources.financedatabase import (
    RAW_EQUITIES_DATA_URL,
    RAW_CRYPTO_DATA_URL,
    RAW_CURRENCY_DATA_URL,
    RAW_ETF_DATA_URL,
    FinanceDatabaseSource,
)
from bearish.sources.investpy import (
    RAW_EQUITIES_INVESTSPY_DATA_URL,
    RAW_CRYPTO_INVESTSPY_DATA_URL,
    RAW_ETF_INVESTSPY_DATA_URL,
    InvestPySource,
)


@pytest.fixture(scope="session")
def bearish_db() -> BearishDb:
    with tempfile.NamedTemporaryFile(delete=False, suffix="db") as file:
        return BearishDb(database_path=file.name)


@pytest.fixture(scope="session")
def _bearish_db_with_assets() -> BearishDb:
    with tempfile.NamedTemporaryFile(delete=False, suffix="db") as file:
        return BearishDb(database_path=file.name)


@pytest.fixture(scope="session")
def bear_db() -> BearishDb:
    bear_path = Path(__file__).parent / "data" / "bear.db"
    return BearishDb(database_path=bear_path)


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


@pytest.fixture(scope="session")
def bearish_db_with_assets(_bearish_db_with_assets: BearishDb):
    with requests_mock.Mocker() as req:
        req.get(
            RAW_EQUITIES_DATA_URL,
            text=Path(__file__)
            .parent.joinpath("data/sources/financedatabase/equities.csv")
            .read_text(),
        )
        req.get(
            RAW_CRYPTO_DATA_URL,
            text=Path(__file__)
            .parent.joinpath("data/sources/financedatabase/cryptos.csv")
            .read_text(),
        )
        req.get(
            RAW_CURRENCY_DATA_URL,
            text=Path(__file__)
            .parent.joinpath("data/sources/financedatabase/currencies.csv")
            .read_text(),
        )
        req.get(
            RAW_ETF_DATA_URL,
            text=Path(__file__)
            .parent.joinpath("data/sources/financedatabase/etfs.csv")
            .read_text(),
        )
        req.get(
            RAW_EQUITIES_INVESTSPY_DATA_URL,
            text=Path(__file__)
            .parent.joinpath("data/sources/investpy/equities.csv")
            .read_text(),
        )
        req.get(
            RAW_CRYPTO_INVESTSPY_DATA_URL,
            text=Path(__file__)
            .parent.joinpath("data/sources/investpy/cryptos.csv")
            .read_text(),
        )
        req.get(
            RAW_ETF_INVESTSPY_DATA_URL,
            text=Path(__file__)
            .parent.joinpath("data/sources/investpy/etfs.csv")
            .read_text(),
        )
        bearish = Bearish(
            path=_bearish_db_with_assets.database_path,
            asset_sources=[FinanceDatabaseSource(), InvestPySource()],
            price_sources=[],
        )
        bearish.write_assets(AssetQuery(countries=["US", "Germany"]))
        return _bearish_db_with_assets
