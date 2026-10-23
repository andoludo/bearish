"""Macro persistence: catalog mirror, point-in-time observations, trackers.

Kept separate from ``crud.py`` as a mixin so the ticker-centric and the
concept-centric halves of the database stay readable on their own.
"""

import logging
import math
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List

from sqlalchemy import Engine, and_, func, insert
from sqlmodel import Session, col, select

from bearish.database.schemas import MacroObservationORM, MacroSeriesORM, MacroTrackerORM
from bearish.macro.models import MacroQuery, MacroSeries, MacroTracker, Observation
from bearish.utils.utils import batch

logger = logging.getLogger(__name__)

BATCH_SIZE = 5000
# Values closer than this are the same vintage, not a revision.
REVISION_TOLERANCE = 1e-9


class MacroCrudMixin:
    def _macro_engine(self) -> Engine:
        return self._engine  # type: ignore[attr-defined,no-any-return]

    @staticmethod
    def _executemany(session: Session, orm: type, rows: List[Dict[str, Any]]) -> None:
        for chunk in batch(rows, BATCH_SIZE):
            session.exec(insert(orm).prefix_with("OR REPLACE"), params=chunk)

    def _write_macro_series(self, series: List[MacroSeries]) -> None:
        if not series:
            return
        with Session(self._macro_engine()) as session:
            self._executemany(session, MacroSeriesORM, [s.model_dump() for s in series])
            session.commit()

    @staticmethod
    def _apply_catalog_filters(statement: Any, query: MacroQuery) -> Any:
        if query.series_ids:
            statement = statement.where(col(MacroSeriesORM.series_id).in_(query.series_ids))
        if query.concepts:
            statement = statement.where(col(MacroSeriesORM.concept).in_(query.concepts))
        if query.entities:
            statement = statement.where(col(MacroSeriesORM.entity).in_(query.entities))
        if query.categories:
            statement = statement.where(col(MacroSeriesORM.category).in_(query.categories))
        if query.sources:
            statement = statement.where(col(MacroSeriesORM.source).in_(query.sources))
        return statement

    def _read_macro_series(self, query: MacroQuery) -> List[MacroSeries]:
        statement = self._apply_catalog_filters(select(MacroSeriesORM), query)
        with Session(self._macro_engine()) as session:
            rows = session.exec(statement).all()
            return [MacroSeries.model_validate(row.model_dump()) for row in rows]

    @staticmethod
    def _latest_vintages(query: MacroQuery) -> Any:
        """Subquery: newest ``as_of`` per (series_id, date), optionally as known on ``query.as_of``."""
        statement = select(
            col(MacroObservationORM.series_id),
            col(MacroObservationORM.date),
            func.max(col(MacroObservationORM.as_of)).label("as_of"),
        )
        if query.series_ids:
            statement = statement.where(col(MacroObservationORM.series_id).in_(query.series_ids))
        if query.as_of is not None:
            statement = statement.where(col(MacroObservationORM.as_of) <= query.as_of)
        return statement.group_by(col(MacroObservationORM.series_id), col(MacroObservationORM.date)).subquery()

    def _latest_values(self, session: Session, series_id: str) -> Dict[date, float]:
        """Latest vintage per date for one series."""
        vintages = self._latest_vintages(MacroQuery(series_ids=[series_id]))
        statement = select(col(MacroObservationORM.date), col(MacroObservationORM.value)).join(
            vintages,
            and_(
                col(MacroObservationORM.series_id) == vintages.c.series_id,
                col(MacroObservationORM.date) == vintages.c.date,
                col(MacroObservationORM.as_of) == vintages.c.as_of,
            ),
        )
        return {row[0]: row[1] for row in session.exec(statement).all()}

    def _write_observations(self, observations: List[Observation]) -> int:
        """Insert only values that are new or revised relative to the latest stored vintage.

        Re-fetching an unchanged series therefore adds no rows, which keeps
        the point-in-time table proportional to the number of revisions
        rather than to the number of fetches.
        """
        if not observations:
            return 0
        by_series: Dict[str, List[Observation]] = defaultdict(list)
        for observation in observations:
            by_series[observation.series_id].append(observation)

        written = 0
        with Session(self._macro_engine()) as session:
            for series_id, rows in by_series.items():
                latest = self._latest_values(session, series_id)
                changed = [
                    row.model_dump()
                    for row in rows
                    if row.date not in latest
                    or not math.isclose(
                        latest[row.date], row.value, rel_tol=REVISION_TOLERANCE, abs_tol=REVISION_TOLERANCE
                    )
                ]
                self._executemany(session, MacroObservationORM, changed)
                written += len(changed)
            session.commit()
        logger.debug(f"Wrote {written} new macro vintages out of {len(observations)} observations")
        return written

    def _read_observations(self, query: MacroQuery) -> List[Observation]:
        vintages = self._latest_vintages(query)
        statement = (
            select(MacroObservationORM)
            .join(
                vintages,
                and_(
                    col(MacroObservationORM.series_id) == vintages.c.series_id,
                    col(MacroObservationORM.date) == vintages.c.date,
                    col(MacroObservationORM.as_of) == vintages.c.as_of,
                ),
            )
            .join(MacroSeriesORM, col(MacroSeriesORM.series_id) == col(MacroObservationORM.series_id))
        )
        statement = self._apply_catalog_filters(statement, query)
        if query.start is not None:
            statement = statement.where(col(MacroObservationORM.date) >= query.start)
        if query.end is not None:
            statement = statement.where(col(MacroObservationORM.date) <= query.end)
        statement = statement.order_by(col(MacroObservationORM.series_id), col(MacroObservationORM.date))
        with Session(self._macro_engine()) as session:
            rows = session.exec(statement).all()
            return [
                Observation(series_id=row.series_id, date=row.date, value=row.value, as_of=row.as_of) for row in rows
            ]

    def _write_macro_trackers(self, trackers: List[MacroTracker]) -> None:
        if not trackers:
            return
        with Session(self._macro_engine()) as session:
            self._executemany(session, MacroTrackerORM, [t.model_dump() for t in trackers])
            session.commit()

    def _read_macro_trackers(self) -> List[MacroTracker]:
        with Session(self._macro_engine()) as session:
            rows = session.exec(select(MacroTrackerORM)).all()
            return [MacroTracker.model_validate(row.model_dump()) for row in rows]
