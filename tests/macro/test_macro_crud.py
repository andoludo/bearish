import datetime
from pathlib import Path

import pytest

from bearish.database.crud import BearishDb
from bearish.macro.catalog._builder import series
from bearish.macro.models import MacroQuery, MacroTracker, Observation


@pytest.fixture
def db(tmp_path: Path) -> BearishDb:
    return BearishDb(database_path=tmp_path / "macro.db")


def _obs(series_id: str, day: datetime.date, value: float, as_of: datetime.date) -> Observation:
    return Observation(series_id=series_id, date=day, value=value, as_of=as_of)


def test_series_round_trip_and_filters(db: BearishDb) -> None:
    entries = [
        series("CPI_YOY", "FRA", "OECD", "a", "M"),
        series("CPI_YOY", "DEU", "OECD", "b", "M"),
        series("Y10", "USA", "FRED", "DGS10", "D"),
    ]
    db.write_macro_series(entries)
    db.write_macro_series(entries)  # idempotent
    assert len(db.read_macro_series()) == 3
    assert {s.entity for s in db.read_macro_series(MacroQuery(concepts=["CPI_YOY"]))} == {"FRA", "DEU"}
    assert [s.series_id for s in db.read_macro_series(MacroQuery(sources=["FRED"]))] == ["Y10.USA"]
    assert db.read_macro_series(MacroQuery(categories=["rates"]))[0].frequency == "D"


def test_observations_are_point_in_time(db: BearishDb) -> None:
    entry = series("CPI_YOY", "FRA", "OECD", "a", "M")
    db.write_macro_series([entry])
    jan, feb = datetime.date(2026, 1, 1), datetime.date(2026, 2, 1)
    first = [_obs(entry.series_id, jan, 1.0, datetime.date(2026, 2, 15)), _obs(entry.series_id, feb, 2.0, datetime.date(2026, 3, 15))]

    assert db.write_observations(first) == 2
    # Re-fetching identical values adds no vintage.
    assert db.write_observations([_obs(entry.series_id, jan, 1.0, datetime.date(2026, 4, 1))]) == 0
    # A revision adds a new vintage and becomes the latest value.
    assert db.write_observations([_obs(entry.series_id, jan, 1.5, datetime.date(2026, 4, 1))]) == 1

    latest = {o.date: o.value for o in db.read_observations(MacroQuery(series_ids=[entry.series_id]))}
    assert latest == {jan: 1.5, feb: 2.0}

    known_in_march = {o.date: o.value for o in db.read_observations(MacroQuery(series_ids=[entry.series_id], as_of=datetime.date(2026, 3, 20)))}
    assert known_in_march == {jan: 1.0, feb: 2.0}

    known_in_feb = db.read_observations(MacroQuery(series_ids=[entry.series_id], as_of=datetime.date(2026, 2, 20)))
    assert [(o.date, o.value) for o in known_in_feb] == [(jan, 1.0)]

    view = db.read_query("SELECT series_id, date, value FROM macrolatest ORDER BY date")
    assert view["value"].tolist() == [1.5, 2.0]


def test_read_observations_filters_by_catalog_fields_and_dates(db: BearishDb) -> None:
    fra = series("CPI_YOY", "FRA", "OECD", "a", "M")
    usa = series("Y10", "USA", "FRED", "DGS10", "D")
    db.write_macro_series([fra, usa])
    as_of = datetime.date(2026, 5, 1)
    db.write_observations(
        [
            _obs(fra.series_id, datetime.date(2026, 1, 1), 1.0, as_of),
            _obs(fra.series_id, datetime.date(2026, 2, 1), 1.1, as_of),
            _obs(usa.series_id, datetime.date(2026, 2, 3), 4.2, as_of),
        ]
    )
    assert len(db.read_observations(MacroQuery(entities=["FRA"]))) == 2
    assert len(db.read_observations(MacroQuery(categories=["rates"]))) == 1
    assert len(db.read_observations(MacroQuery(start=datetime.date(2026, 2, 1)))) == 2
    assert len(db.read_observations(MacroQuery(end=datetime.date(2026, 1, 31)))) == 1
    frame = db.read_macro_frame(MacroQuery(entities=["FRA", "USA"]))
    assert list(frame.columns) == ["CPI_YOY.FRA", "Y10.USA"]
    assert len(frame) == 3
    assert db.read_macro_frame(MacroQuery(entities=["JPN"])).empty


def test_trackers_round_trip(db: BearishDb) -> None:
    tracker = MacroTracker(series_id="CPI_YOY.FRA", source="OECD", last_date=datetime.date(2026, 8, 1), last_as_of=datetime.date(2026, 10, 1))
    db.write_macro_trackers([tracker])
    db.write_macro_trackers([tracker.model_copy(update={"last_date": datetime.date(2026, 9, 1)})])
    stored = db.read_macro_trackers()
    assert len(stored) == 1
    assert stored[0].last_date == datetime.date(2026, 9, 1)
