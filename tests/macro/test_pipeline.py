import datetime
import re
from pathlib import Path
from typing import List, Optional

import pytest
import requests_mock

from bearish.database.crud import BearishDb
from bearish.macro.catalog import select_series
from bearish.macro.models import MacroQuery, MacroSeries, Observation
from bearish.macro.pipeline import fetch_macro, update_macro
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.sources.oecd import OecdSource
from bearish.main import Bearish


class StubSource(AbstractMacroSource):
    """Returns one fixed observation per series (so refetches are unchanged) and records ``start``."""

    __source__ = "FRED"
    calls: List[Optional[datetime.date]] = []
    value: float = 1.0

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        self.calls.append(start)
        day = datetime.date(2026, 1, 1)
        return [Observation(series_id=s.series_id, date=day, value=self.value, as_of=self.today()) for s in series]


@pytest.fixture
def db(tmp_path: Path) -> BearishDb:
    return BearishDb(database_path=tmp_path / "pipe.db")


def test_fetch_macro_writes_catalog_observations_and_trackers(db: BearishDb) -> None:
    series = select_series(sources=["FRED"])[:3]
    source = StubSource(calls=[])
    report = fetch_macro(db, [source], series, start=datetime.date(2025, 6, 1))
    assert report.series_requested == 3
    assert report.series_with_data == 3
    assert report.vintages_written == 3
    assert report.sources == {"FRED": 3}
    assert {s.series_id for s in db.read_macro_series()} == {s.series_id for s in series}
    trackers = {t.series_id: t for t in db.read_macro_trackers()}
    assert trackers[series[0].series_id].last_date == datetime.date(2026, 1, 1)
    assert trackers[series[0].series_id].last_as_of == datetime.date.today()


def test_update_macro_skips_fresh_series_and_uses_revision_window(db: BearishDb) -> None:
    series = select_series(sources=["FRED"])[:2]
    source = StubSource(calls=[])
    fetch_macro(db, [source], series)
    assert source.calls == [None]

    # Same day: nothing is due.
    report = update_macro(db, [source], MacroQuery(series_ids=[s.series_id for s in series]), delay_days=1)
    assert report.series_requested == 0

    # A week later: due again, requested from inside the revision window, not from scratch.
    later = datetime.date.today() + datetime.timedelta(days=7)
    report = update_macro(db, [source], MacroQuery(series_ids=[s.series_id for s in series]), delay_days=1, reference_date=later)
    assert report.series_requested == 2
    assert source.calls[-1] is not None
    assert source.calls[-1] < datetime.date(2026, 1, 1)
    # Unchanged values add no vintages.
    assert report.vintages_written == 0


def test_bearish_write_macro_end_to_end(tmp_path: Path, macro_data_dir: Path) -> None:
    with requests_mock.Mocker() as req:
        req.get(
            re.compile(r"https://sdmx\.oecd\.org/.*"),
            text=(macro_data_dir / "oecd" / "oecd_cli.csv").read_text(),
        )
        bearish = Bearish(path=tmp_path / "bear.db", macro_sources=[OecdSource(pause=0)])
        query = Bearish._macro_query(countries=["France", "DE"], concepts=["CLI"])
        assert query.entities == ["FRA", "DEU"]
        report = bearish.write_macro(query)
    assert report.series_with_data == 2
    frame = bearish.read_macro(MacroQuery(concepts=["CLI"]))
    assert set(frame.columns) == {"CLI.FRA", "CLI.DEU"}
    assert bearish.read_observations(MacroQuery(entities=["FRA"]))


def test_macro_source_without_required_key_is_dropped(tmp_path: Path) -> None:
    class KeyedSource(StubSource):
        requires_api_key = True

    bearish = Bearish(path=tmp_path / "bear.db", macro_sources=[KeyedSource(calls=[])])
    assert bearish.macro_sources == []
