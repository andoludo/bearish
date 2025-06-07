import abc
import logging
from pathlib import Path
from typing import List, TYPE_CHECKING, Optional, Type, Union

import pandas as pd
from pydantic import BaseModel, ConfigDict, validate_call

from bearish.analysis.view import View
from bearish.exchanges.exchanges import ExchangeQuery
from bearish.models.assets.assets import Assets
from bearish.models.base import (
    TrackerQuery,
    Ticker,
    PriceTracker,
    FinancialsTracker,
    BaseTracker,
)
from bearish.models.financials.base import Financials
from bearish.models.financials.earnings_date import EarningsDate
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery
from bearish.utils.utils import observability

if TYPE_CHECKING:
    from bearish.analysis.analysis import Analysis
logger = logging.getLogger(__name__)


class BearishDbBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    database_path: Path

    @validate_call
    def write_assets(self, assets: Assets) -> None:
        return self._write_assets(assets)

    @observability
    @validate_call
    def write_series(self, series: List[Price]) -> None:
        return self._write_series(series)

    @observability
    @validate_call
    def write_financials(self, financials: List[Financials]) -> None:
        return self._write_financials(financials)

    @validate_call
    def read_series(self, query: AssetQuery, months: int = 1) -> List[Price]:
        return self._read_series(query, months)

    @validate_call
    def read_financials(self, query: AssetQuery) -> Financials:
        return self._read_financials(query)

    def read_earnings_date(self, query: AssetQuery) -> List[EarningsDate]:
        financials = self.read_financials(query)
        return financials.earnings_date

    @validate_call
    def read_assets(self, query: AssetQuery) -> Assets:
        return self._read_assets(query)

    @validate_call
    def read_sources(self) -> List[str]:
        return self._read_sources()

    @validate_call
    def get_tickers(self, exchange_query: ExchangeQuery) -> List[Ticker]:
        return list(set(self._get_tickers(exchange_query)))

    def write_source(self, source: str) -> None:
        return self._write_source(source)

    @validate_call
    def read_tracker(
        self,
        tracker_query: TrackerQuery,
        tracker_type: Union[Type[PriceTracker], Type[FinancialsTracker]],
    ) -> List[Ticker]:
        return self._read_tracker(tracker_query, tracker_type)

    def write_trackers(
        self, trackers: List[FinancialsTracker] | List[PriceTracker]
    ) -> None:
        tracker_type = type(trackers[0])
        return self._write_trackers(trackers, tracker_type)

    def write_analysis(self, analysis: "Analysis") -> None:
        return self._write_analysis(analysis)

    def read_analysis(self, ticker: Ticker) -> Optional["Analysis"]:
        return self._read_analysis(ticker)

    def read_views(self, query: str) -> List[View]:
        return self._read_views(query)

    def read_query(self, query: str) -> pd.DataFrame:
        return self._read_query(query)

    def write_views(self, views: List[View]) -> None:
        if not views:
            logger.warning("No views to write.")
            return
        return self._write_views(views)

    @abc.abstractmethod
    def _write_assets(self, assets: Assets) -> None: ...

    @abc.abstractmethod
    def _write_series(self, series: List[Price]) -> None: ...

    @abc.abstractmethod
    def _write_financials(self, financials: List[Financials]) -> None: ...

    @abc.abstractmethod
    def _read_series(self, query: AssetQuery, months: int = 1) -> List[Price]: ...

    @abc.abstractmethod
    def _read_financials(self, query: AssetQuery) -> Financials: ...

    @abc.abstractmethod
    def _read_assets(self, query: AssetQuery) -> Assets: ...

    @abc.abstractmethod
    def _write_source(self, source: str) -> None: ...

    @abc.abstractmethod
    def _read_sources(self) -> List[str]: ...

    @abc.abstractmethod
    def _read_tracker(
        self,
        tracker_query: TrackerQuery,
        tracker_type: Union[Type[PriceTracker], Type[FinancialsTracker]],
    ) -> List[Ticker]: ...
    @abc.abstractmethod
    def _write_trackers(
        self,
        trackers: List[PriceTracker] | List[FinancialsTracker],
        tracker_type: Type[BaseTracker],
    ) -> None: ...

    @abc.abstractmethod
    def _get_tickers(self, exchange_query: ExchangeQuery) -> List[Ticker]: ...

    @abc.abstractmethod
    def _write_analysis(self, analysis: "Analysis") -> None: ...

    @abc.abstractmethod
    def _read_analysis(self, ticker: Ticker) -> Optional["Analysis"]: ...

    @abc.abstractmethod
    def _read_views(self, query: str) -> List[View]: ...

    @abc.abstractmethod
    def _read_query(self, query: str) -> pd.DataFrame: ...

    @abc.abstractmethod
    def _write_views(self, views: List[View]) -> None: ...
