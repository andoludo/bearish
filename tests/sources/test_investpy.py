import requests_mock

from bearish.models.assets.equity import Equity
from bearish.models.assets.crypto import Crypto
from bearish.models.assets.currency import Currency
from bearish.models.assets.etfs import Etf
from bearish.sources.investpy import InvestPySource
from tests.conftest import mock_investpy_urls


def test_read_assets() -> None:
    with requests_mock.Mocker() as req:
        mock_investpy_urls(req)
        assets = InvestPySource()._read_assets()
        assert assets
        assert all(isinstance(equity, Equity) for equity in assets.equities)
        assert all(isinstance(crypto, Crypto) for crypto in assets.cryptos)
        assert all(isinstance(currency, Currency) for currency in assets.currencies)
        assert all(isinstance(etf, Etf) for etf in assets.etfs)
