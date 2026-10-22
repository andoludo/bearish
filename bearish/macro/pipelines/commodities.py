"""Commodity pipeline: reference list, daily futures prices (Yahoo Finance),
monthly Pink Sheet prices, weekly CFTC positioning and Comtrade trade
exposure per country."""

import datetime
import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence

from bearish.database.schemas import PriceCommodityORM
from bearish.interface.interface import BearishDbBase
from bearish.macro.catalog import select_series
from bearish.macro.commodities import COMMODITIES, commodities_with
from bearish.macro.countries import Country, priority_countries
from bearish.macro.models import MacroSources, MacroTracker, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.sources.cftc import CftcSource
from bearish.macro.sources.comtrade import fetch_country_exposures
from bearish.macro.sources.pinksheet import PinkSheetSource
from bearish.models.base import Ticker
from bearish.types import SeriesLength

if TYPE_CHECKING:
    from bearish.main import Bearish

logger = logging.getLogger(__name__)

COMMODITY_MACRO_SOURCES: List[MacroSources] = ["WorldBankPinkSheet", "CFTC"]


def write_commodity_reference(db: BearishDbBase) -> None:
    db.write_commodities(list(COMMODITIES))


def write_commodity_prices(bearish: "Bearish", series_length: SeriesLength = "max") -> List[str]:
    """Daily front-month futures prices into ``pricecommodity``; returns the symbols fetched."""
    symbols = [commodity.yfinance_symbol for commodity in commodities_with("yfinance_symbol")]
    bearish.write_many_series(
        [Ticker(symbol=symbol) for symbol in symbols if symbol],
        series_length,
        apply_filter=False,
        table=PriceCommodityORM,
        track=False,
    )
    return [symbol for symbol in symbols if symbol]


def write_commodity_observations(
    db: BearishDbBase,
    sources: Optional[Sequence[AbstractMacroSource]] = None,
    start: Optional[datetime.date] = None,
) -> int:
    """Pink Sheet and CFTC series into the macro store; returns vintages written."""
    sources = sources if sources is not None else [PinkSheetSource(), CftcSource()]
    entries = select_series(sources=COMMODITY_MACRO_SOURCES)
    db.write_macro_series(entries)
    written = 0
    for source in sources:
        observations: List[Observation] = source.read_observations(entries, start)
        if not observations:
            continue
        written += db.write_observations(observations)
        as_of = max(o.as_of for o in observations)
        last_dates: Dict[str, datetime.date] = {}
        for observation in observations:
            last_dates[observation.series_id] = max(
                last_dates.get(observation.series_id, observation.date), observation.date
            )
        db.write_macro_trackers(
            [
                MacroTracker(series_id=series_id, source=source.__source__, last_date=last_date, last_as_of=as_of)
                for series_id, last_date in last_dates.items()
            ]
        )
    return written


def write_country_exposures(
    db: BearishDbBase,
    year: Optional[int] = None,
    countries: Optional[List[Country]] = None,
    pause: float = 6.0,
) -> int:
    """Comtrade export/import exposure per country; returns rows written."""
    # Annual trade data for year Y is complete around mid Y+1.
    year = year or datetime.date.today().year - 2
    exposures = fetch_country_exposures(countries or priority_countries(), year, pause=pause)
    db.write_country_exposures(exposures)
    return len(exposures)


def run_commodities(  # noqa: PLR0913
    bearish: "Bearish",
    year: Optional[int] = None,
    series_length: SeriesLength = "max",
    prices: bool = True,
    observations: bool = True,
    exposures: bool = True,
    pause: float = 6.0,
) -> None:
    db = bearish._bearish_db
    write_commodity_reference(db)
    if prices:
        symbols = write_commodity_prices(bearish, series_length)
        logger.info(f"Commodity prices fetched for {len(symbols)} futures")
    if observations:
        written = write_commodity_observations(db)
        logger.info(f"Commodity observations: {written} new vintages")
    if exposures:
        rows = write_country_exposures(db, year=year, pause=pause)
        logger.info(f"Country commodity exposures: {rows} rows")
