import json
import os
import pickle
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import requests_mock

from bearish.analysis.analysis import Analysis
from bearish.database.crud import BearishDb
from bearish.main import Bearish, Filter
from bearish.models.api_keys.api_keys import SourceApiKeys
from bearish.models.base import Ticker
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
def _bearish_db_with_analysis() -> BearishDb:
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


@pytest.fixture(scope="session")
def bearish_db_with_analysis(bearish_db_with_assets: BearishDb):
    bearish = Bearish(
        path=bearish_db_with_assets.database_path,
        api_keys=SourceApiKeys(keys={"FMP": os.getenv("FMP_API_KEY")}),
    )
    filter = Filter(countries=["US"], filters=["DAL", "NVDA"])
    bearish.get_detailed_tickers(filter)  # type: ignore
    bearish.get_financials(filter)  # type: ignore
    bearish.get_prices(filter)  # type: ignore
    for ticker in [Ticker(symbol="DAL"), Ticker(symbol="NVDA")]:
        analysis = Analysis.from_ticker(bearish_db_with_assets, ticker)
        bearish._bearish_db.write_analysis(analysis)
    return bearish_db_with_assets
