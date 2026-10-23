import datetime
import re
from pathlib import Path

import pandas as pd
import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.gdelt import (
    METRICS,
    PAIRS,
    GdeltSource,
    aggregate_day,
    pair_entity,
    parse_daily_export,
    split_source_code,
)

DAYS = ("20261020", "20261021")


@pytest.fixture
def gdelt_files(macro_data_dir: Path) -> requests_mock.Mocker:
    files = {day: (macro_data_dir / "gdelt" / f"{day}.export.CSV.zip").read_bytes() for day in DAYS}

    def respond(request, context):  # type: ignore[no-untyped-def]
        day = re.search(r"/(\d{8})\.export", request.url).group(1)  # type: ignore[union-attr]
        if day not in files:
            context.status_code = 404
            return b""
        return files[day]

    with requests_mock.Mocker() as req:
        req.get(re.compile(r"https://data\.gdeltproject\.org/events/\d{8}\.export\.CSV\.zip"), content=respond)
        yield req


class FixedDaySource(GdeltSource):
    """GdeltSource whose 'today' is 2026-10-22 so the window ends on the fixture days."""

    @staticmethod
    def today() -> datetime.date:
        return datetime.date(2026, 10, 22)


def test_pair_entity_is_symmetric_and_catalog_matches() -> None:
    assert pair_entity("USA", "CHN") == pair_entity("CHN", "USA") == "CHN_USA"
    entries = select_series(sources=["GDELT"])
    pair_entries = [e for e in entries if e.entity_type == "country_pair"]
    assert len(pair_entries) == len(PAIRS) * len(METRICS)
    assert series_by_id()["GDELT_CONFLICT_EVENTS.RUS_UKR"].source_code == "pair|RUS|UKR|conflict_events"
    assert split_source_code("pair|USA|CHN|tone") == (("pair", "CHN", "USA"), "tone")
    assert split_source_code("country|USA|conflict_events") == (("country", "USA"), "conflict_events")
    with pytest.raises(ValueError):
        split_source_code("pair|USA|tone")
    assert series_by_id()["GDELT_CONFLICT_EVENTS.USA"].entity_type == "country"


def test_aggregate_day_counts_both_directions_and_quad_classes(macro_data_dir: Path) -> None:
    frame = parse_daily_export((macro_data_dir / "gdelt" / "20261020.export.CSV.zip").read_bytes())
    assert {"actor1", "actor2", "quad", "goldstein", "tone"} <= set(frame.columns)
    daily = aggregate_day(frame, [("RUS", "UKR"), ("IRN", "ISR")], ["USA"])

    rus_ukr = frame[((frame.actor1 == "RUS") & (frame.actor2 == "UKR")) | ((frame.actor1 == "UKR") & (frame.actor2 == "RUS"))]
    assert daily[("pair", "RUS", "UKR")]["conflict_events"] == (rus_ukr.quad == 4).sum() == 260
    assert daily[("pair", "RUS", "UKR")]["verbal_conflict"] == (rus_ukr.quad == 3).sum() == 242
    assert daily[("pair", "RUS", "UKR")]["goldstein"] == pytest.approx(rus_ukr.goldstein.mean())
    assert daily[("pair", "IRN", "ISR")]["conflict_events"] == 64
    usa = frame[(frame.actor1 == "USA") | (frame.actor2 == "USA")]
    assert daily[("country", "USA")]["conflict_events"] == (usa.quad == 4).sum()


def test_gdelt_source_downloads_each_day_once(gdelt_files: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(entities=["RUS_UKR", "CHN_TWN", "USA"]), sources=["GDELT"])
    source = FixedDaySource(pause=0, backfill_days=3)
    assert source.days(None) == [datetime.date(2026, 10, 19), datetime.date(2026, 10, 20), datetime.date(2026, 10, 21)]
    observations = source.read_observations(entries)

    assert gdelt_files.call_count == 3  # one request per day, shared by every series; 10-19 is a 404
    by_series: dict = {}
    for observation in observations:
        by_series.setdefault(observation.series_id, {})[observation.date] = observation.value
    assert set(by_series["GDELT_CONFLICT_EVENTS.RUS_UKR"]) == {datetime.date(2026, 10, 20), datetime.date(2026, 10, 21)}
    assert by_series["GDELT_CONFLICT_EVENTS.RUS_UKR"][datetime.date(2026, 10, 20)] == 260
    assert all(-10 <= v <= 10 for v in by_series["GDELT_GOLDSTEIN.CHN_TWN"].values())
    assert "GDELT_CONFLICT_EVENTS.USA" in by_series


def test_gdelt_cache_dir_avoids_second_download(gdelt_files: requests_mock.Mocker, tmp_path: Path) -> None:
    entries = select_series(MacroQuery(series_ids=["GDELT_TONE.IRN_ISR"]))
    source = FixedDaySource(pause=0, backfill_days=2, cache_dir=tmp_path)
    first = source.read_observations(entries)
    calls = gdelt_files.call_count
    second = FixedDaySource(pause=0, backfill_days=2, cache_dir=tmp_path).read_observations(entries)
    assert gdelt_files.call_count == calls
    assert [(o.date, o.value) for o in first] == [(o.date, o.value) for o in second]
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{day}.export.CSV.zip" for day in DAYS]


def test_gdelt_respects_start(gdelt_files: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(series_ids=["GDELT_CONFLICT_EVENTS.RUS_UKR"]))
    observations = FixedDaySource(pause=0).read_observations(entries, start=datetime.date(2026, 10, 21))
    assert gdelt_files.call_count == 1
    assert [o.date for o in observations] == [datetime.date(2026, 10, 21)]
    assert isinstance(pd.Timestamp(observations[0].date), pd.Timestamp)


@pytest.mark.network
def test_gdelt_live() -> None:
    entries = select_series(MacroQuery(series_ids=["GDELT_CONFLICT_EVENTS.RUS_UKR"]))
    observations = GdeltSource(backfill_days=2).read_observations(entries)
    assert observations
    assert observations[-1].value > 0
