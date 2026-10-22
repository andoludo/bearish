import os
import tempfile
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import pytest
import requests_mock


from bearish.database.crud import BearishDb
from bearish.database.schemas import PriceIndexORM, PriceEtfORM
from bearish.main import Bearish, Filter
from bearish.models.api_keys.api_keys import SourceApiKeys
from bearish.models.base import Ticker, TrackerQuery, PriceTracker, FinancialsTracker
from bearish.models.price.price import Price
from bearish.models.price.prices import Prices
from bearish.models.query.query import AssetQuery, Symbols

from bearish.sources.financedatabase import FinanceDatabaseSource
from bearish.sources.investpy import InvestPySource
from bearish.sources.tiingo import TiingoSource
from bearish.sources.yfinance import yFinanceSource
from tests.conftest import mock_finance_database_urls, mock_investpy_urls


def test_update_asset_financedatabase(bearish_db: BearishDb) -> None:
    with requests_mock.Mocker() as req:
        mock_finance_database_urls(req)
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


def test_update_assets_multi_sources(bearish_db: BearishDb) -> None:
    with requests_mock.Mocker() as req:
        mock_finance_database_urls(req)
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


@pytest.mark.network
def test_get_prices(bearish_db_with_assets: BearishDb) -> None:
    bearish = Bearish(
        path=bearish_db_with_assets.database_path,
    )
    filter = Filter(countries=["US"], filters=["DAL"])
    bearish.get_detailed_tickers(filter)  # type: ignore
    bearish.get_prices(filter)  # type: ignore
    prices = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="DAL")]))
    )
    assert prices


@pytest.mark.network
def test_get_financials(bearish_db_with_assets: BearishDb) -> None:
    bearish = Bearish(
        path=bearish_db_with_assets.database_path,
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


@pytest.mark.lfs
def test_read_tracker(bear_db: BearishDb) -> None:
    date_today = bear_db.read_price_tracker("AAPL")
    reference_date = date_today - timedelta(days=12)
    date_str = reference_date.strftime("%Y-%m-%d")
    trackers = bear_db.read_tracker(
        TrackerQuery(reference_date=datetime.strptime(date_str, "%Y-%m-%d").date()),
        PriceTracker,
    )
    assert trackers
    assert len(trackers) == 6


@pytest.mark.lfs
def test_read_tracker_today(bear_db: BearishDb) -> None:
    date_today = bear_db.read_price_tracker("AAPL")
    reference_date = date_today - timedelta(days=3)
    date_str = reference_date.strftime("%Y-%m-%d")
    trackers = bear_db.read_tracker(
        TrackerQuery(reference_date=datetime.strptime(date_str, "%Y-%m-%d").date()),
        PriceTracker,
    )
    assert trackers


@pytest.mark.lfs
@pytest.mark.network
def test_update_prices(bear_db: BearishDb) -> None:

    date_today = date.today()
    reference_date = date_today - timedelta(days=60)
    bearish = Bearish(path=bear_db.database_path)
    bearish.update_prices(reference_date=reference_date, series_length="3mo")
    series = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")])), months=2
    )
    assert len({p.date.month for p in series}) in [2, 3]


@pytest.mark.lfs
@pytest.mark.network
def test_update_financials(bear_db: BearishDb) -> None:
    date_str = "2025-06-22"
    reference_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    bearish = Bearish(path=bear_db.database_path)
    bearish.update_financials(reference_date=reference_date)
    financials = bearish.read_financials(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert financials


@pytest.mark.network
def test_index_query(bearish_db: BearishDb) -> None:
    with requests_mock.Mocker() as req:
        mock_finance_database_urls(req, index=True)
        bearish = Bearish(
            path=bearish_db.database_path, asset_sources=[FinanceDatabaseSource()]
        )
        bearish.write_assets()
        bearish.get_prices_index()
        assets_query = AssetQuery(symbols=Symbols(index=[Ticker(symbol="^GSPC")]))
        series = bearish.read_series(assets_query, table=PriceIndexORM)
        assert series


@pytest.mark.lfs
@pytest.mark.network
def test_price_etf(bear_db: BearishDb) -> None:
    bearish = Bearish(path=bear_db.database_path)
    etf_symbols = bearish.get_prices_etf(series_length="1d", limit=5)
    assets_query = AssetQuery(
        symbols=Symbols(index=[Ticker(symbol=symbol) for symbol in etf_symbols])
    )
    series = bearish.read_series(assets_query, table=PriceEtfORM)
    assert series
