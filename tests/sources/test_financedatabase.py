import requests_mock

from bearish.models.assets.equity import Equity
from bearish.models.assets.crypto import Crypto
from bearish.models.assets.currency import Currency
from bearish.models.assets.etfs import Etf
from bearish.models.assets.index import Index
from bearish.sources.financedatabase import FinanceDatabaseSource
from tests.conftest import mock_finance_database_urls


def test_read_assets() -> None:
    with requests_mock.Mocker() as req:
        mock_finance_database_urls(req, index=True)
        assets = FinanceDatabaseSource()._read_assets()
        assert assets
        assert all(isinstance(equity, Equity) for equity in assets.equities)
        assert all(isinstance(crypto, Crypto) for crypto in assets.cryptos)
        assert all(isinstance(currency, Currency) for currency in assets.currencies)
        assert all(isinstance(etf, Etf) for etf in assets.etfs)
        assert all(isinstance(index, Index) for index in assets.index)
