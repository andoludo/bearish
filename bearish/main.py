import datetime
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional, List, Any, Dict, get_args, Annotated, cast, Union, Type, Callable

import pandas as pd
import typer
from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    PrivateAttr,
    validate_call,
    model_validator,
)
from rich.console import Console
from sqlmodel import SQLModel

from bearish.database.crud import BearishDb
from bearish.database.schemas import PriceIndexORM, PriceEtfORM
from bearish.exchanges.exchanges import (
    Countries,
    exchanges_factory,
    ExchangeQuery,
    Exchanges,
)
from bearish.exceptions import InvalidApiKeyError
from bearish.interface.interface import BearishDbBase
from bearish.macro.catalog import select_series
from bearish.macro.countries import iso3_from
from bearish.macro.models import MacroQuery, Observation
from bearish.macro.pipeline import MacroRunReport, fetch_macro, update_macro
from bearish.macro.pipelines.commodities import run_commodities
from bearish.macro.pipelines.linking import run_linking
from bearish.signals.pipelines.conflict import run_conflict_sources, write_conflict_events
from bearish.signals.pipelines.elections import (
    run_midterm_study,
    write_congress_trades,
    write_election_events,
    write_fomc_events,
    write_lobbying,
    write_prediction_quotes,
)
from bearish.signals.sources.congress import HouseTradesResult
from bearish.signals.sources.prediction import ELECTION_QUERIES, GEOPOLITICS_QUERIES
from bearish.signals.pipelines.early_winners import (
    run_screen,
    write_federal_awards,
    write_short_data,
    write_theme_mentions,
)
from bearish.macro.sources import AbstractMacroSource, ArxivSource, default_macro_sources
from bearish.models.api_keys.api_keys import SourceApiKeys
from bearish.models.assets.assets import Assets
from bearish.models.assets.index import PRICE_INDEX
from bearish.models.assets.snapshots import Snapshots
from bearish.coverage import write_coverage
from bearish.fx import write_fx_prices
from bearish.sources.wikipedia_index import fetch_index_members, pages_for
from bearish.models.base import Ticker, TrackerQuery, FinancialsTracker, PriceTracker
from bearish.models.financials.base import Financials
from bearish.models.price.price import Price
from bearish.models.price.prices import Prices
from bearish.models.query.query import AssetQuery, Symbols
from bearish.models.sec.sec import Secs
from bearish.sources.edgar_filings import fetch_filings
from bearish.sources.sec_13f import HoldingsReport, SecurityMapper, list_data_sets, load_holdings, pick_data_sets
from bearish.sources.sec_insiders import fetch_insider_transactions
from bearish.sources.sec_ownership import fetch_ownership
from bearish.sources.sec_xbrl import SecXbrlSource
from bearish.sources.base import AbstractSource
from bearish.sources.financedatabase import FinanceDatabaseSource
from bearish.sources.investpy import InvestPySource
from bearish.sources.tiingo import TiingoSource
from bearish.sources.yahooquery import YahooQuerySource
from bearish.sources.yfinance import yFinanceSource
from bearish.types import SeriesLength, Sources
from bearish.utils.utils import batch

logger = logging.getLogger(__name__)
app = typer.Typer()
console = Console()


class CountryEnum(str, Enum): ...


CountriesEnum = Enum(  # type: ignore
    "CountriesEnum",
    {country: country for country in get_args(Countries)},
    type=CountryEnum,
)


class Filter(BaseModel):
    countries: List[CountriesEnum] = Field(default_factory=list)
    filters: Optional[List[str] | str] = None

    @model_validator(mode="after")
    def _model_validator(self) -> "Filter":
        if self.filters is not None and isinstance(self.filters, str):
            self.filters = [t.strip() for t in self.filters.split(",")]
        return self

    def filter(self, tickers: List[Ticker]) -> List[Ticker]:
        if not self.filters:
            return tickers
        return list({t for t in tickers if t.symbol in self.filters})


def _default_asset_sources() -> List[AbstractSource]:
    return [FinanceDatabaseSource(), InvestPySource()]


def _default_detailed_sources() -> List[AbstractSource]:
    return [yFinanceSource(), YahooQuerySource()]


def _default_financials_sources() -> List[AbstractSource]:
    # SEC XBRL first: as-reported statements with real filing dates for US
    # filers; it yields nothing for other tickers, which fall through to Yahoo.
    return [SecXbrlSource(), yFinanceSource(), YahooQuerySource()]


def _default_price_sources() -> List[AbstractSource]:
    return [yFinanceSource(), YahooQuerySource(), TiingoSource()]


class Bearish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: Path
    auto_migration: bool = True
    batch_size: int = Field(default=100)
    pause: int = Field(default=60)
    api_keys: SourceApiKeys = Field(default_factory=SourceApiKeys)
    _bearish_db: BearishDbBase = PrivateAttr()
    exchanges: Exchanges = Field(default_factory=exchanges_factory)
    asset_sources: List[AbstractSource] = Field(default_factory=_default_asset_sources)
    detailed_asset_sources: List[AbstractSource] = Field(default_factory=_default_detailed_sources)
    financials_sources: List[AbstractSource] = Field(default_factory=_default_financials_sources)
    price_sources: List[AbstractSource] = Field(default_factory=_default_price_sources)
    macro_sources: List[AbstractMacroSource] = Field(default_factory=default_macro_sources)

    def model_post_init(self, __context: Any) -> None:
        self._bearish_db = BearishDb(
            database_path=self.path, auto_migration=self.auto_migration
        )
        for source in self._all_sources():
            source.set_pause(self.pause)
            self._set_api_key_or_drop(source)
        for macro_source in list(self.macro_sources):
            self._set_macro_api_key_or_drop(macro_source)

    def _set_macro_api_key_or_drop(self, source: AbstractMacroSource) -> None:
        """Macro providers read ``<SOURCE>_API_KEY`` or the key file; keyless ones ignore it."""
        name = source.__source__
        api_key = self.api_keys.keys.get(name, os.environ.get(f"{name.upper()}_API_KEY"))
        try:
            source.set_api_key(api_key)
        except InvalidApiKeyError as e:
            logger.warning(f"{e}. {name} will be skipped")
            self.macro_sources.remove(source)

    def _all_sources(self) -> set[AbstractSource]:
        return set(
            self.financials_sources
            + self.price_sources
            + self.asset_sources
            + self.detailed_asset_sources
        )

    def _source_lists(self) -> List[List[AbstractSource]]:
        return [
            self.financials_sources,
            self.price_sources,
            self.asset_sources,
            self.detailed_asset_sources,
        ]

    def _set_api_key_or_drop(self, source: AbstractSource) -> None:
        """Configure the source's API key; drop the source everywhere if invalid."""
        api_key = self.api_keys.keys.get(
            source.__source__, os.environ.get(source.__source__.upper())
        )
        try:
            source.set_api_key(api_key)
        except Exception as e:
            logger.error(
                f"Invalid API key for {source.__source__}: {e}. It will be removed from sources"
            )
            for sources in self._source_lists():
                if source in sources:
                    sources.remove(source)

    def set_batch_size(self, batch_size: int) -> None:
        self.batch_size = batch_size

    def set_pause(self, pause: int) -> None:
        for source in self._all_sources():
            source.set_pause(pause)

    def get_asset_sources(self) -> List[Sources]:
        return [source.__source__ for source in self.asset_sources]

    def get_detailed_asset_sources(self) -> List[Sources]:
        return [source.__source__ for source in self.detailed_asset_sources]

    def write_assets(self, query: Optional[AssetQuery] = None) -> None:
        existing_sources = self._bearish_db.read_sources()
        asset_sources = [
            asset_source
            for asset_source in self.asset_sources
            if asset_source.__source__ not in existing_sources
        ]
        logger.debug(f"Found asset sources: {[s.__source__ for s in asset_sources]}")
        return self._write_base_assets(asset_sources, query)

    def write_detailed_assets(self, query: Optional[AssetQuery] = None) -> None:
        return self._write_base_assets(
            self.detailed_asset_sources, query, use_all_sources=False
        )

    def _write_base_assets(
        self,
        asset_sources: List[AbstractSource],
        query: Optional[AssetQuery] = None,
        use_all_sources: bool = True,
    ) -> None:

        if query:
            cached_assets = self.read_assets(AssetQuery.model_validate(query))
            query.update_symbols(cached_assets)
        for source in asset_sources:

            logger.info(f"Fetching assets from source {type(source).__name__}")
            assets_ = source.read_assets(query)
            if assets_.is_empty():
                logger.warning(f"No assets found from {type(source).__name__}")
                continue
            logger.debug(
                f"writing assets from {type(source).__name__}. Number of symbols: {len(assets_.symbols())}"
            )
            self._bearish_db.write_assets(assets_)
            snapshots = Snapshots.from_assets(assets_)
            if not snapshots.is_empty():
                self._bearish_db.write_snapshots(snapshots)
            self._bearish_db.write_source(source.__source__)
            if use_all_sources:
                continue
            if not assets_.failed_query.symbols:
                break
            else:
                query = AssetQuery(
                    symbols=Symbols(equities=assets_.failed_query.symbols)  # type: ignore
                )

    def read_assets(self, assets_query: AssetQuery) -> Assets:
        return self._bearish_db.read_assets(assets_query)

    def read_financials(self, assets_query: AssetQuery) -> Financials:
        return self._bearish_db.read_financials(assets_query)

    def read_series(
        self,
        assets_query: AssetQuery,
        months: int = 1,
        table: Optional[Type[SQLModel]] = None,
    ) -> List[Price]:
        return self._bearish_db.read_series(assets_query, months=months, table=table)

    def _get_tracked_tickers(
        self,
        tracker_query: TrackerQuery,
        tracker_type: Union[Type[PriceTracker], Type[FinancialsTracker]],
    ) -> List[Ticker]:
        return self._bearish_db.read_tracker(tracker_query, tracker_type)

    def get_tickers_without_financials(self, tickers: List[Ticker]) -> List[Ticker]:
        tracked_tickers = self._get_tracked_tickers(TrackerQuery(), FinancialsTracker)
        return [t for t in tickers if t not in tracked_tickers]

    def get_tickers_without_price(self, tickers: List[Ticker]) -> List[Ticker]:
        return [
            t
            for t in tickers
            if t not in self._get_tracked_tickers(TrackerQuery(), PriceTracker)
        ]

    def get_ticker_with_price(self) -> List[Ticker]:
        return self._get_tracked_tickers(TrackerQuery(), PriceTracker)

    def write_many_financials(self, tickers: List[Ticker]) -> None:
        """Fetch statements per batch, falling through the financials sources per ticker.

        The first source is asked for the whole batch; tickers it returns
        nothing for (e.g. non-US names when SEC XBRL is first) are passed to
        the next source, so each ticker is filled by the first provider that
        covers it.
        """
        logger.warning(f"Found tickers without financials: {len(tickers)}")
        for chunk in batch(tickers, size=self.batch_size):
            remaining = list(chunk)
            for source in self.financials_sources:
                if not remaining:
                    break
                logger.debug(f"getting financial data for {len(remaining)} tickers from {source.__source__}")
                try:
                    financials_ = source.read_financials(remaining)
                except Exception as e:  # keep going: one failed batch must not stop the run
                    logger.error(f"Error reading data using {source.__source__}: {e}")
                    continue
                covered = self._symbols_with_financials(financials_)
                if not covered:
                    continue
                self._bearish_db.write_financials(financials_)
                self._bearish_db.write_trackers(
                    [
                        FinancialsTracker(symbol=t.symbol, source=source.__source__, exchange=t.exchange)
                        for t in remaining
                        if t.symbol in covered
                    ]
                )
                remaining = [t for t in remaining if t.symbol not in covered]
            if remaining:
                logger.warning(f"No financial data found for {[t.symbol for t in remaining]}")

    @staticmethod
    def _symbols_with_financials(financials: List[Financials]) -> set[str]:
        return {
            item.symbol
            for financial in financials
            for field in type(financial).model_fields
            for item in getattr(financial, field)
        }

    @validate_call
    def write_many_series(
        self,
        tickers: List[Ticker],
        type: SeriesLength,
        apply_filter: bool = True,
        table: Optional[Type[SQLModel]] = None,
        track: bool = True,
    ) -> None:
        chunks = batch(tickers, self.batch_size)
        source = self.price_sources[0]
        for chunk in chunks:
            logger.debug(f"getting financial data for {len(chunk)} tickers")
            try:
                series_ = source.read_series(chunk, type, apply_filter=apply_filter)
            except Exception as e:  # keep going: one failed batch must not stop the run
                logger.error(f"Error reading series: {e}")
                continue
            if series_:
                self._bearish_db.write_series(series_, table=table)
                if track:
                    prices_date = Prices(prices=series_)
                    self._bearish_db.write_trackers(
                        [
                            PriceTracker(
                                symbol=t.symbol,
                                source=source.__source__,
                                exchange=t.exchange,
                                date=prices_date.ticker_date(t.symbol),
                            )
                            for t in chunk
                        ]
                    )

    def read_sources(self) -> List[str]:
        return self._bearish_db.read_sources()

    def get_tickers(self, exchange_query: ExchangeQuery) -> List[Ticker]:
        return self._bearish_db.get_tickers(exchange_query)

    def get_detailed_tickers(self, filter: Filter) -> None:
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries), self.get_asset_sources()
            )
        )

        tickers = filter.filter(tickers)
        asset_query = AssetQuery(symbols=Symbols(equities=tickers))  # type: ignore
        self.write_detailed_assets(asset_query)

    def get_financials(self, filter: Filter) -> None:
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries),
                self.get_detailed_asset_sources(),
            )
        )
        tickers = filter.filter(tickers)
        logger.debug(f"Found tickers: {[t.symbol for t in tickers]}")
        self.write_many_financials(tickers)

    def get_filings(self, filter: Filter) -> None:
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries),
                self.get_detailed_asset_sources(),
            )
        )
        tickers = filter.filter(tickers)
        filings = fetch_filings([t.symbol for t in tickers])
        logger.debug(f"Fetched {len(filings)} EDGAR filings")
        self._bearish_db.write_filings(filings)
        self._bearish_db.backfill_filed_dates()

    def _filtered_symbols(self, filter: Filter) -> List[str]:
        """Symbols of the stored tickers matching a country / symbol filter."""
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries),
                self.get_detailed_asset_sources(),
            )
        )
        return sorted({t.symbol for t in filter.filter(tickers)})

    def get_theme_mentions(
        self,
        filter: Optional[Filter] = None,
        themes: Optional[List[str]] = None,
        start: Optional[datetime.date] = None,
        adoption: bool = False,
    ) -> Dict[str, int]:
        """Theme mentions in SEC filings per company and market-wide; optionally arXiv adoption series."""
        symbols = self._filtered_symbols(filter) if filter else None
        counts = write_theme_mentions(self._bearish_db, symbols=symbols, themes=themes, start=start)
        if adoption:
            series = select_series(MacroQuery(concepts=["ADOPTION_PAPERS"]))
            report = fetch_macro(self._bearish_db, [ArxivSource()], series, start=start)
            counts["adoption_vintages"] = report.vintages_written
        return counts

    def write_events(self, fomc_start_year: int = 1994) -> Dict[str, int]:
        """Curated elections and conflicts plus the FOMC calendar into the marketevent table."""
        return {
            "elections": write_election_events(self._bearish_db),
            "conflicts": write_conflict_events(self._bearish_db),
            "fomc": write_fomc_events(self._bearish_db, start_year=fomc_start_year),
        }

    def midterm_study(self, assets: Optional[List[str]] = None, price_source: str = "yfinance") -> pd.DataFrame:
        """Returns around every US midterm since 1946, stored in eventreturn and summarised by group."""
        kwargs: Dict[str, Any] = {"price_source": price_source}
        if assets:
            kwargs["assets"] = assets
        return run_midterm_study(self._bearish_db, **kwargs)

    def predictions(self, category: str = "all") -> int:
        """Snapshot Polymarket/Kalshi odds for elections and/or geopolitics."""
        queries = {
            "election": ELECTION_QUERIES,
            "geopolitics": GEOPOLITICS_QUERIES,
            "all": ELECTION_QUERIES + GEOPOLITICS_QUERIES,
        }[category]
        return write_prediction_quotes(self._bearish_db, queries=queries)

    def congress_trades(
        self, year: Optional[int] = None, since: Optional[datetime.date] = None, max_filings: int = 200
    ) -> HouseTradesResult:
        return write_congress_trades(self._bearish_db, year=year, since=since, max_filings=max_filings)

    def get_lobbying(self, filter: Filter, years: List[int]) -> int:
        return write_lobbying(self._bearish_db, self._filtered_symbols(filter), years)

    def get_short_data(self, filter: Filter, days: int = 20, history_days: int = 400) -> Dict[str, int]:
        return write_short_data(self._bearish_db, self._filtered_symbols(filter), days=days, history_days=history_days)

    def get_federal_awards(self, filter: Filter, years: int = 2) -> int:
        return write_federal_awards(self._bearish_db, self._filtered_symbols(filter), years=years)

    def screen(
        self,
        as_of: Optional[datetime.date] = None,
        universe: Optional[List[str]] = None,
        min_market_cap: Optional[float] = None,
        max_market_cap: Optional[float] = None,
        top: Optional[int] = None,
    ) -> pd.DataFrame:
        """Early-winner screen using only data public on ``as_of``."""
        return run_screen(
            self._bearish_db,
            as_of=as_of,
            universe=universe,
            min_market_cap=min_market_cap,
            max_market_cap=max_market_cap,
            top=top,
        )

    def get_insiders(
        self,
        filter: Filter,
        since: Optional[datetime.date] = None,
        max_filings: int = 50,
    ) -> int:
        """Fetch SEC Form 4 insider transactions for the filtered tickers; returns rows written."""
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries),
                self.get_detailed_asset_sources(),
            )
        )
        tickers = filter.filter(tickers)
        transactions = fetch_insider_transactions(
            [t.symbol for t in tickers], since=since, max_filings=max_filings
        )
        logger.debug(f"Fetched {len(transactions)} insider transactions")
        self._bearish_db.write_insider_transactions(transactions)
        return len(transactions)

    def get_holdings(
        self,
        windows: int = 2,
        managers: Optional[List[str]] = None,
        top_managers: int = 300,
        data_sets: Optional[List[str]] = None,
    ) -> HoldingsReport:
        """Load Form 13F institutional holdings from the SEC bulk data sets.

        ``windows`` newest filing windows are loaded (two give the latest
        quarter plus the one before it, which is what the per-security flows
        need). Per-manager rows are kept for ``managers`` plus the
        ``top_managers`` largest filers; summaries cover every security.
        """
        available = list_data_sets()
        refs, unknown = pick_data_sets(available, windows, data_sets)
        if unknown:
            raise ValueError(f"Unknown 13F data sets: {unknown}. Available: {[r.name for r in available[:8]]}...")
        return load_holdings(
            self._bearish_db,
            refs,
            managers=managers,
            top_n=top_managers,
            mapper=SecurityMapper.from_db(self._bearish_db),
        )

    def get_ownership(
        self,
        filter: Filter,
        since: Optional[datetime.date] = None,
        max_filings: int = 100,
    ) -> int:
        """Fetch Schedule 13D/13G beneficial-ownership filings (>= 5 % holders) for the filtered tickers."""
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries),
                self.get_detailed_asset_sources(),
            )
        )
        tickers = filter.filter(tickers)
        rows = fetch_ownership([t.symbol for t in tickers], since=since, max_filings=max_filings)
        logger.debug(f"Fetched {len(rows)} Schedule 13D/13G rows")
        self._bearish_db.write_ownership13dg(rows)
        return len(rows)

    def get_prices(self, filter: Filter) -> None:
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries),
                self.get_detailed_asset_sources(),
            )
        )
        tickers = filter.filter(tickers)
        self.write_many_series(tickers, "max")

    def get_prices_index(self, series_length: SeriesLength = "max") -> None:
        asset_query = AssetQuery(symbols=Symbols(index=PRICE_INDEX))  # type: ignore
        assets = self.read_assets(asset_query)
        self.write_many_series(
            [Ticker(symbol=i.symbol) for i in assets.index],
            series_length,
            apply_filter=False,
            table=PriceIndexORM,
            track=False,
        )

    def get_prices_etf(
        self,
        series_length: SeriesLength = "max",
        limit: Optional[int] = None,
        exchanges: Optional[List[str]] = None,
    ) -> List[str]:
        """Fetch ETF prices; ``exchanges`` restricts to listings on those exchange codes.

        Many ETF rows are secondary listings (Berlin, Munich, ...) with no price
        history at the providers, so callers interested in liquid data pass the
        primary exchanges (e.g. ``["NYSE", "PCX", "NMS"]``).
        """
        query_etfs = "SELECT DISTINCT symbol FROM etf"
        if exchanges:
            exchange_list = ",".join(f"'{exchange}'" for exchange in exchanges)
            query_etfs += f" WHERE exchange IN ({exchange_list})"
        query_etfs += " ORDER BY symbol;"
        etf_symbols = self._bearish_db.read_query(query_etfs)["symbol"].tolist()
        if limit:
            etf_symbols = etf_symbols[:limit]
        self.write_many_series(
            [Ticker(symbol=symbol) for symbol in etf_symbols],
            series_length,
            apply_filter=False,
            table=PriceEtfORM,
            track=False,
        )
        return etf_symbols

    def get_prices_fx(
        self, series_length: SeriesLength = "max", currencies: Optional[List[str]] = None
    ) -> List[str]:
        """Daily USD<CCY>=X quotes into ``pricecurrency`` for every currency in use (plus the core set)."""
        return write_fx_prices(self, series_length=series_length, currencies=currencies)

    def get_index_members(self, indices: Optional[List[str]] = None) -> int:
        """Index constituent snapshots (Wikipedia) into ``indexmember``; returns rows written."""
        members = fetch_index_members(pages_for(indices))
        self._bearish_db.write_index_members(members)
        return len(members)

    def coverage(self, symbols: Optional[List[str]] = None) -> int:
        """Refresh the per-symbol data census in ``coverage``; returns rows written."""
        return write_coverage(self._bearish_db, symbols=symbols)

    # --- macro -------------------------------------------------------------

    @staticmethod
    def _macro_query(
        countries: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        concepts: Optional[List[str]] = None,
    ) -> MacroQuery:
        """Build a catalog query; country names/ISO-2 are accepted and mapped to ISO-3."""
        entities: List[str] = []
        for country in countries or []:
            iso3 = iso3_from(country) or country.upper()
            entities.append(iso3)
        return MacroQuery(
            entities=entities,
            categories=categories or [],
            sources=sources or [],
            concepts=concepts or [],
        )

    def write_macro(
        self,
        query: Optional[MacroQuery] = None,
        start: Optional[datetime.date] = None,
    ) -> MacroRunReport:
        """Fetch every catalog series matching ``query`` (all priority series when None)."""
        series = select_series(query)
        if query and query.entities:
            # Regional/global series are always relevant when a country is asked for.
            series += [
                s
                for s in select_series(query.model_copy(update={"entities": []}))
                if s.entity_type in {"region", "global"} and s not in series
            ]
        return fetch_macro(self._bearish_db, self.macro_sources, series, start=start)

    def update_macro(self, query: Optional[MacroQuery] = None, delay: int = 1) -> MacroRunReport:
        return update_macro(self._bearish_db, self.macro_sources, query=query, delay_days=delay)

    def read_macro(self, query: Optional[MacroQuery] = None) -> pd.DataFrame:
        return self._bearish_db.read_macro_frame(query)

    def read_observations(self, query: Optional[MacroQuery] = None) -> List[Observation]:
        return self._bearish_db.read_observations(query)

    def commodities(  # noqa: PLR0913
        self,
        year: Optional[int] = None,
        series_length: SeriesLength = "max",
        prices: bool = True,
        observations: bool = True,
        exposures: bool = True,
        pause: float = 6.0,
    ) -> None:
        """Commodity reference, futures prices, Pink Sheet / COT observations and trade exposure."""
        run_commodities(
            self,
            year=year,
            series_length=series_length,
            prices=prices,
            observations=observations,
            exposures=exposures,
            pause=pause,
        )

    def conflicts(self, start: Optional[datetime.date] = None) -> MacroRunReport:
        """Chokepoint transits, GDELT conflict/tone, OFAC designations, SIPRI spending and conflict events."""
        return run_conflict_sources(self, start=start)

    def link(self) -> Dict[str, int]:
        """Populate the linking tables: country references, sector-commodity sensitivities, ETF exposure."""
        return run_linking(self._bearish_db)

    def _update(
        self,
        tracker_type: Union[Type[PriceTracker], Type[FinancialsTracker]],
        write_function: Callable[[List[Ticker]], None],
        symbols: Optional[List[str]] = None,
        reference_date: Optional[datetime.date] = None,
        delay: int = 5,
    ) -> None:
        reference_date = reference_date or datetime.date.today()
        tickers = self._get_tracked_tickers(
            TrackerQuery(reference_date=reference_date, delay=delay), tracker_type
        )
        if symbols is not None:
            tickers = [t for t in tickers if t.symbol in symbols]
        write_function(tickers)

    def update_prices(  # noqa: PLR0913
        self,
        symbols: Optional[List[str]] = None,
        reference_date: Optional[datetime.date] = None,
        delay: int = 1,
        series_length: SeriesLength = "1mo",
        batch_size: int = 100,
        pause: int = 60,
    ) -> None:
        def write_function(tickers: List[Ticker]) -> None:
            logger.debug(f"Updating prices for {len(tickers)} tickers")
            self.write_many_series(tickers, series_length, apply_filter=False)

        self.set_batch_size(batch_size)
        self.set_pause(pause)
        self._update(
            PriceTracker,
            write_function,
            symbols=symbols,
            reference_date=reference_date,
            delay=delay,
        )

    def update_financials(
        self,
        symbols: Optional[List[str]] = None,
        reference_date: Optional[datetime.date] = None,
        delay: int = 20,
    ) -> None:
        def write_function(tickers: List[Ticker]) -> None:
            self.write_many_financials(tickers)

        self._update(
            FinancialsTracker,
            write_function,
            symbols=symbols,
            reference_date=reference_date,
            delay=delay,
        )


def _bearish_from(path: Path, api_keys: Optional[Path]) -> Bearish:
    """Build a Bearish instance for a CLI command from a database path and key file."""
    return Bearish(path=path, api_keys=SourceApiKeys.from_file(api_keys))


@app.command()
def run(  # noqa: PLR0913
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
    etf: bool = True,
    index: bool = True,
    fx: bool = True,
    sec: bool = True,
    financials: bool = True,
) -> None:
    console.log(
        f"Fetching assets to database for countries: {countries}, with filters: {filters}",
    )
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Fetching Tickers data..."):
        bearish.write_assets()
        filter = Filter(countries=countries, filters=filters)
        bearish.get_detailed_tickers(filter)
        console.log("[bold][red]Tickers downloaded!")
    with console.status("[bold green]Fetching Price data..."):
        bearish.get_prices(filter)
        console.log("[bold][red]Price downloaded!")
    if index:
        with console.status("[bold green]Fetching Price index..."):
            bearish.get_prices_index()
            console.log("[bold][red]Price index downloaded!")
        with console.status("[bold green]Fetching index constituents..."):
            bearish.get_index_members()
            console.log("[bold][red]Index constituents downloaded!")
    if etf:
        with console.status("[bold green]Fetching Etf price..."):
            bearish.get_prices_etf()
            console.log("[bold][red]Price etf downloaded!")
    if fx:
        with console.status("[bold green]Fetching FX rates..."):
            bearish.get_prices_fx()
            console.log("[bold][red]FX rates downloaded!")
    if sec:
        with console.status("[bold green]Fetching SEC data..."):
            Secs.upload(bearish._bearish_db)  # type: ignore
            console.log("[bold][red]SEC data downloaded!")
    if financials:
        with console.status("[bold green]Fetching Financial data..."):
            bearish.get_financials(filter)
            console.log("[bold][red]Financial downloaded!")
    with console.status("[bold green]Taking the coverage census..."):
        bearish.coverage()
        console.log("[bold][red]Coverage updated!")


@app.command()
def tickers(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
    skip_base_tickers: Optional[bool] = False,
) -> None:
    with console.status("[bold green]Fetching Tickers data..."):
        logger.info(
            f"Writing assets to database for countries: {countries}",
        )
        bearish = _bearish_from(path, api_keys)
        if not skip_base_tickers:
            console.log("[green]Fetching base Tickers[/green]")
            bearish.write_assets()
        filter = Filter(countries=countries, filters=filters)
        console.log("[green]Fetching detailed Tickers[/green]")
        bearish.get_detailed_tickers(filter)
        console.log("[bold][red]Tickers downloaded!")


@app.command()
def financials(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
) -> None:
    with console.status("[bold green]Fetching Financial data..."):
        bearish = _bearish_from(path, api_keys)
        filter = Filter(countries=countries, filters=filters)
        bearish.get_financials(filter)
        console.log("[bold][red]Financial data downloaded!")


@app.command()
def prices(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
) -> None:
    with console.status("[bold green]Fetching Price data..."):
        bearish = _bearish_from(path, api_keys)
        filter = Filter(countries=countries, filters=filters)
        bearish.get_prices(filter)
        console.log("[bold][red]Price data downloaded!")


@app.command()
def filings(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
) -> None:
    with console.status("[bold green]Fetching EDGAR filings..."):
        bearish = _bearish_from(path, api_keys)
        filter = Filter(countries=countries, filters=filters)
        bearish.get_filings(filter)
        console.log("[bold][red]Filings downloaded!")


@app.command()
def insiders(  # noqa: PLR0913
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    since: Annotated[Optional[datetime.datetime], typer.Option(help="Only filings filed on/after this date")] = None,
    max_filings: Annotated[int, typer.Option(help="Newest Form 4 filings fetched per symbol")] = 50,
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch SEC Form 4 insider transactions (US filers) into the insidertransaction table."""
    with console.status("[bold green]Fetching insider transactions..."):
        bearish = _bearish_from(path, api_keys)
        filter = Filter(countries=countries, filters=filters)
        written = bearish.get_insiders(filter, since=since.date() if since else None, max_filings=max_filings)
        console.log(f"[bold][red]{written} insider transactions downloaded!")


@app.command()
def holdings(  # noqa: PLR0913
    path: Path,
    windows: Annotated[int, typer.Option(help="Newest 13F filing windows to load (2 = latest quarter + prior)")] = 2,
    managers: Annotated[Optional[List[str]], typer.Option(help="Manager CIKs always stored")] = None,
    top_managers: Annotated[int, typer.Option(help="Also store the N largest managers by reported value")] = 300,
    data_set: Annotated[Optional[List[str]], typer.Option(help="Explicit data set names instead of --windows")] = None,
    api_keys: Optional[Path] = None,
) -> None:
    """Load Form 13F institutional holdings (per manager) and per-security holder flows from the SEC bulk data sets."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Loading 13F data sets (about 100 MB each)..."):
        report = bearish.get_holdings(windows=windows, managers=managers, top_managers=top_managers, data_sets=data_set)
    console.log(
        f"[bold][red]13F loaded! {report.holdings_written} positions for {report.managers_stored} managers, "
        f"{report.summaries_written} security summaries ({report.symbols_resolved} with a symbol), "
        f"periods {report.periods}"
    )


@app.command()
def ownership(  # noqa: PLR0913
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    since: Annotated[Optional[datetime.datetime], typer.Option(help="Filed on/after this date")] = None,
    max_filings: Annotated[int, typer.Option(help="Newest Schedule 13D/13G filings fetched per symbol")] = 100,
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch Schedule 13D/13G filings (holders crossing 5 %, activists) into the ownership13dg table."""
    with console.status("[bold green]Fetching Schedule 13D/13G filings..."):
        bearish = _bearish_from(path, api_keys)
        filter = Filter(countries=countries, filters=filters)
        written = bearish.get_ownership(filter, since=since.date() if since else None, max_filings=max_filings)
        console.log(f"[bold][red]{written} beneficial-ownership rows downloaded!")


@app.command()
def sec(
    path: Path,
    api_keys: Optional[Path] = None,
) -> None:
    with console.status("[bold green]Fetching SEC data..."):
        bearish = _bearish_from(path, api_keys)
        Secs.upload(bearish._bearish_db)  # type: ignore


@app.command()
def macro(  # noqa: PLR0913
    path: Path,
    countries: Annotated[
        Optional[List[str]],
        typer.Argument(help="ISO-3/ISO-2 codes or names; default: every priority country"),
    ] = None,
    categories: Annotated[Optional[List[str]], typer.Option(help="growth, inflation, rates, credit, ...")] = None,
    sources: Annotated[Optional[List[str]], typer.Option(help="Restrict to providers, e.g. OECD FRED")] = None,
    concepts: Annotated[Optional[List[str]], typer.Option(help="Restrict to concepts, e.g. CPI_YOY")] = None,
    start: Annotated[Optional[datetime.datetime], typer.Option(help="Earliest observation date")] = None,
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch macro-economic series (growth, inflation, rates, credit, sentiment) point-in-time."""
    bearish = _bearish_from(path, api_keys)
    query = Bearish._macro_query(countries, categories, sources, concepts)
    with console.status("[bold green]Fetching macro data..."):
        report = bearish.write_macro(query, start=start.date() if start else None)
    console.log(
        f"[bold][red]Macro downloaded! {report.series_with_data}/{report.series_requested} series, "
        f"{report.vintages_written} new vintages ({report.sources})"
    )


@app.command()
def commodities(  # noqa: PLR0913
    path: Path,
    year: Annotated[Optional[int], typer.Option(help="Comtrade reference year (default: two years ago)")] = None,
    series_length: str = "max",
    prices: bool = True,
    observations: bool = True,
    exposures: Annotated[bool, typer.Option(help="Country trade exposure from Comtrade (slow, rate limited)")] = True,
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch commodity prices, monthly Pink Sheet history, CFTC positioning and country trade exposure."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Fetching commodity data..."):
        bearish.commodities(
            year=year,
            series_length=series_length,  # type: ignore[arg-type]
            prices=prices,
            observations=observations,
            exposures=exposures,
        )
    console.log("[bold][red]Commodity data downloaded!")


@app.command()
def coverage(
    path: Path,
    symbols: Annotated[Optional[List[str]], typer.Argument(help="Restrict the census to these symbols")] = None,
    api_keys: Optional[Path] = None,
) -> None:
    """Summarise, per symbol and table, the first / last date and row count into the coverage table."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Taking the coverage census..."):
        written = bearish.coverage(symbols)
    console.log(f"[bold][red]Coverage census written: {written} rows!")


@app.command()
def members(
    path: Path,
    indices: Annotated[
        Optional[List[str]], typer.Argument(help="Index symbols, e.g. ^GSPC ^GDAXI; default: all")
    ] = None,
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch index constituents (S&P 500, Nasdaq-100, DAX, CAC 40, BEL 20, FTSE 100, ...) into indexmember."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Fetching index constituents..."):
        written = bearish.get_index_members(indices)
    console.log(f"[bold][red]{written} index constituents downloaded!")


@app.command()
def fx(
    path: Path,
    currencies: Annotated[Optional[List[str]], typer.Argument(help="ISO codes; default: every currency in use")] = None,
    series_length: str = "max",
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch daily USD<CCY>=X exchange rates into the pricecurrency table (fxrate view)."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Fetching FX rates..."):
        symbols = bearish.get_prices_fx(series_length=series_length, currencies=currencies)  # type: ignore[arg-type]
    console.log(f"[bold][red]FX rates downloaded for {len(symbols)} pairs!")


@app.command()
def conflicts(
    path: Path,
    start: Annotated[Optional[datetime.datetime], typer.Option(help="Earliest observation (GDELT: 120 days)")] = None,
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch conflict and supply-chain shock signals and the curated conflict / sanctions-wave events."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Fetching conflict signals..."):
        report = bearish.conflicts(start=start.date() if start else None)
    console.log(
        f"[bold][red]Conflict signals downloaded! {report.series_with_data}/{report.series_requested} series, "
        f"{report.vintages_written} new vintages ({report.sources})"
    )


@app.command()
def themes(  # noqa: PLR0913
    path: Path,
    countries: Annotated[Optional[List[CountriesEnum]], typer.Argument()] = None,
    filters: Optional[str] = None,
    theme: Annotated[Optional[List[str]], typer.Option(help="Theme keys, e.g. ai_accelerator (default: all)")] = None,
    start: Annotated[Optional[datetime.datetime], typer.Option(help="First quarter (default: two years ago)")] = None,
    adoption: Annotated[bool, typer.Option(help="Also fetch arXiv paper counts per theme (slow)")] = False,
    api_keys: Optional[Path] = None,
) -> None:
    """Count technology-theme mentions in SEC filings, per company and market-wide."""
    bearish = _bearish_from(path, api_keys)
    filter = Filter(countries=countries, filters=filters) if countries else None
    with console.status("[bold green]Searching EDGAR filings for themes..."):
        counts = bearish.get_theme_mentions(
            filter, themes=theme, start=start.date() if start else None, adoption=adoption
        )
    console.log(f"[bold][red]Theme mentions written! {counts}")


@app.command()
def shorts(  # noqa: PLR0913
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    days: Annotated[int, typer.Option(help="Trading days of FINRA daily short volume")] = 20,
    history_days: Annotated[int, typer.Option(help="Days of short-interest history")] = 400,
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch FINRA short interest and daily short-volume ratios for the filtered tickers."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Fetching FINRA short data..."):
        counts = bearish.get_short_data(
            Filter(countries=countries, filters=filters), days=days, history_days=history_days
        )
    console.log(f"[bold][red]Short data written! {counts}")


@app.command()
def awards(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    years: Annotated[int, typer.Option(help="Years of USAspending history")] = 2,
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch quarterly federal contract awards per company from USAspending."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Fetching federal awards..."):
        written = bearish.get_federal_awards(Filter(countries=countries, filters=filters), years=years)
    console.log(f"[bold][red]{written} federal-award values written!")


@app.command()
def screen(  # noqa: PLR0913
    path: Path,
    as_of: Annotated[Optional[datetime.datetime], typer.Option(help="Screen date (default: today)")] = None,
    universe: Annotated[Optional[List[str]], typer.Option(help="Restrict to these symbols")] = None,
    min_market_cap: Optional[float] = None,
    max_market_cap: Optional[float] = None,
    top: Annotated[int, typer.Option(help="Rows to show")] = 25,
    output: Annotated[Optional[Path], typer.Option(help="Write the full ranked table to this CSV")] = None,
    api_keys: Optional[Path] = None,
) -> None:
    """Rank stocks on early-winner signals known on the screen date (no look-ahead)."""
    bearish = _bearish_from(path, api_keys)
    frame = bearish.screen(
        as_of=as_of.date() if as_of else None,
        universe=universe,
        min_market_cap=min_market_cap,
        max_market_cap=max_market_cap,
    )
    if output:
        frame.to_csv(output)
    console.print(frame.head(top).to_string())


@app.command()
def events(
    path: Path,
    fomc_start_year: Annotated[int, typer.Option(help="First year of the FOMC calendar")] = 1994,
    api_keys: Optional[Path] = None,
) -> None:
    """Load dated events: US elections since 1946, curated conflicts and FOMC meetings."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Loading events..."):
        counts = bearish.write_events(fomc_start_year=fomc_start_year)
    console.log(f"[bold][red]Events written! {counts}")


@app.command()
def midterms(
    path: Path,
    asset: Annotated[Optional[List[str]], typer.Option(help="Symbols (default: ^GSPC + sector SPDRs)")] = None,
    price_source: Annotated[str, typer.Option(help="yfinance, db or factor")] = "yfinance",
    output: Annotated[Optional[Path], typer.Option(help="Write the summary table to this CSV")] = None,
    api_keys: Optional[Path] = None,
) -> None:
    """Event study of market returns around every US midterm election since 1946."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Measuring returns around midterms..."):
        summary = bearish.midterm_study(assets=asset, price_source=price_source)
    if output:
        summary.to_csv(output)
    console.print(summary.to_string())


@app.command()
def predictions(
    path: Path,
    category: Annotated[str, typer.Option(help="election, geopolitics or all")] = "all",
    api_keys: Optional[Path] = None,
) -> None:
    """Snapshot Polymarket and Kalshi probabilities into the predictionquote table."""
    if category not in {"election", "geopolitics", "all"}:
        raise typer.BadParameter("category must be election, geopolitics or all")
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Fetching prediction markets..."):
        written = bearish.predictions(category=category)
    console.log(f"[bold][red]{written} prediction-market quotes written!")


@app.command()
def congress(
    path: Path,
    year: Annotated[Optional[int], typer.Option(help="Filing year (default: current year)")] = None,
    since: Annotated[Optional[datetime.datetime], typer.Option(help="Only filings on/after this date")] = None,
    max_filings: Annotated[int, typer.Option(help="Newest periodic transaction reports to parse")] = 200,
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch House members' stock trades (STOCK Act periodic transaction reports)."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Parsing House periodic transaction reports..."):
        result = bearish.congress_trades(year=year, since=since.date() if since else None, max_filings=max_filings)
    console.log(
        f"[bold][red]{len(result.trades)} trades from {result.parsed}/{result.filings} reports "
        f"({result.scanned} scanned on paper, {result.failed} failed)"
    )


@app.command()
def lobbying(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    year: Annotated[Optional[List[int]], typer.Option(help="Filing years (default: last two)")] = None,
    api_keys: Optional[Path] = None,
) -> None:
    """Fetch quarterly federal lobbying spend per company (Senate LDA filings)."""
    bearish = _bearish_from(path, api_keys)
    years = year or [datetime.date.today().year - 1, datetime.date.today().year]
    with console.status("[bold green]Fetching lobbying filings..."):
        written = bearish.get_lobbying(Filter(countries=countries, filters=filters), years)
    console.log(f"[bold][red]{written} lobbying values written!")


@app.command()
def link(path: Path, api_keys: Optional[Path] = None) -> None:
    """Build the tables that connect macro/commodity entities to equities, sectors and ETFs."""
    bearish = _bearish_from(path, api_keys)
    with console.status("[bold green]Building linking tables..."):
        counts = bearish.link()
    console.log(f"[bold][red]Linking tables built! {counts}")


@app.command()
def update(  # noqa: PLR0913
    path: Path,
    etf: bool = True,
    index: bool = True,
    fx: bool = True,
    sec: bool = True,
    financials: bool = True,
    macro: bool = True,
    symbols: Optional[List[str]] = None,
    api_keys: Optional[Path] = None,
    series_length: str = "1mo",
) -> None:
    bearish = _bearish_from(path, api_keys)
    bearish.update_prices(symbols, series_length=series_length)  # type: ignore
    if index:
        bearish.get_prices_index(series_length=series_length)  # type: ignore
        bearish.get_index_members()
    if etf:
        bearish.get_prices_etf(series_length=series_length)  # type: ignore
    if fx:
        bearish.get_prices_fx(series_length=series_length)  # type: ignore[arg-type]
    if sec:
        Secs.upload(bearish._bearish_db)  # type: ignore
    if financials:
        bearish.update_financials(symbols)
    if macro:
        report = bearish.update_macro()
        console.log(f"[bold][red]Macro updated! {report.vintages_written} new vintages")
    bearish.coverage()


if __name__ == "__main__":
    app()
