import datetime
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests_mock

from bearish.macro.catalog import select_series
from bearish.macro.models import MacroQuery
from bearish.macro.sources.eurostat import EurostatSource, parse_jsonstat, since_label, split_source_code

FIXTURES = {
    ("ei_bssi_m_r2", None): "esi.json",
    ("sts_inppd_m", None): "ppi.json",
    ("namq_10_gdp", None): "gdp.json",
    ("prc_hicp_manr", "CP00"): "hicp.json",
    ("prc_hicp_manr", "TOT_X_NRG_FOOD"): "hicp_core.json",
    ("une_rt_m", None): "une.json",
}


@pytest.fixture
def eurostat_api(macro_data_dir: Path) -> requests_mock.Mocker:
    def _body(request, context):  # noqa: ANN001, ANN202
        dataset = urlparse(request.url).path.rsplit("/", 1)[-1]
        coicop = parse_qs(urlparse(request.url).query).get("coicop", [None])[0]
        name = FIXTURES.get((dataset, coicop)) or FIXTURES.get((dataset, None))
        assert name, f"no fixture for {request.url}"
        return json.loads((macro_data_dir / "eurostat" / name).read_text())

    with requests_mock.Mocker() as req:
        req.get(re.compile(r"https://ec\.europa\.eu/eurostat/api/dissemination/statistics/1\.0/data/.*"), json=_body)
        yield req


def test_split_source_code() -> None:
    dataset, fixed, geo = split_source_code("ei_bssi_m_r2?indic=BS-ESI-I&s_adj=SA&geo=FR")
    assert dataset == "ei_bssi_m_r2"
    assert fixed == (("indic", "BS-ESI-I"), ("s_adj", "SA"))
    assert geo == "FR"
    with pytest.raises(ValueError):
        split_source_code("ei_bssi_m_r2?indic=BS-ESI-I")


def test_parse_jsonstat(macro_data_dir: Path) -> None:
    payload = json.loads((macro_data_dir / "eurostat" / "gdp.json").read_text())
    frame = parse_jsonstat(payload)
    assert set(frame.index.get_level_values(0)) == {"DE", "FR", "IT", "EU27_2020"}
    assert frame.loc["FR"].index.min() == datetime.date(2023, 1, 1)
    assert parse_jsonstat({"value": {}}).empty


def test_since_label() -> None:
    assert since_label(datetime.date(2025, 5, 1), "M") == "2025-05"
    assert since_label(datetime.date(2025, 5, 1), "Q") == "2025-Q2"
    assert since_label(datetime.date(2025, 5, 1), "A") == "2025"


def test_eurostat_groups_geos_and_maps_back(eurostat_api: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(concepts=["ESI"], entities=["FRA", "DEU", "ITA", "EU27"]))
    assert len(entries) == 4
    observations = EurostatSource(pause=0).read_observations(entries, start=datetime.date(2025, 1, 1))
    assert eurostat_api.call_count == 1
    geos = parse_qs(urlparse(eurostat_api.last_request.url).query)["geo"]
    assert set(geos) == {"FR", "DE", "IT", "EU27_2020"}
    assert {o.series_id for o in observations} == {"ESI.FRA", "ESI.DEU", "ESI.ITA", "ESI.EU27"}
    assert all(o.date >= datetime.date(2025, 1, 1) for o in observations)
    assert all(80 < o.value < 120 for o in observations)


def test_eurostat_catalog_concepts_all_parse(eurostat_api: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(entities=["FRA", "DEU", "EU27", "EA20"]), sources=["Eurostat"])
    observations = EurostatSource(pause=0).read_observations(entries, start=datetime.date(2024, 6, 1))
    got = {o.series_id for o in observations}
    assert {"PPI_YOY.FRA", "GDP_QOQ.DEU", "GDP_QOQ.EU27", "CPI_YOY.EA20", "CORE_CPI_YOY.EU27", "UNEMP_RATE.EU27"} <= got
    gdp = [o for o in observations if o.series_id == "GDP_QOQ.FRA"]
    assert gdp and all(abs(o.value) < 5 for o in gdp)
    assert all(o.date.month in (1, 4, 7, 10) and o.date.day == 1 for o in gdp)


def test_eurostat_handles_error_payload() -> None:
    entries = select_series(MacroQuery(concepts=["ESI"], entities=["FRA"]))
    with requests_mock.Mocker() as req:
        req.get(re.compile(r"https://ec\.europa\.eu/.*"), json={"error": [{"status": 400, "label": "bad"}]})
        assert EurostatSource(pause=0).read_observations(entries) == []


@pytest.mark.network
def test_eurostat_live() -> None:
    entries = select_series(MacroQuery(concepts=["ESI"], entities=["FRA", "EU27"]))
    observations = EurostatSource().read_observations(entries, start=datetime.date.today() - datetime.timedelta(days=120))
    assert {o.series_id for o in observations} == {"ESI.FRA", "ESI.EU27"}
