from typing import ClassVar, Dict, List

from pydantic import Field

from bearish.exchanges.exchanges import Countries
from bearish.models.assets.crypto import Crypto
from bearish.models.assets.equity import Equity
from bearish.models.assets.etfs import Etf
from bearish.models.base import SourceBase
from bearish.sources.base import (
    UrlSources,
    UrlSource,
    DatabaseCsvSource,
)
from bearish.types import Sources

RAW_EQUITIES_INVESTSPY_DATA_URL = "https://raw.githubusercontent.com/alvarobartt/investpy/refs/heads/master/investpy/resources/stocks.csv"
RAW_CRYPTO_INVESTSPY_DATA_URL = "https://raw.githubusercontent.com/alvarobartt/investpy/refs/heads/master/investpy/resources/cryptos.csv"
RAW_ETF_INVESTSPY_DATA_URL = "https://raw.githubusercontent.com/alvarobartt/investpy/refs/heads/master/investpy/resources/etfs.csv"


class InvestPyBase(SourceBase):
    __source__: Sources = "investpy"


class InvestPyEquity(InvestPyBase, Equity):
    __alias__: ClassVar[Dict[str, str]] = {
        "symbol": "symbol",
        "name": "name",
        "currency": "currency",
        "isin": "isin",
        "country": "country",
    }


class InvestPyCrypto(InvestPyBase, Crypto):
    __alias__: ClassVar[Dict[str, str]] = {
        "symbol": "symbol",
        "name": "name",
        "currency": "currency",
    }


class InvestPyEtf(InvestPyBase, Etf):
    __alias__: ClassVar[Dict[str, str]] = {
        "symbol": "symbol",
        "name": "name",
        "currency": "currency",
        "isin": "isin",
        "country": "country",
        "stock_exchange": "exchange",
    }


class InvestPySource(InvestPyBase, DatabaseCsvSource):
    countries: List[Countries] = Field(default_factory=list)
    __url_sources__ = UrlSources(
        equity=UrlSource(
            url=RAW_EQUITIES_INVESTSPY_DATA_URL,
            type_class=InvestPyEquity,
            filters=["symbol", "country"],
        ),
        crypto=UrlSource(
            url=RAW_CRYPTO_INVESTSPY_DATA_URL,
            type_class=InvestPyCrypto,
            filters=["symbol"],
        ),
        etf=UrlSource(
            url=RAW_ETF_INVESTSPY_DATA_URL, type_class=InvestPyEtf, filters=["symbol"]
        ),
    )
