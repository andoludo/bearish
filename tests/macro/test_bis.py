import datetime
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.bis import BisSource, bis_area, parse_bis_csv, split_source_code

FIXTURES = {
    "WS_CBPOL": "cbpol.csv",
    "WS_CREDIT_GAP": "credit_gap.csv",
    "WS_TC": "credit_gdp.csv",
    "WS_SPP": "spp.csv",
    "WS_EER": "eer.csv",
}


@pytest.fixture
def bis_api(macro_data_dir: Path) -> requests_mock.Mocker:
    def respond(request, context):  # type: ignore[no-untyped-def]
        flow = next(flow for flow in FIXTURES if f"/BIS/{flow}/" in request.url)
        return (macro_data_dir / "bis" / FIXTURES[flow]).read_text()

    with requests_mock.Mocker() as req:
        req.get(re.compile(r"https://stats\.bis\.org/api/v2/data/dataflow/BIS/.*"), text=respond)
        yield req


def test_bis_area_codes() -> None:
    assert bis_area("USA") == "US"
    assert bis_area("EA20") == "XM"
    assert bis_area("XX") == "XX"


def test_split_source_code() -> None:
    assert split_source_code("WS_TC/2.0/Q.FR.P.A.M.770.A", "FR") == ("WS_TC", "2.0", "Q.{area}.P.A.M.770.A")
    assert split_source_code("WS_EER/1.0/M.R.B.US", "US") == ("WS_EER", "1.0", "M.R.B.{area}")
    with pytest.raises(ValueError):
        split_source_code("WS_CBPOL/1.0/M.US", "FR")


def test_parse_bis_csv_handles_both_area_columns(macro_data_dir: Path) -> None:
    policy = parse_bis_csv((macro_data_dir / "bis" / "cbpol.csv").read_text())
    assert set(policy.index.get_level_values(0)) == {"US", "XM", "JP", "GB"}
    credit = parse_bis_csv((macro_data_dir / "bis" / "credit_gdp.csv").read_text())
    assert set(credit.index.get_level_values(0)) == {"US", "FR", "CN"}
    assert credit.loc["FR"].index.min() == datetime.date(2023, 1, 1)


def test_bis_merges_areas_per_dataflow(bis_api: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(concepts=["POLICY_RATE"], entities=["USA", "JPN", "GBR", "EA20"]))
    assert len(entries) == 4
    observations = BisSource(pause=0).read_observations(entries, start=datetime.date(2025, 1, 1))
    assert bis_api.call_count == 1
    assert "M.US+JP+GB+XM" in bis_api.last_request.url or "+XM" in bis_api.last_request.url
    by_series = {}
    for observation in observations:
        by_series.setdefault(observation.series_id, []).append(observation)
    assert set(by_series) == {"POLICY_RATE.USA", "POLICY_RATE.JPN", "POLICY_RATE.GBR", "POLICY_RATE.EA20"}
    assert all(0 <= o.value < 10 for o in observations)
    assert all(o.date >= datetime.date(2025, 1, 1) for o in observations)


def test_bis_credit_property_and_reer_concepts(bis_api: requests_mock.Mocker) -> None:
    concepts = ["CREDIT_GDP_GAP", "CREDIT_GDP", "HOUSE_PRICE_YOY", "REER"]
    entries = select_series(MacroQuery(concepts=concepts, entities=["USA", "FRA", "CHN"]))
    observations = BisSource(pause=0).read_observations(entries, start=datetime.date(2024, 1, 1))
    assert bis_api.call_count == 4
    got = {o.series_id.split(".")[0] for o in observations}
    assert got == set(concepts)
    gap = [o for o in observations if o.series_id == "CREDIT_GDP_GAP.USA"]
    assert gap and all(-40 < o.value < 40 for o in gap)
    ratio = [o for o in observations if o.series_id == "CREDIT_GDP.FRA"]
    assert ratio and all(150 < o.value < 260 for o in ratio)


def test_bis_ignores_other_sources() -> None:
    assert BisSource(pause=0).read_observations(select_series(sources=["IMF"])[:3]) == []


def test_bis_catalog_shape() -> None:
    assert series_by_id()["POLICY_RATE.EA20"].entity_type == "region"
    assert "POLICY_RATE.FRA" not in series_by_id()  # euro-area members share the ECB rate
    assert series_by_id()["REER.TWN"].source == "BIS"


@pytest.mark.network
def test_bis_live() -> None:
    entries = select_series(MacroQuery(concepts=["POLICY_RATE"], entities=["USA", "EA20"]))
    observations = BisSource().read_observations(entries, start=datetime.date.today() - datetime.timedelta(days=120))
    assert {o.series_id for o in observations} == {"POLICY_RATE.USA", "POLICY_RATE.EA20"}
