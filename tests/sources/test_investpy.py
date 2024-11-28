from pathlib import Path

import requests_mock

from bearish.models.assets.equity import Equity
from bearish.models.assets.crypto import Crypto
from bearish.models.assets.currency import Currency
from bearish.models.assets.etfs import Etf

from bearish.sources.investpy import (
    InvestPySource,
    RAW_EQUITIES_INVESTSPY_DATA_URL,
    RAW_CRYPTO_INVESTSPY_DATA_URL,
    RAW_ETF_INVESTSPY_DATA_URL,
)


def test_read_assets() -> None:
    with requests_mock.Mocker() as req:
        req.get(
            RAW_EQUITIES_INVESTSPY_DATA_URL,
            text=Path(__file__)
            .parents[1]
            .joinpath("data/sources/investpy/equities.csv")
            .read_text(),
        )
        req.get(
            RAW_CRYPTO_INVESTSPY_DATA_URL,
            text=Path(__file__)
            .parents[1]
            .joinpath("data/sources/investpy/cryptos.csv")
            .read_text(),
        )
        req.get(
            RAW_ETF_INVESTSPY_DATA_URL,
            text=Path(__file__)
            .parents[1]
            .joinpath("data/sources/investpy/etfs.csv")
            .read_text(),
        )
        assets = InvestPySource()._read_assets()
        assert assets
        assert all(isinstance(equity, Equity) for equity in assets.equities)
        assert all(isinstance(crypto, Crypto) for crypto in assets.cryptos)
        assert all(isinstance(currency, Currency) for currency in assets.currencies)
        assert all(isinstance(etf, Etf) for etf in assets.etfs)
