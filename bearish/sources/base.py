import abc
import logging
from functools import wraps
from io import StringIO
from typing import List, Optional, Type, Callable, Any, cast

import pandas as pd
import requests  # type: ignore
from pydantic import ConfigDict, validate_call, BaseModel, Field

from bearish.exceptions import InvalidApiKeyError, LimitApiKeyReachedError
from bearish.exchanges.exchanges import Countries, Exchanges, exchanges_factory
from bearish.models.query.query import AssetQuery
from bearish.models.assets.assets import Assets
from bearish.models.base import SourceBase, DataSourceBase, Ticker

from bearish.models.financials.base import Financials
from bearish.models.price.price import Price
from bearish.types import Sources, SeriesLength
from bearish.utils.utils import observability

logger = logging.getLogger(__name__)


class ValidTickers(BaseModel):
    sources: List[Sources] = Field(default_factory=list)
    exchanges: List[str] = Field(default_factory=list)

    def is_valid(self, ticker: Ticker) -> bool:
        if not self.exchanges and not self.sources:
            return True
        elif self.exchanges and not self.sources:
            return ticker.exchange in self.exchanges
        elif self.sources and not self.exchanges:
            return ticker.source in self.sources
        else:
            return bool(
                ticker.exchange is not None
                and self.exchanges
                and ticker.source in self.sources
            )


class ApiUsage(BaseModel):
    calls: int = 0
    calls_limit: Optional[int] = None

    def limit_reached(self) -> bool:
        return self.calls >= self.calls_limit if self.calls_limit else False

    def add_api_calls(self, calls: int) -> None:
        self.calls += calls


def check_api_limit(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(self: "AbstractSource", *args: Any, **kwargs: Any) -> Any:
        if self.api_usage.limit_reached():
            raise LimitApiKeyReachedError(
                f"API '{self.__source__}' Limit reached : {self.api_usage.calls_limit}"
            )
        logger.debug(f"API '{self.__source__}' call count: {self.api_usage.calls}")
        return func(self, *args, **kwargs)

    return cast(Callable[..., Any], wrapper)


class AbstractSource(SourceBase, abc.ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    countries: List[Countries]
    exchanges: Exchanges = Field(default_factory=exchanges_factory)
    api_usage: ApiUsage = Field(default_factory=ApiUsage)
    pause: int = 60

    @validate_call(validate_return=True)
    @check_api_limit
    @observability
    def read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        query_ = None
        if query:
            query_ = self.exchanges.get_asset_query(query, self.countries)
            logger.debug(
                f"Reading assets from {type(self).__name__} with {len(query_.symbols.all())} tickers"
            )
        try:
            return self._read_assets(query_)
        except Exception as e:
            logger.error(
                f"Error reading assets from {type(self).__name__}: {e}", exc_info=True
            )
            return Assets()

    @validate_call(validate_return=True)
    @check_api_limit
    @observability
    def read_financials(self, tickers: List[Ticker]) -> List[Financials]:

        tickers = [
            ticker
            for ticker in tickers
            if self.exchanges.ticker_belongs_to_countries(
                ticker, countries=self.countries
            )
        ]

        try:
            logger.info(f"Reading Financials from {type(self).__name__}")
            return self._read_financials([t.symbol for t in tickers])

        except InvalidApiKeyError as e:
            raise e
        except Exception as e:
            logger.error(f"Error reading Financials from {type(self).__name__}: {e}")

        return []

    @validate_call(validate_return=True)
    @check_api_limit
    @observability
    def read_series(
        self, tickers: List[Ticker], type_: SeriesLength, apply_filter: bool = True
    ) -> List[Price]:
        if apply_filter:
            tickers = [
                ticker
                for ticker in tickers
                if self.exchanges.ticker_belongs_to_countries(
                    ticker, countries=self.countries
                )
            ]
        try:
            prices_ = self._read_series([t.symbol for t in tickers], type_)
            return [p for p in prices_ if p.valid()]
        except InvalidApiKeyError as e:
            raise e
        except Exception as e:
            logger.error(f"Error reading prices from {type(self).__name__}: {e}")

        return []

    @abc.abstractmethod
    def _read_financials(self, tickers: List[str]) -> List[Financials]: ...

    @abc.abstractmethod
    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets: ...

    @abc.abstractmethod
    def _read_series(self, tickers: List[str], type: SeriesLength) -> List[Price]: ...

    @abc.abstractmethod
    def set_api_key(self, api_key: str) -> None: ...

    def set_pause(self, value: int) -> None:
        self.pause = value

    def __hash__(self) -> int:
        return hash(self.__source__)


class UrlSource(BaseModel):
    url: str
    results: List[SourceBase] = Field(default_factory=list)
    type_class: Type[SourceBase]
    filters: Optional[List[str]] = None
    renames: Optional[dict[str, str]] = None


class UrlSources(BaseModel):
    equity: UrlSource
    crypto: UrlSource
    currency: Optional[UrlSource] = Field(None)
    etf: UrlSource
    index: Optional[UrlSource] = Field(None)

    def to_assets(self) -> Assets:

        return Assets(
            equities=self.equity.results,
            cryptos=self.crypto.results,
            currencies=self.currency.results if self.currency else [],
            etfs=self.etf.results,
            index=self.index.results if self.index else [],
        )


class DatabaseCsvSource(AbstractSource):
    __url_sources__: UrlSources

    def set_api_key(self, api_key: str) -> None: ...

    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        sources = self.__url_sources__
        for field in sources.model_fields:
            try:
                url_source = getattr(sources, field)
                if url_source is None:
                    continue
                response = requests.get(url_source.url, timeout=10)
                if not response.ok:
                    raise Exception(f"Failed to download data from {url_source.url}")
                data = pd.read_csv(StringIO(response.text))
                url_source.results = self._from_dataframe(
                    data, url_source.type_class, url_source.filters, url_source.renames
                )
            except Exception as e:
                logger.error(f"Failed to download data from {url_source.url}: {e}")
                continue
        return sources.to_assets()

    def _from_dataframe(
        self,
        data: pd.DataFrame,
        databaseclass: Type[DataSourceBase],
        filters: Optional[list[str]] = None,
        renames: Optional[dict[str, str]] = None,
    ) -> List[DataSourceBase]:
        if renames:
            data = data.rename(columns=renames)
        if filters:
            data = data.dropna(subset=filters)

        equities_mapping = [equity.to_dict() for _, equity in data.iterrows()]
        return [databaseclass(**equity_mapping) for equity_mapping in equities_mapping]

    def _read_financials(self, tickers: List[str]) -> List[Financials]:
        return [Financials()]

    def _read_series(self, tickers: List[str], type: str) -> List[Price]:
        return []
