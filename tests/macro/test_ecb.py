import datetime
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.ecb import EcbSource, parse_ecb_csv

FIXTURES = {
    "BSI/": "ecb_m3.csv",
    "SR_10Y": "ecb_y10.csv",
    "SR_2Y": "ecb_y2.csv",
    "EXR/": "ecb_fx.csv",
    "LFSI/": "ecb_une.csv",
}


@pytest.fixture
def ecb_api(macro_data_dir: Path) -> requests_mock.Mocker:
    def _body(request, context):  # noqa: ANN001, ANN202
        for marker, name in FIXTURES.items():
            if marker in request.url:
                return (macro_data_dir / "ecb" / name).read_text()
        raise AssertionError(f"no fixture for {request.url}")

    with requests_mock.Mocker() as req:
        req.get(re.compile(r"https://data-api\.ecb\.europa\.eu/service/data/.*"), text=_body)
        yield req


def test_parse_ecb_csv_handles_daily_and_monthly(macro_data_dir: Path) -> None:
    daily = parse_ecb_csv((macro_data_dir / "ecb" / "ecb_y10.csv").read_text())
    monthly = parse_ecb_csv((macro_data_dir / "ecb" / "ecb_m3.csv").read_text())
    assert daily.index.min() == datetime.datetime(2025, 7, 1)
    assert monthly.index[0] == datetime.datetime(2025, 7, 1)
    assert parse_ecb_csv("").empty


def test_ecb_catalog_entries_parse(ecb_api: requests_mock.Mocker) -> None:
    entries = select_series(sources=["ECB"])
    assert {e.entity for e in entries} == {"EA20"}
    observations = EcbSource(pause=0).read_observations(entries, start=datetime.date(2025, 9, 1))
    by_series = {}
    for observation in observations:
        by_series.setdefault(observation.series_id, []).append(observation)
    assert set(by_series) == {"M2_YOY.EA20", "Y10.EA20", "Y2.EA20", "FX_USD.EA20", "UNEMP_RATE.EA20"}
    assert ecb_api.call_count == len(entries)
    assert all(o.date >= datetime.date(2025, 9, 1) for o in observations)
    assert all(1.0 < o.value < 1.5 for o in by_series["FX_USD.EA20"])  # USD per EUR
    assert all(5 < o.value < 9 for o in by_series["UNEMP_RATE.EA20"])
    assert series_by_id()["M2_YOY.EA20"].is_proxy


def test_ecb_ignores_other_sources() -> None:
    assert EcbSource(pause=0).read_observations(select_series(sources=["FRED"])[:2]) == []


@pytest.mark.network
def test_ecb_live() -> None:
    entries = select_series(MacroQuery(series_ids=["FX_USD.EA20"]))
    observations = EcbSource().read_observations(entries, start=datetime.date.today() - datetime.timedelta(days=30))
    assert observations
