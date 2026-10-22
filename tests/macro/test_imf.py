import datetime
import json
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.imf import IMF_DATAMAPPER_URL, ImfSource, datamapper_code


@pytest.fixture
def imf_api(macro_data_dir: Path) -> requests_mock.Mocker:
    def respond(request, context):  # type: ignore[no-untyped-def]
        indicator = request.url.rstrip("/").rsplit("/", 1)[-1]
        path = macro_data_dir / "imf" / f"{indicator}.json"
        if not path.exists():
            context.status_code = 404
            return {}
        return json.loads(path.read_text())

    with requests_mock.Mocker() as req:
        req.get(re.compile(r"https://www\.imf\.org/external/datamapper/api/v1/.*"), json=respond)
        yield req


def test_region_codes_map_to_datamapper_aggregates() -> None:
    assert datamapper_code("WLD") == "WEOWORLD"
    assert datamapper_code("EA20") == "EURO"
    assert datamapper_code("FRA") == "FRA"


def test_imf_one_request_per_indicator(imf_api: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(concepts=["GDP_FCST", "DEBT_GDP"], entities=["FRA", "USA", "CHN", "WLD", "EA20"]))
    assert len(entries) == 10
    observations = ImfSource(pause=0).read_observations(entries, start=datetime.date(2020, 1, 1))
    assert imf_api.call_count == 2
    by_series = {}
    for observation in observations:
        by_series.setdefault(observation.series_id, []).append(observation)
    assert set(by_series) == {s.series_id for s in entries}
    growth = by_series["GDP_FCST.WLD"]
    assert all(o.date.month == 1 and o.date.day == 1 for o in growth)
    assert all(-15 < o.value < 15 for o in growth)
    # WEO carries forecast years beyond today
    assert max(o.date for o in growth) > datetime.date.today()
    debt = by_series["DEBT_GDP.USA"]
    assert all(50 < o.value < 200 for o in debt)
    assert all(o.date >= datetime.date(2020, 1, 1) for o in observations)


def test_imf_skips_missing_entities(imf_api: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(concepts=["GDP_FCST"], entities=["JPN"]))  # not in the trimmed fixture
    assert ImfSource(pause=0).read_observations(entries) == []


def test_imf_ignores_other_sources() -> None:
    assert ImfSource(pause=0).read_observations(select_series(sources=["FRED"])[:3]) == []


def test_imf_catalog_covers_fiscal_and_external_balances() -> None:
    assert series_by_id()["CA_GDP.DEU"].source == "IMF"
    assert series_by_id()["DEFICIT_GDP.ITA"].frequency == "A"
    assert series_by_id()["INFL_FCST.EM"].entity_type == "region"


@pytest.mark.network
def test_imf_live() -> None:
    entries = select_series(MacroQuery(concepts=["GDP_FCST"], entities=["FRA", "WLD"]))
    observations = ImfSource().read_observations(entries, start=datetime.date(2024, 1, 1))
    assert {o.series_id for o in observations} == {"GDP_FCST.FRA", "GDP_FCST.WLD"}
