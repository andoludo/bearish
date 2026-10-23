import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd
import pytest

from bearish.database.crud import BearishDb
from bearish.macro.catalog import select_series
from bearish.macro.models import MacroQuery, MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.signals.conflicts import CONFLICT_EVENTS, sanctions_wave_events, sanctions_waves_from_db
from bearish.signals.pipelines.conflict import (
    CONFLICT_MACRO_SOURCES,
    conflict_sources,
    run_conflict_sources,
    write_conflict_events,
)


def test_curated_conflict_events_are_well_formed() -> None:
    ids = [event.event_id for event in CONFLICT_EVENTS]
    assert len(ids) == len(set(ids))
    assert all(event.event_type == "conflict" and event.source == "curated" for event in CONFLICT_EVENTS)
    assert all(event.country and len(event.country) == 3 for event in CONFLICT_EVENTS)
    by_id = {event.event_id: event for event in CONFLICT_EVENTS}
    assert by_id["CONFLICT_RUS_UKR_2022"].date == datetime.date(2022, 2, 24)
    assert by_id["CONFLICT_SEPT11_2001"].date == datetime.date(2001, 9, 11)
    assert by_id["CONFLICT_ISR_HAMAS_2023"].date == datetime.date(2023, 10, 7)
    assert "oil" in by_id["CONFLICT_IRQ_KWT_1990"].tag_set()
    assert min(event.date for event in CONFLICT_EVENTS).year == 1990


def test_sanctions_wave_events_threshold() -> None:
    months = pd.date_range("2022-01-01", periods=4, freq="MS")
    counts = pd.DataFrame({"RUS": [10, 545, 147, 0], "IRN": [5, 5, 60, 0], "WLD": [999, 999, 999, 999]}, index=months)
    events = sanctions_wave_events(counts, threshold=50, as_of=datetime.date(2026, 10, 23))
    assert [(e.event_id, e.outcome) for e in events] == [
        ("SANCTIONS_RUS_2022-02", "545"),
        ("SANCTIONS_IRN_2022-03", "60"),
        ("SANCTIONS_RUS_2022-03", "147"),
    ]
    wave = events[0]
    assert wave.event_type == "sanctions"
    assert wave.date == datetime.date(2022, 2, 1)
    assert wave.end_date == datetime.date(2022, 2, 28)
    assert wave.tag_set() == {"sanctions", "ofac", "RUS"}


class _StubOfac(AbstractMacroSource):
    __source__ = "OFAC"

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        values = {datetime.date(2022, 2, 1): 92.0, datetime.date(2022, 3, 1): 545.0}
        return [
            Observation(series_id=s.series_id, date=day, value=value if s.entity == "RUS" else 1.0, as_of=self.today())
            for s in series
            for day, value in values.items()
        ]


@pytest.fixture
def db(tmp_path: Path) -> BearishDb:
    return BearishDb(database_path=tmp_path / "conflict.db")


def test_pipeline_writes_series_events_and_waves(db: BearishDb) -> None:
    assert {source.__source__ for source in conflict_sources()} == set(CONFLICT_MACRO_SOURCES)
    report = run_conflict_sources(db, sources=[_StubOfac()], wave_threshold=100)
    assert report.series_requested == len(select_series(sources=["OFAC"]))
    assert report.sources == {"OFAC": 2 * report.series_requested}
    assert len(db.read_observations(MacroQuery(series_ids=["SANCTIONS_NEW.RUS"]))) == 2

    conflicts = db.read_events(event_type="conflict")
    assert len(conflicts) == len(CONFLICT_EVENTS)
    waves = db.read_events(event_type="sanctions")
    assert [e.event_id for e in waves] == ["SANCTIONS_RUS_2022-03"]
    assert sanctions_waves_from_db(db, threshold=50)[0].event_id == "SANCTIONS_RUS_2022-02"

    assert write_conflict_events(db) == len(CONFLICT_EVENTS)  # idempotent upsert
    assert len(db.read_events(event_type="conflict")) == len(CONFLICT_EVENTS)


def test_sanctions_waves_from_empty_db(db: BearishDb) -> None:
    assert sanctions_waves_from_db(db) == []
