import abc
import logging
from datetime import date
from pathlib import Path
from typing import List, Type, Union, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, validate_call
from sqlmodel import SQLModel

from bearish.exchanges.exchanges import ExchangeQuery
from bearish.macro.commodities import Commodity, CountryCommodityExposure
from bearish.macro.links import CountryAlias, CountryRef, EtfExposure, SectorCommoditySensitivity
from bearish.macro.models import MacroQuery, MacroSeries, MacroTracker, Observation
from bearish.models.sec.insider import InsiderTransaction
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
from bearish.models.sec.filing import Filing
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
    def write_filings(self, filings: List[Filing]) -> None:
        return self._write_filings(filings)

    @validate_call
    def read_filings(self, symbol: str) -> List[Filing]:
        return self._read_filings(symbol)

    def backfill_filed_dates(self) -> None:
        return self._backfill_filed_dates()

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
    def read_sec_companies(self) -> List[str]:
        return self._read_sec_companies()

    @validate_call
    def read_sec_share_data(self, company: str) -> pd.DataFrame:
        return self._read_sec_share_data(company)

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

    # --- macro -----------------------------------------------------------

    @validate_call
    def write_macro_series(self, series: List[MacroSeries]) -> None:
        return self._write_macro_series(series)

    @validate_call
    def read_macro_series(self, query: Optional[MacroQuery] = None) -> List[MacroSeries]:
        return self._read_macro_series(query or MacroQuery())

    @validate_call
    def write_observations(self, observations: List[Observation]) -> int:
        """Store observations point-in-time; returns the number of new vintages written."""
        return self._write_observations(observations)

    @validate_call
    def read_observations(self, query: Optional[MacroQuery] = None) -> List[Observation]:
        return self._read_observations(query or MacroQuery())

    def read_macro_frame(self, query: Optional[MacroQuery] = None) -> pd.DataFrame:
        """Observations as a wide frame: one row per date, one column per series_id."""
        observations = self.read_observations(query)
        if not observations:
            return pd.DataFrame()
        frame = pd.DataFrame([o.model_dump() for o in observations])
        return frame.pivot_table(index="date", columns="series_id", values="value", aggfunc="last").sort_index()

    @validate_call
    def write_macro_trackers(self, trackers: List[MacroTracker]) -> None:
        return self._write_macro_trackers(trackers)

    @validate_call
    def read_macro_trackers(self) -> List[MacroTracker]:
        return self._read_macro_trackers()

    # --- reference & linking tables ---------------------------------------

    @validate_call
    def write_commodities(self, commodities: List[Commodity]) -> None:
        return self._write_commodities(commodities)

    def read_commodities(self) -> List[Commodity]:
        return self._read_commodities()

    @validate_call
    def write_country_exposures(self, exposures: List[CountryCommodityExposure]) -> None:
        return self._write_country_exposures(exposures)

    def read_country_exposures(
        self, country: Optional[str] = None, commodity: Optional[str] = None
    ) -> List[CountryCommodityExposure]:
        return self._read_country_exposures(country=country, commodity=commodity)

    @validate_call
    def write_insider_transactions(self, transactions: List[InsiderTransaction]) -> None:
        return self._write_insider_transactions(transactions)

    def read_insider_transactions(self, symbol: Optional[str] = None) -> List[InsiderTransaction]:
        return self._read_insider_transactions(symbol=symbol)

    @validate_call
    def write_country_references(self, refs: List[CountryRef], aliases: List[CountryAlias]) -> None:
        return self._write_country_references(refs, aliases)

    def read_country_references(self) -> List[CountryRef]:
        return self._read_country_references()

    @validate_call
    def write_sector_sensitivities(self, sensitivities: List[SectorCommoditySensitivity]) -> None:
        return self._write_sector_sensitivities(sensitivities)

    def read_sector_sensitivities(self, commodity: Optional[str] = None) -> List[SectorCommoditySensitivity]:
        return self._read_sector_sensitivities(commodity=commodity)

    @validate_call
    def write_etf_exposures(self, exposures: List[EtfExposure]) -> None:
        return self._write_etf_exposures(exposures)

    def read_etf_exposures(self, symbol: Optional[str] = None, entity: Optional[str] = None) -> List[EtfExposure]:
        return self._read_etf_exposures(symbol=symbol, entity=entity)

    @abc.abstractmethod
    def _write_assets(self, assets: Assets) -> None: ...

    @abc.abstractmethod
    def _write_macro_series(self, series: List[MacroSeries]) -> None: ...

    @abc.abstractmethod
    def _read_macro_series(self, query: MacroQuery) -> List[MacroSeries]: ...

    @abc.abstractmethod
    def _write_observations(self, observations: List[Observation]) -> int: ...

    @abc.abstractmethod
    def _read_observations(self, query: MacroQuery) -> List[Observation]: ...

    @abc.abstractmethod
    def _write_macro_trackers(self, trackers: List[MacroTracker]) -> None: ...

    @abc.abstractmethod
    def _read_macro_trackers(self) -> List[MacroTracker]: ...

    @abc.abstractmethod
    def _write_commodities(self, commodities: List[Commodity]) -> None: ...

    @abc.abstractmethod
    def _read_commodities(self) -> List[Commodity]: ...

    @abc.abstractmethod
    def _write_country_exposures(self, exposures: List[CountryCommodityExposure]) -> None: ...

    @abc.abstractmethod
    def _read_country_exposures(
        self, country: Optional[str] = None, commodity: Optional[str] = None
    ) -> List[CountryCommodityExposure]: ...

    @abc.abstractmethod
    def _write_insider_transactions(self, transactions: List[InsiderTransaction]) -> None: ...

    @abc.abstractmethod
    def _read_insider_transactions(self, symbol: Optional[str] = None) -> List[InsiderTransaction]: ...

    @abc.abstractmethod
    def _write_country_references(self, refs: List[CountryRef], aliases: List[CountryAlias]) -> None: ...

    @abc.abstractmethod
    def _read_country_references(self) -> List[CountryRef]: ...

    @abc.abstractmethod
    def _write_sector_sensitivities(self, sensitivities: List[SectorCommoditySensitivity]) -> None: ...

    @abc.abstractmethod
    def _read_sector_sensitivities(self, commodity: Optional[str] = None) -> List[SectorCommoditySensitivity]: ...

    @abc.abstractmethod
    def _write_etf_exposures(self, exposures: List[EtfExposure]) -> None: ...

    @abc.abstractmethod
    def _read_etf_exposures(
        self, symbol: Optional[str] = None, entity: Optional[str] = None
    ) -> List[EtfExposure]: ...

    @abc.abstractmethod
    def _write_series(
        self, series: List[Price], table: Optional[Type[SQLModel]] = None
    ) -> None: ...

    @abc.abstractmethod
    def _write_sec(self, secs: List[Sec]) -> None: ...

    @abc.abstractmethod
    def _write_filings(self, filings: List[Filing]) -> None: ...

    @abc.abstractmethod
    def _read_filings(self, symbol: str) -> List[Filing]: ...

    @abc.abstractmethod
    def _backfill_filed_dates(self) -> None: ...

    @abc.abstractmethod
    def _read_sec(self, ticker: str) -> List[Sec]: ...

    @abc.abstractmethod
    def _read_sec_shares(self) -> List[SecShareIncrease]: ...
    @abc.abstractmethod
    def _read_sec_companies(self) -> List[str]: ...

    @abc.abstractmethod
    def _read_sec_share_data(self, company: str) -> pd.DataFrame: ...
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
