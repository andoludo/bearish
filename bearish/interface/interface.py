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
from bearish.macro.sectors import SectorAlias
from bearish.models.sec.holdings import Holding13F, Holding13FSummary, Ownership13DG
from bearish.models.sec.insider import InsiderTransaction
from bearish.signals.models import CongressTrade, EventReturn, MarketEvent, PredictionQuote, TickerSignal
from bearish.models.assets.assets import Assets
from bearish.models.assets.snapshots import EquitySnapshot, EtfSnapshot, Snapshots
from bearish.models.assets.index_members import IndexMember
from bearish.models.coverage import Coverage
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

    @validate_call
    def write_snapshots(self, snapshots: Snapshots) -> None:
        return self._write_snapshots(snapshots)

    def read_equity_snapshots(self, symbol: Optional[str] = None) -> List[EquitySnapshot]:
        return self._read_equity_snapshots(symbol=symbol)

    def read_etf_snapshots(self, symbol: Optional[str] = None) -> List[EtfSnapshot]:
        return self._read_etf_snapshots(symbol=symbol)

    @validate_call
    def write_index_members(self, members: List[IndexMember]) -> None:
        return self._write_index_members(members)

    def read_index_members(
        self, index_symbol: Optional[str] = None, symbol: Optional[str] = None, latest: bool = True
    ) -> List[IndexMember]:
        """Members of an index (or the indices a symbol belongs to); ``latest`` keeps only the newest snapshot."""
        return self._read_index_members(index_symbol=index_symbol, symbol=symbol, latest=latest)

    @validate_call
    def write_coverage(self, rows: List[Coverage], replace: bool = True) -> None:
        """Store a coverage census; ``replace`` drops the previous census first (a full run), else upserts."""
        return self._write_coverage(rows, replace=replace)

    def read_coverage(self, symbol: Optional[str] = None, table_name: Optional[str] = None) -> List[Coverage]:
        return self._read_coverage(symbol=symbol, table_name=table_name)

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
    def read_filings(self, symbol: str, forms: Optional[List[str]] = None) -> List[Filing]:
        return self._read_filings(symbol, forms=forms)

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
    def write_holdings13f(self, holdings: List[Holding13F]) -> None:
        return self._write_holdings13f(holdings)

    def read_holdings13f(self, symbol: Optional[str] = None, manager_cik: Optional[str] = None) -> List[Holding13F]:
        return self._read_holdings13f(symbol=symbol, manager_cik=manager_cik)

    @validate_call
    def write_holdings13f_summary(self, summaries: List[Holding13FSummary]) -> None:
        return self._write_holdings13f_summary(summaries)

    def read_holdings13f_summary(
        self, symbol: Optional[str] = None, cusip: Optional[str] = None
    ) -> List[Holding13FSummary]:
        return self._read_holdings13f_summary(symbol=symbol, cusip=cusip)

    @validate_call
    def write_ownership13dg(self, rows: List[Ownership13DG]) -> None:
        return self._write_ownership13dg(rows)

    def read_ownership13dg(self, symbol: Optional[str] = None) -> List[Ownership13DG]:
        return self._read_ownership13dg(symbol=symbol)

    # --- events & signals ---------------------------------------------------

    @validate_call
    def write_events(self, events: List[MarketEvent]) -> None:
        return self._write_events(events)

    def read_events(self, event_type: Optional[str] = None, tag: Optional[str] = None) -> List[MarketEvent]:
        return self._read_events(event_type=event_type, tag=tag)

    @validate_call
    def write_event_returns(self, returns: List[EventReturn]) -> None:
        return self._write_event_returns(returns)

    def read_event_returns(self, event_id: Optional[str] = None, asset: Optional[str] = None) -> List[EventReturn]:
        return self._read_event_returns(event_id=event_id, asset=asset)

    @validate_call
    def write_ticker_signals(self, signals: List[TickerSignal]) -> int:
        """Store signals point-in-time; returns the number of new vintages written."""
        return self._write_ticker_signals(signals)

    def read_ticker_signals(
        self,
        symbols: Optional[List[str]] = None,
        signals: Optional[List[str]] = None,
        signal_prefix: Optional[str] = None,
        start: Optional[date] = None,
        as_of: Optional[date] = None,
    ) -> List[TickerSignal]:
        return self._read_ticker_signals(
            symbols=symbols, signals=signals, signal_prefix=signal_prefix, start=start, as_of=as_of
        )

    def read_ticker_signal_frame(
        self, signals: Optional[List[str]] = None, signal_prefix: Optional[str] = None, as_of: Optional[date] = None
    ) -> pd.DataFrame:
        """Latest-known signal values as a frame indexed by (symbol, date) with one column per signal."""
        rows = self.read_ticker_signals(signals=signals, signal_prefix=signal_prefix, as_of=as_of)
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame([r.model_dump() for r in rows])
        return frame.pivot_table(index=["symbol", "date"], columns="signal", values="value", aggfunc="last")

    @validate_call
    def write_congress_trades(self, trades: List[CongressTrade]) -> None:
        return self._write_congress_trades(trades)

    def read_congress_trades(self, symbol: Optional[str] = None, member: Optional[str] = None) -> List[CongressTrade]:
        return self._read_congress_trades(symbol=symbol, member=member)

    @validate_call
    def write_prediction_quotes(self, quotes: List[PredictionQuote]) -> None:
        return self._write_prediction_quotes(quotes)

    def read_prediction_quotes(
        self, category: Optional[str] = None, platform: Optional[str] = None
    ) -> List[PredictionQuote]:
        return self._read_prediction_quotes(category=category, platform=platform)

    @validate_call
    def write_country_references(self, refs: List[CountryRef], aliases: List[CountryAlias]) -> None:
        return self._write_country_references(refs, aliases)

    def read_country_references(self) -> List[CountryRef]:
        return self._read_country_references()

    @validate_call
    def write_sector_aliases(self, aliases: List[SectorAlias]) -> None:
        return self._write_sector_aliases(aliases)

    def read_sector_aliases(self, level: Optional[str] = None) -> List[SectorAlias]:
        return self._read_sector_aliases(level=level)

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
    def _write_holdings13f(self, holdings: List[Holding13F]) -> None: ...

    @abc.abstractmethod
    def _read_holdings13f(
        self, symbol: Optional[str] = None, manager_cik: Optional[str] = None
    ) -> List[Holding13F]: ...

    @abc.abstractmethod
    def _write_holdings13f_summary(self, summaries: List[Holding13FSummary]) -> None: ...

    @abc.abstractmethod
    def _read_holdings13f_summary(
        self, symbol: Optional[str] = None, cusip: Optional[str] = None
    ) -> List[Holding13FSummary]: ...

    @abc.abstractmethod
    def _write_ownership13dg(self, rows: List[Ownership13DG]) -> None: ...

    @abc.abstractmethod
    def _read_ownership13dg(self, symbol: Optional[str] = None) -> List[Ownership13DG]: ...

    @abc.abstractmethod
    def _write_events(self, events: List[MarketEvent]) -> None: ...

    @abc.abstractmethod
    def _read_events(self, event_type: Optional[str] = None, tag: Optional[str] = None) -> List[MarketEvent]: ...

    @abc.abstractmethod
    def _write_event_returns(self, returns: List[EventReturn]) -> None: ...

    @abc.abstractmethod
    def _read_event_returns(
        self, event_id: Optional[str] = None, asset: Optional[str] = None
    ) -> List[EventReturn]: ...

    @abc.abstractmethod
    def _write_ticker_signals(self, signals: List[TickerSignal]) -> int: ...

    @abc.abstractmethod
    def _read_ticker_signals(
        self,
        symbols: Optional[List[str]] = None,
        signals: Optional[List[str]] = None,
        signal_prefix: Optional[str] = None,
        start: Optional[date] = None,
        as_of: Optional[date] = None,
    ) -> List[TickerSignal]: ...

    @abc.abstractmethod
    def _write_congress_trades(self, trades: List[CongressTrade]) -> None: ...

    @abc.abstractmethod
    def _read_congress_trades(
        self, symbol: Optional[str] = None, member: Optional[str] = None
    ) -> List[CongressTrade]: ...

    @abc.abstractmethod
    def _write_prediction_quotes(self, quotes: List[PredictionQuote]) -> None: ...

    @abc.abstractmethod
    def _read_prediction_quotes(
        self, category: Optional[str] = None, platform: Optional[str] = None
    ) -> List[PredictionQuote]: ...

    @abc.abstractmethod
    def _write_country_references(self, refs: List[CountryRef], aliases: List[CountryAlias]) -> None: ...

    @abc.abstractmethod
    def _read_country_references(self) -> List[CountryRef]: ...

    @abc.abstractmethod
    def _write_sector_aliases(self, aliases: List[SectorAlias]) -> None: ...

    @abc.abstractmethod
    def _read_sector_aliases(self, level: Optional[str] = None) -> List[SectorAlias]: ...

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
    def _write_snapshots(self, snapshots: Snapshots) -> None: ...

    @abc.abstractmethod
    def _read_equity_snapshots(self, symbol: Optional[str] = None) -> List[EquitySnapshot]: ...

    @abc.abstractmethod
    def _read_etf_snapshots(self, symbol: Optional[str] = None) -> List[EtfSnapshot]: ...

    @abc.abstractmethod
    def _write_index_members(self, members: List[IndexMember]) -> None: ...

    @abc.abstractmethod
    def _read_index_members(
        self, index_symbol: Optional[str] = None, symbol: Optional[str] = None, latest: bool = True
    ) -> List[IndexMember]: ...

    @abc.abstractmethod
    def _write_coverage(self, rows: List[Coverage], replace: bool = True) -> None: ...

    @abc.abstractmethod
    def _read_coverage(self, symbol: Optional[str] = None, table_name: Optional[str] = None) -> List[Coverage]: ...

    @abc.abstractmethod
    def _write_series(
        self, series: List[Price], table: Optional[Type[SQLModel]] = None
    ) -> None: ...

    @abc.abstractmethod
    def _write_sec(self, secs: List[Sec]) -> None: ...

    @abc.abstractmethod
    def _write_filings(self, filings: List[Filing]) -> None: ...

    @abc.abstractmethod
    def _read_filings(self, symbol: str, forms: Optional[List[str]] = None) -> List[Filing]: ...

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
