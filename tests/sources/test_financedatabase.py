from pathlib import Path

import requests_mock

from bearish.models.assets.equity import Equity
from bearish.models.assets.crypto import Crypto
from bearish.models.assets.currency import Currency
from bearish.models.assets.etfs import Etf
from bearish.models.assets.index import Index
from bearish.sources.financedatabase import (
    RAW_EQUITIES_DATA_URL,
    FinanceDatabaseSource,
    RAW_CRYPTO_DATA_URL,
    RAW_CURRENCY_DATA_URL,
    RAW_ETF_DATA_URL,
    RAW_INDEX_DATA_URL,
)


def test_read_assets() -> None:
    with requests_mock.Mocker() as req:
        req.get(
            RAW_EQUITIES_DATA_URL,
            text=Path(__file__)
            .parents[1]
            .joinpath("data/sources/financedatabase/equities.csv")
            .read_text(),
        )
        req.get(
            RAW_CRYPTO_DATA_URL,
            text=Path(__file__)
            .parents[1]
            .joinpath("data/sources/financedatabase/cryptos.csv")
            .read_text(),
        )
        req.get(
            RAW_CURRENCY_DATA_URL,
            text=Path(__file__)
            .parents[1]
            .joinpath("data/sources/financedatabase/currencies.csv")
            .read_text(),
        )
        req.get(
            RAW_ETF_DATA_URL,
            text=Path(__file__)
            .parents[1]
            .joinpath("data/sources/financedatabase/etfs.csv")
            .read_text(),
        )
        req.get(
            RAW_INDEX_DATA_URL,
            text=Path(__file__)
            .parents[1]
            .joinpath("data/sources/financedatabase/index.csv")
            .read_text(),
        )
        assets = FinanceDatabaseSource()._read_assets()
        assert assets
        assert all(isinstance(equity, Equity) for equity in assets.equities)
        assert all(isinstance(crypto, Crypto) for crypto in assets.cryptos)
        assert all(isinstance(currency, Currency) for currency in assets.currencies)
        assert all(isinstance(etf, Etf) for etf in assets.etfs)
        assert all(isinstance(index, Index) for index in assets.index)
