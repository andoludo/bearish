import os
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
import requests_mock


from bearish.database.crud import BearishDb
from bearish.main import Bearish, Filter
from bearish.models.api_keys.api_keys import SourceApiKeys
from bearish.models.base import Ticker, TrackerQuery, PriceTracker, FinancialsTracker
from bearish.models.price.price import Price
from bearish.models.price.prices import Prices
from bearish.models.query.query import AssetQuery, Symbols

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


def test_write_financials(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path,
        asset_sources=[],
        price_sources=[],
        financials_sources=[yFinanceSource()],
    )
    bearish.write_many_financials(
        [
            Ticker(symbol="AAPL", source="Yfinance", exchange="NASDAQ"),
            Ticker(symbol="AIR.PA"),
        ]
    )
    financials = bearish.read_financials(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert not financials.is_empty()
    assert financials.quarterly_financial_metrics


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
        TrackerQuery(source="Yfinance"), tracker_type=FinancialsTracker
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
    tracked_ticker = bearish._get_tracked_tickers(TrackerQuery(), PriceTracker)
    assert prices
    assert tracked_ticker
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
    bearish.write_many_series(
        tickers=[
            Ticker(symbol="AIR.PA"),
            Ticker(symbol="BNP.PA"),
            Ticker(symbol="AIR.PA"),
            Ticker(symbol="MC.PA"),
            Ticker(symbol="ORA.PA"),
        ],
        type="1d",
    )
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
                Ticker(symbol="BNP.PA"),
                Ticker(symbol="AIR.PA"),
                Ticker(symbol="MC.PA"),
                Ticker(symbol="ORA.PA"),
            ]
        )
    )
    bearish.write_detailed_assets(asset_query)
    assets = bearish.read_assets(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AIR.PA")]))
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


def test_write_financials_yfinance(bearish_db: BearishDb):
    bearish = Bearish(
        path=bearish_db.database_path,
        asset_sources=[],
        price_sources=[],
        financials_sources=[yFinanceSource()],
    )
    bearish.write_many_financials(
        [
            Ticker(symbol="MLHCF.PA"),
            Ticker(symbol="BNP.PA"),
            Ticker(symbol="AIR.PA"),
            Ticker(symbol="MC.PA"),
            Ticker(symbol="ORA.PA"),
        ]
    )
    financials = bearish.read_financials(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="MLHCF.PA")]))
    )
    assert financials


def test_get_detailed_tickers(bearish_db_with_assets: BearishDb):
    bearish = Bearish(
        path=bearish_db_with_assets.database_path,
        api_keys=SourceApiKeys(keys={"FMP": os.getenv("FMP_API_KEY")}),
    )
    filter = Filter(countries=["US"], filters=["NVDA"])
    bearish.get_detailed_tickers(filter)  # type: ignore
    assets = bearish.read_assets(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="NVDA")]))
    )
    assert len(assets.equities) == 2


def test_get_detailed_tickers_fmp(bearish_db_with_assets: BearishDb):
    bearish = Bearish(
        path=bearish_db_with_assets.database_path,
        api_keys=SourceApiKeys(keys={"FMP": os.getenv("FMP_API_KEY")}),
        detailed_asset_sources=[FmpSource()],
        financials_sources=[FmpSource()],
        price_sources=[FmpSource()],
    )
    filter = Filter(countries=["US"], filters=["NVDA"])
    bearish.get_detailed_tickers(filter)  # type: ignore
    assets = bearish.read_assets(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="NVDA")]))
    )
    assert len(assets.equities) > 1


def test_get_prices(bearish_db_with_assets: BearishDb):
    bearish = Bearish(
        path=bearish_db_with_assets.database_path,
        api_keys=SourceApiKeys(keys={"FMP": os.getenv("FMP_API_KEY")}),
    )
    filter = Filter(countries=["US"], filters=["DAL"])
    bearish.get_detailed_tickers(filter)  # type: ignore
    bearish.get_prices(filter)  # type: ignore
    prices = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="DAL")]))
    )
    assert prices


def test_get_financials(bearish_db_with_assets: BearishDb):
    bearish = Bearish(
        path=bearish_db_with_assets.database_path,
        api_keys=SourceApiKeys(keys={"FMP": os.getenv("FMP_API_KEY")}),
    )
    filter = Filter(countries=["US"], filters=["DAL", "NVDA"])
    bearish.get_detailed_tickers(filter)  # type: ignore
    bearish.get_financials(filter)  # type: ignore
    financials = bearish.read_financials(
        AssetQuery(
            symbols=Symbols(equities=[Ticker(symbol="DAL"), Ticker(symbol="NVDA")])
        )
    )
    assert financials


def test_read_tracker(bear_db: BearishDb) -> None:
    date_str = "2025-06-30"
    trackers = bear_db.read_tracker(
        TrackerQuery(reference_date=datetime.strptime(date_str, "%Y-%m-%d").date()),
        PriceTracker,
    )
    assert trackers
    assert len(trackers) == 2


def test_read_tracker_today(bear_db: BearishDb) -> None:
    date_str = "2025-06-20"
    trackers = bear_db.read_tracker(
        TrackerQuery(reference_date=datetime.strptime(date_str, "%Y-%m-%d").date()),
        PriceTracker,
    )
    assert not trackers


def test_update_prices(bear_db: BearishDb) -> None:
    date_str = "2025-06-22"
    reference_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    bearish = Bearish(path=bear_db.database_path)
    bearish.update_prices(reference_date=reference_date)
    series = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert len({p.created_at for p in series}) > 1


def test_update_financials(bear_db: BearishDb) -> None:
    date_str = "2025-06-22"
    reference_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    bearish = Bearish(path=bear_db.database_path)
    bearish.update_financials(reference_date=reference_date)
    financials = bearish.read_financials(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert financials
