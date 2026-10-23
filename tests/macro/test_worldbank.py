import datetime
import json
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.worldbank import WorldBankSource


@pytest.fixture
def worldbank_api(macro_data_dir: Path) -> requests_mock.Mocker:
    def respond(request, context):  # type: ignore[no-untyped-def]
        page = request.qs.get("page", ["1"])[0]
        path = macro_data_dir / "worldbank" / f"NY.GDP.PCAP.CD_page{page}.json"
        return json.loads(path.read_text())

    with requests_mock.Mocker() as req:
        req.get(re.compile(r"https://api\.worldbank\.org/v2/country/.*"), json=respond)
        yield req


def test_worldbank_follows_pagination_and_splits_by_country(worldbank_api: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(concepts=["GDP_PER_CAPITA"], entities=["FRA", "USA", "CHN"]))
    assert len(entries) == 3
    observations = WorldBankSource(pause=0).read_observations(entries, start=datetime.date(2018, 1, 1))
    assert worldbank_api.call_count == 3  # three pages, one indicator
    assert "/country/US;FR;CN/" in worldbank_api.request_history[0].url  # one request covers all countries
    by_series = {}
    for observation in observations:
        by_series.setdefault(observation.series_id, []).append(observation)
    assert set(by_series) == {"GDP_PER_CAPITA.FRA", "GDP_PER_CAPITA.USA", "GDP_PER_CAPITA.CHN"}
    assert len(by_series["GDP_PER_CAPITA.USA"]) == 7  # 2018..2024
    assert all(60_000 < o.value < 100_000 for o in by_series["GDP_PER_CAPITA.USA"])
    assert all(o.date.month == 1 for o in observations)


def test_worldbank_handles_error_payload() -> None:
    entries = select_series(MacroQuery(concepts=["TRADE_GDP"], entities=["FRA"]))
    with requests_mock.Mocker() as req:
        req.get(re.compile(r"https://api\.worldbank\.org/.*"), json=[{"message": [{"id": "120", "value": "Invalid value"}]}])
        assert WorldBankSource(pause=0).read_observations(entries) == []


def test_worldbank_ignores_other_sources() -> None:
    assert WorldBankSource(pause=0).read_observations(select_series(sources=["OECD"])[:3]) == []


def test_worldbank_catalog_excludes_taiwan() -> None:
    assert "GDP_PER_CAPITA.TWN" not in series_by_id()
    assert series_by_id()["RESERVES.IND"].source == "WorldBank"


@pytest.mark.network
def test_worldbank_live() -> None:
    entries = select_series(MacroQuery(concepts=["TRADE_GDP"], entities=["FRA", "DEU"]))
    observations = WorldBankSource().read_observations(entries, start=datetime.date(2020, 1, 1))
    assert {o.series_id for o in observations} == {"TRADE_GDP.FRA", "TRADE_GDP.DEU"}
