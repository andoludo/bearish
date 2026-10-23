"""Fetch-and-store orchestration for the macro catalog.

Separated from ``bearish.main`` so it can be driven from the CLI, from
``Bearish`` and from tests with the same code path.
"""

import datetime
import logging
from collections import defaultdict
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from bearish.interface.interface import BearishDbBase
from bearish.macro.catalog import select_series
from bearish.macro.models import Frequency, MacroQuery, MacroSeries, MacroTracker, Observation
from bearish.macro.sources.base import AbstractMacroSource

logger = logging.getLogger(__name__)

# How far back an incremental update re-requests data so that provider
# revisions of recent periods are captured as new vintages.
REVISION_WINDOW: Dict[Frequency, datetime.timedelta] = {
    "D": datetime.timedelta(days=60),
    "W": datetime.timedelta(days=120),
    "M": datetime.timedelta(days=450),
    "Q": datetime.timedelta(days=750),
    "A": datetime.timedelta(days=1100),
}


class MacroRunReport(BaseModel):
    series_requested: int = 0
    series_with_data: int = 0
    observations_fetched: int = 0
    vintages_written: int = 0
    sources: Dict[str, int] = Field(default_factory=dict, description="Observations fetched per source")

    def add(self, source: str, observations: List[Observation], written: int) -> None:
        self.observations_fetched += len(observations)
        self.vintages_written += written
        self.sources[source] = self.sources.get(source, 0) + len(observations)
        self.series_with_data += len({o.series_id for o in observations})


def _trackers_from(observations: List[Observation], source: str, as_of: datetime.date) -> List[MacroTracker]:
    last_dates: Dict[str, datetime.date] = {}
    for observation in observations:
        current = last_dates.get(observation.series_id)
        if current is None or observation.date > current:
            last_dates[observation.series_id] = observation.date
    return [
        MacroTracker(series_id=series_id, source=source, last_date=last_date, last_as_of=as_of)
        for series_id, last_date in last_dates.items()
    ]


def fetch_macro(
    db: BearishDbBase,
    sources: List[AbstractMacroSource],
    series: List[MacroSeries],
    start: Optional[datetime.date] = None,
    starts: Optional[Dict[str, datetime.date]] = None,
) -> MacroRunReport:
    """Fetch ``series`` from the matching ``sources`` and store them point-in-time.

    ``starts`` gives a per-series start (incremental updates); ``start`` is the
    fallback for series without one. Catalog rows and trackers are written
    alongside the observations.
    """
    report = MacroRunReport(series_requested=len(series))
    if not series:
        return report
    db.write_macro_series(series)
    today = datetime.date.today()
    by_source: Dict[str, List[MacroSeries]] = defaultdict(list)
    for macro_series in series:
        by_source[macro_series.source].append(macro_series)

    for source in sources:
        own = by_source.get(source.__source__, [])
        if not own:
            continue
        # Series sharing a start date are fetched together; a provider call per
        # distinct start keeps the incremental window tight without per-series requests.
        by_start: Dict[Optional[datetime.date], List[MacroSeries]] = defaultdict(list)
        for macro_series in own:
            by_start[(starts or {}).get(macro_series.series_id, start)].append(macro_series)
        for series_start, group in by_start.items():
            logger.info(f"Fetching {len(group)} series from {source.__source__} (start={series_start})")
            observations = source.read_observations(group, series_start)
            written = db.write_observations(observations)
            db.write_macro_trackers(_trackers_from(observations, source.__source__, today))
            report.add(source.__source__, observations, written)
    return report


def update_macro(
    db: BearishDbBase,
    sources: List[AbstractMacroSource],
    query: Optional[MacroQuery] = None,
    delay_days: int = 1,
    reference_date: Optional[datetime.date] = None,
) -> MacroRunReport:
    """Incremental refresh: re-request each tracked series from inside its revision window.

    Series fetched less than ``delay_days`` ago are skipped; series never
    fetched are pulled in full.
    """
    reference_date = reference_date or datetime.date.today()
    series = select_series(query)
    trackers = {t.series_id: t for t in db.read_macro_trackers()}
    due: List[MacroSeries] = []
    starts: Dict[str, datetime.date] = {}
    for macro_series in series:
        tracker = trackers.get(macro_series.series_id)
        if tracker is None:
            due.append(macro_series)
            continue
        if (reference_date - tracker.last_as_of).days < delay_days:
            continue
        due.append(macro_series)
        starts[macro_series.series_id] = tracker.last_date - REVISION_WINDOW[macro_series.frequency]
    logger.info(f"{len(due)} of {len(series)} macro series due for update")
    return fetch_macro(db, sources, due, starts=starts)
