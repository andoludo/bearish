from typing import ClassVar, Dict

from bearish.models.assets.crypto import Crypto
from bearish.models.assets.currency import Currency
from bearish.models.assets.equity import Equity
from bearish.models.assets.etfs import Etf
from bearish.models.base import SourceBase
from bearish.sources.base import (
    UrlSources,
    UrlSource,
    DatabaseCsvSource,
)

RAW_EQUITIES_DATA_URL = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/refs/heads/main/database/equities.csv"
RAW_CRYPTO_DATA_URL = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/refs/heads/main/database/cryptos.csv"
RAW_CURRENCY_DATA_URL = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/refs/heads/main/database/currencies.csv"
RAW_ETF_DATA_URL = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/refs/heads/main/database/etfs.csv"


class FinanceDatabaseBase(SourceBase):
    __source__ = "FinanceDatabase"
    __alias__: ClassVar[Dict[str, str]] = {
        "symbol": "symbol",
        "cryptocurrency": "cryptocurrency",
    }


class FinanceDatabaseEquity(FinanceDatabaseBase, Equity): ...


class FinanceDatabaseCrypto(FinanceDatabaseBase, Crypto): ...


class FinanceDatabaseCurrency(FinanceDatabaseBase, Currency): ...


class FinanceDatabaseEtf(FinanceDatabaseBase, Etf): ...


class FinanceDatabaseSource(FinanceDatabaseBase, DatabaseCsvSource):
    __url_sources__ = UrlSources(
        equity=UrlSource(
            url=RAW_EQUITIES_DATA_URL,
            type_class=FinanceDatabaseEquity,
            filters=["symbol", "country"],
        ),
        crypto=UrlSource(
            url=RAW_CRYPTO_DATA_URL,
            type_class=FinanceDatabaseCrypto,
            filters=["symbol", "cryptocurrency"],
        ),
        currency=UrlSource(
            url=RAW_CURRENCY_DATA_URL,
            type_class=FinanceDatabaseCurrency,
            filters=["symbol"],
        ),
        etf=UrlSource(
            url=RAW_ETF_DATA_URL, type_class=FinanceDatabaseEtf, filters=["symbol"]
        ),
    )
