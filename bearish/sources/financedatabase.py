from io import StringIO
from typing import Optional, List, Type

import pandas as pd
import requests  # type: ignore
from pydantic import BaseModel, Field

from bearish.models.base import CandleStick, Equity, Crypto, Currency, Etf
from bearish.sources.base import AbstractSource, Assets, Financials

RAW_EQUITIES_DATA_URL = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/refs/heads/main/database/equities.csv"
RAW_CRYPTO_DATA_URL = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/refs/heads/main/database/cryptos.csv"
RAW_CURRENCY_DATA_URL = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/refs/heads/main/database/currencies.csv"
RAW_ETF_DATA_URL = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/refs/heads/main/database/etfs.csv"


class FinanceDatabaseBase(BaseModel):
    __source__ = "FinanceDatabase"
    __alias__ = {"symbol": "symbol", "cryptocurrency": "cryptocurrency"}


class FinanceDatabaseEquity(FinanceDatabaseBase, Equity):
    ...


class FinanceDatabaseCrypto(FinanceDatabaseBase, Crypto):
    ...


class FinanceDatabaseCurrency(FinanceDatabaseBase, Currency):
    ...


class FinanceDatabaseEtf(FinanceDatabaseBase, Etf):
    ...


class UrlSource(BaseModel):
    url: str
    results: List[FinanceDatabaseBase] = Field(default_factory=list)
    type_class: Type[FinanceDatabaseBase]
    filters: Optional[List[str]] = None


class FinanceDatabaseUrlSources(BaseModel):
    equity: UrlSource
    crypto: UrlSource
    currency: UrlSource
    etf: UrlSource


class FinanceDatabaseSource(AbstractSource):
    def _read_assets(self, keywords: Optional[List[str]] = None) -> Assets:
        sources = FinanceDatabaseUrlSources(
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
        for field in sources.model_fields:
            url_source = getattr(sources, field)
            response = requests.get(url_source.url, timeout=10)
            if not response.ok:
                raise Exception(f"Failed to download data from {url_source.url}")
            data = pd.read_csv(StringIO(response.text))
            url_source.results = self._from_dataframe(
                data, url_source.type_class, url_source.filters
            )
        return Assets(
            equities=sources.equity.results,
            cryptos=sources.crypto.results,
            currencies=sources.currency.results,
            etfs=sources.etf.results,
        )

    def _from_dataframe(
        self,
        data: pd.DataFrame,
        financedatabaseclass: Type[FinanceDatabaseBase],
        filters: Optional[list[str]] = None,
    ) -> List[FinanceDatabaseBase]:
        if filters:
            data = data.dropna(subset=filters)
        equities_mapping = [equity.to_dict() for _, equity in data.iterrows()]
        return [
            financedatabaseclass(**equity_mapping)
            for equity_mapping in equities_mapping
        ]

    def _read_financials(self, ticker: str) -> Financials:
        return Financials()

    def read_series(self, ticker: str, type: str) -> List[CandleStick]:
        return []
