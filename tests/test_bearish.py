import tempfile
from pathlib import Path

import pytest
import requests_mock

from bearish.database.crud import BearishDb
from bearish.main import Bearish, AssetQuery
from bearish.sources.financedatabase import FinanceDatabaseSource, RAW_EQUITIES_DATA_URL, RAW_CRYPTO_DATA_URL, \
    RAW_CURRENCY_DATA_URL, RAW_ETF_DATA_URL
from bearish.sources.yfinance import yFinanceSource


@pytest.fixture(scope="session")
def bearish_db() -> BearishDb:
    with tempfile.NamedTemporaryFile(delete=False, suffix="db") as file:
        return BearishDb(database_path=file.name)




def test_update_asset_yfinance(bearish_db: BearishDb):
    bearish = Bearish(bearish_db=bearish_db, sources=[yFinanceSource()])
    bearish.write_assets(filters=["AAPL"])
    assets = bearish.read_assets(AssetQuery(symbols=["AAPL"]))
    assert assets

def test_update_asset_financedatabase(bearish_db: BearishDb):
    with requests_mock.Mocker() as req:
        req.get(
            RAW_EQUITIES_DATA_URL, text=Path(__file__).parent.joinpath("data/equities.csv").read_text()
        )
        req.get(
            RAW_CRYPTO_DATA_URL, text=Path(__file__).parent.joinpath("data/cryptos.csv").read_text()
        )
        req.get(
            RAW_CURRENCY_DATA_URL, text=Path(__file__).parent.joinpath("data/currencies.csv").read_text()
        )
        req.get(
            RAW_ETF_DATA_URL, text=Path(__file__).parent.joinpath("data/etfs.csv").read_text()
        )
        bearish = Bearish(bearish_db=bearish_db, sources=[FinanceDatabaseSource()])
        bearish.write_assets()
        assets = bearish.read_assets(AssetQuery(symbols=["AAVE-INR"]))
        assets_multi = bearish.read_assets(AssetQuery(symbols=["000006.SZ", "AAVE-KRW"]))
        assert assets.cryptos
        assert assets_multi.equities
        assert assets_multi.cryptos


def test_update_financials(bearish_db: BearishDb):
    bearish = Bearish(bearish_db=bearish_db, sources=[yFinanceSource()])
    bearish.write_financials("AAPL")
    financials = bearish.read_financials(AssetQuery(symbols=["AAPL"]))
    assert financials


def test_update_series(bearish_db: BearishDb):
    bearish = Bearish(bearish_db=bearish_db, sources=[yFinanceSource()])
    bearish.write_series("AAPL", "full")
    series = bearish.read_series(AssetQuery(symbols=["AAPL"]))
    assert series
    assert len(series) > 1
