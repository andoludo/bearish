import tempfile
from pathlib import Path

import pytest
import requests_mock

from bearish.database.crud import BearishDb
from bearish.main import Bearish
from bearish.models.api_keys.api_keys import SourceApiKeys
from bearish.models.query.query import AssetQuery, Symbols
from bearish.sources.alphavantage import AlphaVantageBase, AlphaVantageSource
from bearish.sources.financedatabase import (
    FinanceDatabaseSource,
    RAW_EQUITIES_DATA_URL,
    RAW_CRYPTO_DATA_URL,
    RAW_CURRENCY_DATA_URL,
    RAW_ETF_DATA_URL,
)
from bearish.sources.investpy import (
    InvestPySource,
    RAW_EQUITIES_INVESTSPY_DATA_URL,
    RAW_CRYPTO_INVESTSPY_DATA_URL,
    RAW_ETF_INVESTSPY_DATA_URL,
)
from bearish.sources.yfinance import yFinanceSource
from tests.conftest import FakeFundamentalData, FakeTimeSeries


@pytest.fixture(scope="session")
def bearish_db() -> BearishDb:
    with tempfile.NamedTemporaryFile(delete=False, suffix="db") as file:
        return BearishDb(database_path=Path(file.name))


def test_update_asset_yfinance(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path, sources=[yFinanceSource()], asset_sources=[]
    )
    bearish.write_assets(AssetQuery(symbols=Symbols(equities=["AAPL"])))
    assets = bearish.read_assets(AssetQuery(symbols=Symbols(equities=["AAPL"])))
    assert assets


def test_update_asset_financedatabase(bearish_db: BearishDb):
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
        bearish = Bearish(
            path=bearish_db.database_path,
            asset_sources=[],
            sources=[FinanceDatabaseSource()],
        )
        bearish.write_assets()
        assets = bearish.read_assets(AssetQuery(symbols=Symbols(equities=["AAVE-INR"])))

        assets_multi = bearish.read_assets(
            AssetQuery(symbols=Symbols(equities=["000006.SZ", "AAVE-KRW"]))
        )

        assert assets.cryptos
        assert assets_multi.equities
        assert assets_multi.cryptos


def test_update_assets_multi_sources(bearish_db: BearishDb):
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
        bearish = Bearish(
            path=bearish_db.database_path,
            asset_sources=[FinanceDatabaseSource()],
            sources=[yFinanceSource()],
        )
        bearish.write_assets()

        assets = bearish.read_assets(AssetQuery(symbols=Symbols(equities=["AAVE-INR"])))

        assets_multi = bearish.read_assets(
            AssetQuery(symbols=Symbols(equities=["000006.SZ", "AAVE-KRW"]))
        )
        sources = bearish.read_sources()
        assert assets.cryptos
        assert assets_multi.equities
        assert assets_multi.cryptos
        assert sources


def test_update_financials(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path, asset_sources=[], sources=[yFinanceSource()]
    )
    bearish.write_many_financials(["AAPL"])
    financials = bearish.read_financials(AssetQuery(symbols=Symbols(equities=["AAPL"])))
    assert financials


def test_update_series(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path, asset_sources=[], sources=[yFinanceSource()]
    )
    bearish.write_many_series(["AAPL"], "full")
    series = bearish.read_series(AssetQuery(symbols=Symbols(equities=["AAPL"])))
    assert series
    assert len(series) > 1


def test_update_series_multiple_times(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path, asset_sources=[], sources=[yFinanceSource()]
    )
    bearish.write_many_series(["AAPL"], "5d")
    bearish.write_many_series(["AAPL"], "5d")
    series = bearish.read_series(AssetQuery(symbols=Symbols(equities=["AAPL"])))
    assert series
    assert len(series) > 1


def test_update_financials_alphavantage(bearish_db: BearishDb):
    AlphaVantageBase.fundamentals = FakeFundamentalData()
    AlphaVantageBase.timeseries = FakeTimeSeries()
    bearish = Bearish(
        path=bearish_db.database_path,
        api_keys=SourceApiKeys(keys={"AlphaVantage": "AlphaVantage"}),
        asset_sources=[],
        sources=[AlphaVantageSource()],
    )
    bearish.write_many_financials(["AAPL"])
    financials = bearish.read_financials(AssetQuery(symbols=Symbols(equities=["AAPL"])))
    assert financials


def test_update_series_alphavantage(bearish_db: BearishDb):
    AlphaVantageBase.fundamentals = FakeFundamentalData()
    AlphaVantageBase.timeseries = FakeTimeSeries()
    bearish = Bearish(
        path=bearish_db.database_path,
        api_keys=SourceApiKeys(keys={"AlphaVantage": "AlphaVantage"}),
        asset_sources=[],
        sources=[AlphaVantageSource()],
    )
    bearish.write_many_series(["AAPL"], "full")
    series = bearish.read_series(AssetQuery(symbols=Symbols(equities=["AAPL"])))
    assert series
    assert len(series) > 1


@pytest.mark.skip("Test with real db")
def test_real_db():
    bearish = Bearish(path=Path("/home/aan/Documents/bearish/bearish.db"))
    assets = bearish.read_assets(AssetQuery(exchanges=["BRU"]))
    bearish.write_many_financials([asset.symbol for asset in assets.equities])


@pytest.mark.skip("Test with real db")
def test_real_db_series():
    bearish = Bearish(path=Path("/home/aan/Documents/bearish/bearish.db"))
    assets = bearish.read_assets(AssetQuery(exchanges=["BRU"]))
    bearish.write_many_series([asset.symbol for asset in assets.equities], "full")


def test_write_assets(bearish_db: BearishDb):
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
            path=bearish_db.database_path,
            asset_sources=[FinanceDatabaseSource()],
            sources=[InvestPySource()],
        )
        bearish.write_assets(AssetQuery(countries=["Argentina"]))
        assets = bearish.read_assets(AssetQuery(countries=["Argentina"]))
        assert not assets.is_empty()
