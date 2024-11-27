import abc
import logging
from io import StringIO
from typing import List, Optional, Type

import pandas as pd
import requests
from pydantic import ConfigDict, validate_call, BaseModel, Field

from bearish.models.query.query import AssetQuery
from bearish.models.assets.assets import Assets
from bearish.models.base import SourceBase, DataSourceBase

from bearish.models.financials.base import Financials
from bearish.models.price.price import Price

logger = logging.getLogger(__name__)


class AbstractSource(SourceBase, abc.ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @validate_call(validate_return=True)
    def read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        try:
            return self._read_assets(query)
        except Exception as e:
            logger.error(f"Error reading assets from {type(self).__name__}: {e}")
            return Assets()

    @validate_call(validate_return=True)
    def read_financials(self, ticker: str) -> Financials:
        try:
            logger.info(f"Reading Financials from {type(self).__name__}: for {ticker}")
            return self._read_financials(ticker)
        except Exception as e:
            logger.error(f"Error reading Financials from {type(self).__name__}: {e}")
            return Financials()

    @abc.abstractmethod
    def _read_financials(self, ticker: str) -> Financials:
        ...

    @abc.abstractmethod
    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        ...

    @abc.abstractmethod
    def read_series(self, ticker: str, type: str) -> List[Price]:
        ...

class UrlSource(BaseModel):
    url: str
    results: List[SourceBase] = Field(default_factory=list)
    type_class: Type[SourceBase]
    filters: Optional[List[str]] = None

class UrlSources(BaseModel):
    equity: UrlSource
    crypto: UrlSource
    currency: Optional[UrlSource] = Field(None)
    etf: UrlSource

    def to_assets(self) ->Assets:

        return Assets(
            equities=self.equity.results,
            cryptos=self.crypto.results,
            currencies=self.currency.results if self.currency else [],
            etfs=self.etf.results,
        )

class DatabaseCsvSource(AbstractSource):
    __url_sources__: UrlSources
    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        sources = self.__url_sources__
        for field in sources.model_fields:
            url_source = getattr(sources, field)
            if url_source is None:
                continue
            response = requests.get(url_source.url, timeout=10)
            if not response.ok:
                raise Exception(f"Failed to download data from {url_source.url}")
            data = pd.read_csv(StringIO(response.text))
            url_source.results = self._from_dataframe(
                data, url_source.type_class, url_source.filters
            )
        return sources.to_assets()

    def _from_dataframe(
        self,
        data: pd.DataFrame,
        databaseclass: Type[DataSourceBase],
        filters: Optional[list[str]] = None,
    ) -> List[DataSourceBase]:
        if filters:
            data = data.dropna(subset=filters)
        equities_mapping = [equity.to_dict() for _, equity in data.iterrows()]
        return [
            databaseclass(**equity_mapping)
            for equity_mapping in equities_mapping
        ]

    def _read_financials(self, ticker: str) -> Financials:
        return Financials()

    def read_series(self, ticker: str, type: str) -> List[Price]:
        return []

