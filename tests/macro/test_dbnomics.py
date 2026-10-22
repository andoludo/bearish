import datetime
import json
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.dbnomics import DBNOMICS_SERIES_URL, DbnomicsSource, document_id, series_from_document


@pytest.fixture
def dbnomics_api(macro_data_dir: Path) -> requests_mock.Mocker:
    payload = json.loads((macro_data_dir / "dbnomics" / "series_ids.json").read_text())
    with requests_mock.Mocker() as req:
        req.get(DBNOMICS_SERIES_URL, json=payload)
        yield req


def test_series_from_document_drops_na_and_uses_period_start() -> None:
    document = {"period": ["2025-Q1", "2025-Q2", "2025-Q3"], "period_start_day": ["2025-01-01", "2025-04-01", "2025-07-01"], "value": [1.5, "NA", 2.5]}
    values = series_from_document(document)
    assert values.index.min() == datetime.datetime(2025, 1, 1)
    assert values.tolist() == [1.5, 2.5]
    assert series_from_document({"period": [], "value": []}).empty
    assert document_id({"provider_code": "ILO", "dataset_code": "D", "series_code": "S"}) == "ILO/D/S"


def test_dbnomics_batches_ids_across_providers(dbnomics_api: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(concepts=["UNEMP_RATE"], entities=["BRA", "IND", "ZAF", "CHN"]), sources=["DBnomics"])
    assert len(entries) == 4
    observations = DbnomicsSource(pause=0).read_observations(entries, start=datetime.date(2020, 1, 1))
    assert dbnomics_api.call_count == 1
    assert "nbs/m_a0e01/a0e0101" in dbnomics_api.last_request.qs["series_ids"][0]  # qs is lower-cased by requests_mock
    by_series = {}
    for observation in observations:
        by_series.setdefault(observation.series_id, []).append(observation)
    assert set(by_series) == {"UNEMP_RATE.BRA", "UNEMP_RATE.IND", "UNEMP_RATE.ZAF", "UNEMP_RATE.CHN"}
    china = sorted(by_series["UNEMP_RATE.CHN"], key=lambda o: o.date)
    assert china[-1].date.day == 1 and 4 < china[-1].value < 7
    assert all(o.date >= datetime.date(2020, 1, 1) for o in observations)
    assert all(20 < o.value < 40 for o in by_series["UNEMP_RATE.ZAF"])


def test_dbnomics_warns_on_missing_series(dbnomics_api: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(concepts=["UNEMP_RATE"], entities=["TWN"]), sources=["DBnomics"])  # not in fixture
    assert DbnomicsSource(pause=0).read_observations(entries) == []


def test_dbnomics_ignores_other_sources() -> None:
    assert DbnomicsSource(pause=0).read_observations(select_series(sources=["BIS"])[:3]) == []


def test_dbnomics_catalog_entries_are_flagged_as_proxies() -> None:
    entries = select_series(sources=["DBnomics"])
    assert entries and all(e.is_proxy for e in entries)
    assert series_by_id()["UNEMP_RATE.CHN"].frequency == "M"
    assert "UNEMP_RATE.USA" not in {e.series_id for e in entries}  # OECD owns members


@pytest.mark.network
def test_dbnomics_live() -> None:
    entries = select_series(MacroQuery(concepts=["UNEMP_RATE"], entities=["CHN", "BRA"]), sources=["DBnomics"])
    observations = DbnomicsSource().read_observations(entries, start=datetime.date(2023, 1, 1))
    assert {o.series_id for o in observations} == {"UNEMP_RATE.CHN", "UNEMP_RATE.BRA"}
