"""Conflict and supply-chain shock pipeline.

Fetches chokepoint transits (PortWatch), country-pair conflict intensity
(GDELT), new sanctions designations (OFAC) and military spending (SIPRI) into
the point-in-time macro store, then writes the curated conflict events and the
sanctions waves detected in the stored OFAC series to ``marketevent``.
"""

import datetime
import logging
from typing import TYPE_CHECKING, List, Optional, Union

from bearish.interface.interface import BearishDbBase
from bearish.macro.catalog import select_series
from bearish.macro.models import MacroSources
from bearish.macro.pipeline import MacroRunReport, fetch_macro
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.sources.gdelt import GdeltSource
from bearish.macro.sources.ofac import OfacSource
from bearish.macro.sources.portwatch import PortWatchSource
from bearish.macro.sources.sipri import SipriSource
from bearish.signals.conflicts import CONFLICT_EVENTS, WAVE_THRESHOLD, sanctions_waves_from_db

if TYPE_CHECKING:
    from bearish.main import Bearish

logger = logging.getLogger(__name__)

CONFLICT_MACRO_SOURCES: List[MacroSources] = ["PortWatch", "GDELT", "OFAC", "SIPRI"]


def conflict_sources() -> List[AbstractMacroSource]:
    return [PortWatchSource(), GdeltSource(), OfacSource(), SipriSource()]


def write_conflict_events(db: BearishDbBase) -> int:
    db.write_events(list(CONFLICT_EVENTS))
    return len(CONFLICT_EVENTS)


def write_sanctions_waves(db: BearishDbBase, threshold: int = WAVE_THRESHOLD) -> int:
    events = sanctions_waves_from_db(db, threshold=threshold)
    db.write_events(events)
    return len(events)


def _db(target: Union["Bearish", BearishDbBase]) -> BearishDbBase:
    return target if isinstance(target, BearishDbBase) else target._bearish_db


def run_conflict_sources(
    target: Union["Bearish", BearishDbBase],
    start: Optional[datetime.date] = None,
    sources: Optional[List[AbstractMacroSource]] = None,
    wave_threshold: int = WAVE_THRESHOLD,
) -> MacroRunReport:
    """Fetch every conflict series, then refresh the conflict and sanctions-wave events.

    ``start`` bounds the fetched history; GDELT additionally caps it at its
    backfill window (400 days by default) because it downloads one file per day.
    """
    db = _db(target)
    sources = sources if sources is not None else conflict_sources()
    names = [source.__source__ for source in sources]
    series = select_series(sources=[name for name in CONFLICT_MACRO_SOURCES if name in names])
    report = fetch_macro(db, sources, series, start=start)
    events = write_conflict_events(db)
    waves = write_sanctions_waves(db, threshold=wave_threshold)
    logger.info(f"Conflict pipeline: {report.vintages_written} vintages, {events} conflict events, {waves} waves")
    return report
