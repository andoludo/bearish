import os
import tempfile
from pathlib import Path

import pytest
import requests_mock

from bearish.database.crud import BearishDb
from bearish.main import Bearish
from bearish.models.api_keys.api_keys import SourceApiKeys
from bearish.models.base import Ticker, TrackerQuery
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery, Symbols
from bearish.sources.alphavantage import AlphaVantageBase, AlphaVantageSource
from bearish.sources.financedatabase import (
    FinanceDatabaseSource,
    RAW_EQUITIES_DATA_URL,
    RAW_CRYPTO_DATA_URL,
    RAW_CURRENCY_DATA_URL,
    RAW_ETF_DATA_URL,
)
from bearish.sources.financial_modelling_prep import FmpAssetsSource, FmpSource
from bearish.sources.investpy import (
    InvestPySource,
    RAW_EQUITIES_INVESTSPY_DATA_URL,
    RAW_CRYPTO_INVESTSPY_DATA_URL,
    RAW_ETF_INVESTSPY_DATA_URL,
)
from bearish.sources.tiingo import TiingoSource
from bearish.sources.yfinance import yFinanceSource
from tests.conftest import FakeFundamentalData, FakeTimeSeries


@pytest.fixture(scope="session")
def bearish_db() -> BearishDb:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as file:
        bearish = BearishDb(database_path=Path(file.name))
        return bearish


def test_update_asset_yfinance(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path,
        price_sources=[yFinanceSource()],
        financials_sources=[],
        asset_sources=[],
    )
    bearish.write_assets(AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")])))
    assets = bearish.read_assets(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert assets


@pytest.mark.skip("Test with real db")
def test_update_asset_fmp(bearish_db: BearishDb):
    api_keys = SourceApiKeys(keys={"FMPAssets": "..."})
    bearish = Bearish(
        api_keys=api_keys,
        path=bearish_db.database_path,
        price_sources=[],
        financials_sources=[],
        asset_sources=[FmpAssetsSource()],
    )
    bearish.write_assets(AssetQuery(exchanges=["BRU"]))
    assets = bearish.read_assets(AssetQuery(exchanges=["NASDAQ"]))
    assert not assets.is_empty()


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
            asset_sources=[FinanceDatabaseSource()],
            price_sources=[],
            financials_sources=[],
        )
        bearish.write_assets()
        assets = bearish.read_assets(
            AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAVE-INR")]))
        )

        assets_multi = bearish.read_assets(
            AssetQuery(
                symbols=Symbols(
                    equities=[Ticker(symbol="000006.SZ"), Ticker(symbol="AAVE-KRW")]
                )
            )
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
            price_sources=[yFinanceSource()],
            financials_sources=[],
        )
        bearish.write_assets()

        assets = bearish.read_assets(
            AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAVE-INR")]))
        )

        assets_multi = bearish.read_assets(
            AssetQuery(
                symbols=Symbols(
                    equities=[Ticker(symbol="000006.SZ"), Ticker(symbol="AAVE-KRW")]
                )
            )
        )
        sources = bearish.read_sources()
        assert assets.cryptos
        assert assets_multi.equities
        assert assets_multi.cryptos
        assert sources


def test_update_financials(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path,
        asset_sources=[],
        price_sources=[],
        financials_sources=[yFinanceSource()],
    )
    bearish.write_many_financials(
        [Ticker(symbol="AAPL", source="Yfinance", exchange="NASDAQ")]
    )
    financials = bearish.read_financials(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert financials


def test_update_series(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path,
        asset_sources=[],
        price_sources=[yFinanceSource()],
    )
    bearish.write_many_series([Ticker(symbol="AIR.PA")], "max")
    series = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AIR.PA")]))
    )
    assert series
    assert len(series) > 1


def test_trackers(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path,
        asset_sources=[],
        price_sources=[yFinanceSource()],
        financials_sources=[yFinanceSource()],
    )
    bearish.write_many_financials([Ticker(symbol="AIR.PA")])
    bearish.write_many_series([Ticker(symbol="AIR.PA")], "max")
    financials = bearish._bearish_db.read_tracker(
        TrackerQuery(source="Yfinance", financials=True)
    )
    assert financials


def test_update_series_multiple_times(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path,
        asset_sources=[],
        price_sources=[yFinanceSource()],
    )
    bearish.write_many_series([Ticker(symbol="AIR.PA", source="Yfinance")], "5d")
    bearish.write_many_series([Ticker(symbol="AIR.PA", source="Yfinance")], "5d")
    series = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AIR.PA")]))
    )
    assert series
    assert len(series) > 1


def test_update_financials_alphavantage(bearish_db: BearishDb):
    AlphaVantageBase.fundamentals = FakeFundamentalData()
    AlphaVantageBase.timeseries = FakeTimeSeries()
    bearish = Bearish(
        path=bearish_db.database_path,
        api_keys=SourceApiKeys(keys={"AlphaVantage": "AlphaVantage"}),
        asset_sources=[],
        financials_sources=[AlphaVantageSource()],
    )
    bearish.write_many_financials([Ticker(symbol="AAPL")])
    financials = bearish.read_financials(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert financials


def test_update_series_alphavantage(bearish_db: BearishDb):
    AlphaVantageBase.fundamentals = FakeFundamentalData()
    AlphaVantageBase.timeseries = FakeTimeSeries()
    bearish = Bearish(
        path=bearish_db.database_path,
        api_keys=SourceApiKeys(keys={"AlphaVantage": "AlphaVantage"}),
        asset_sources=[],
        price_sources=[AlphaVantageSource()],
    )
    bearish.write_many_series([Ticker(symbol="AAPL", exchange="NASDAQ")], "max")
    series = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert series
    assert len(series) > 1


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
            asset_sources=[FinanceDatabaseSource(), InvestPySource()],
            price_sources=[],
        )
        bearish.write_assets(AssetQuery(countries=["Argentina"]))
        assets = bearish.read_assets(AssetQuery(countries=["Argentina"]))
        assert not assets.is_empty()


def test_write_assets_finance_database(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path,
        asset_sources=[FinanceDatabaseSource()],
        price_sources=[],
    )
    bearish.write_assets(AssetQuery(countries=["Argentina"]))
    assets = bearish.read_assets(AssetQuery(countries=["Argentina"]))
    assert not assets.is_empty()


def test_write_assets_tiingo(bearish_db: BearishDb):
    source_api_keys = SourceApiKeys(keys={"Tiingo": os.getenv("TIINGO_API_KEY")})
    bearish = Bearish(
        api_keys=source_api_keys,
        path=bearish_db.database_path,
        asset_sources=[],
        price_sources=[TiingoSource()],
    )
    bearish.write_many_series(
        tickers=[Ticker(symbol="AAPL", exchange="NASDAQ")], type="max"
    )
    prices = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert prices
    assert all(isinstance(p, Price) for p in prices)


def test_write_assets_fmp(bearish_db: BearishDb):
    source_api_keys = SourceApiKeys(keys={"FMP": os.getenv("FMP_API_KEY")})
    bearish = Bearish(
        api_keys=source_api_keys,
        path=bearish_db.database_path,
        asset_sources=[],
        price_sources=[FmpSource()],
    )
    bearish.write_many_series(
        tickers=[Ticker(symbol="AAPL", exchange="NASDAQ")], type="max"
    )
    prices = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert prices
    assert all(isinstance(p, Price) for p in prices)


def test_write_assets_yfinance(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path,
        asset_sources=[],
        price_sources=[yFinanceSource()],
    )
    bearish.write_many_series(tickers=[Ticker(symbol="AIR.PA")], type="1d")
    prices = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AIR.PA")]))
    )
    assert prices
    assert all(isinstance(p, Price) for p in prices)


def test_detailed_assets(bearish_db: BearishDb) -> None:
    bearish = Bearish(
        path=bearish_db.database_path,
        detailed_asset_sources=[yFinanceSource()],
    )
    asset_query = AssetQuery(
        symbols=Symbols(
            equities=[
                Ticker(symbol="VOW"),
                Ticker(symbol="ACR"),
                Ticker(symbol="1WE"),
                Ticker(symbol="VBK"),
            ]
        )
    )
    bearish.write_detailed_assets(asset_query)
    assets = bearish.read_assets(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="VOW")]))
    )
    assert assets.equities


def test_update_financials_fmp(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path,
        api_keys=SourceApiKeys(keys={"FMP": os.getenv("FMP_API_KEY")}),
        asset_sources=[],
        financials_sources=[FmpSource()],
    )
    bearish.write_many_financials([Ticker(symbol="AAPL", exchange="NASDAQ")])
    financials = bearish.read_financials(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert financials
