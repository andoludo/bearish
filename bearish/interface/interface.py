import abc
import logging
from datetime import date
from pathlib import Path
from typing import List, Type, Union, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, validate_call
from sqlmodel import SQLModel

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
from bearish.models.sec.sec import Sec, SecShareIncrease
from bearish.utils.utils import observability


logger = logging.getLogger(__name__)


class BearishDbBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    database_path: Path

    @validate_call
    def write_assets(self, assets: Assets) -> None:
        return self._write_assets(assets)

    @observability
    @validate_call
    def write_series(
        self, series: List[Price], table: Optional[Type[SQLModel]] = None
    ) -> None:
        return self._write_series(series, table=table)

    @validate_call
    def write_sec(self, secs: List[Sec]) -> None:
        return self._write_sec(secs)

    @validate_call
    def read_sec(self, ticker: str) -> List[Sec]:
        return self._read_sec(ticker)

    @validate_call
    def read_sec_shares(self) -> List[SecShareIncrease]:
        return self._read_sec_shares()

    @validate_call
    def write_sec_shares(self, sec_shares: List[SecShareIncrease]) -> None:
        return self._write_sec_shares(sec_shares)

    @observability
    @validate_call
    def write_financials(self, financials: List[Financials]) -> None:
        return self._write_financials(financials)

    @validate_call
    def read_series(
        self, query: AssetQuery, months: int = 1, table: Optional[Type[SQLModel]] = None
    ) -> List[Price]:
        return self._read_series(query, months, table=table)

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

    def read_query(self, query: str) -> pd.DataFrame:
        return self._read_query(query)

    @abc.abstractmethod
    def _write_assets(self, assets: Assets) -> None: ...

    @abc.abstractmethod
    def _write_series(
        self, series: List[Price], table: Optional[Type[SQLModel]] = None
    ) -> None: ...

    @abc.abstractmethod
    def _write_sec(self, secs: List[Sec]) -> None: ...

    @abc.abstractmethod
    def _read_sec(self, ticker: str) -> List[Sec]: ...

    @abc.abstractmethod
    def _read_sec_shares(self) -> List[SecShareIncrease]: ...
    @abc.abstractmethod
    def _write_sec_shares(self, sec_shares: List[SecShareIncrease]) -> None: ...
    @abc.abstractmethod
    def _write_financials(self, financials: List[Financials]) -> None: ...

    @abc.abstractmethod
    def _read_series(
        self, query: AssetQuery, months: int = 1, table: Optional[Type[SQLModel]] = None
    ) -> List[Price]: ...

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
    def _read_query(self, query: str) -> pd.DataFrame: ...

    @abc.abstractmethod
    def read_price_tracker(self, symbol: str) -> Optional[date]: ...
