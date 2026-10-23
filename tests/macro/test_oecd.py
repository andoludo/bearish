import datetime
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.oecd import OecdSource, parse_sdmx_csv, split_source_code

FIXTURES = {
    "DF_CLI,/": {"LI": "oecd_cli.csv", "BCICP": "oecd_bci.csv", "CCICP": "oecd_cci.csv"},
    "DF_PRICES_ALL": {"_T.N.GY": "oecd_cpi.csv", "_TXCP01_NRG": "oecd_cpi_core.csv"},
    "DF_IALFS_UNE_M": {"": "oecd_une.csv"},
    "DF_QNA_EXPENDITURE_GROWTH_OECD": {"": "oecd_gdp.csv"},
    "DF_INDSERV": {"PRVM": "oecd_ip.csv", "TOVM": "oecd_retail.csv"},
    "DF_FINMARK": {"IRLT": "oecd_irlt.csv", "IR3TIB": "oecd_ir3m.csv"},
}


def _fixture_for(url: str, data_dir: Path) -> str:
    for flow, by_measure in FIXTURES.items():
        if flow in url:
            for measure, name in by_measure.items():
                if measure in url:
                    return (data_dir / "oecd" / name).read_text()
    raise AssertionError(f"no fixture for {url}")


@pytest.fixture
def oecd_api(macro_data_dir: Path) -> requests_mock.Mocker:
    with requests_mock.Mocker() as req:
        req.get(
            re.compile(r"https://sdmx\.oecd\.org/public/rest/data/.*"),
            text=lambda request, context: _fixture_for(request.url, macro_data_dir),
        )
        yield req


def test_split_source_code_marks_the_entity_slot() -> None:
    flow, key = split_source_code("OECD.SDD.NAD,DSD@DF,1.1/Q..FRA.S1..B1GQ......GY.", "FRA")
    assert flow == "OECD.SDD.NAD,DSD@DF,1.1"
    assert key == "Q..{ref_area}.S1..B1GQ......GY."
    with pytest.raises(ValueError):
        split_source_code("FLOW/USA.M.LI", "FRA")


def test_parse_sdmx_csv(macro_data_dir: Path) -> None:
    frame = parse_sdmx_csv((macro_data_dir / "oecd" / "oecd_gdp.csv").read_text())
    assert set(frame.index.get_level_values(0)) == {"DEU", "FRA", "JPN", "USA"}
    assert frame.loc["FRA"].index.min() == datetime.date(2023, 1, 1)  # quarter start


def test_oecd_groups_countries_into_one_request(oecd_api: requests_mock.Mocker) -> None:
    entries = select_series(MacroQuery(concepts=["CLI"], entities=["FRA", "DEU", "USA", "JPN"]))
    assert len(entries) == 4
    observations = OecdSource(pause=0).read_observations(entries, start=datetime.date(2025, 1, 1))
    assert oecd_api.call_count == 1
    assert "FRA+DEU+USA+JPN" in oecd_api.last_request.url or "DEU+FRA" in oecd_api.last_request.url
    assert {o.series_id for o in observations} == {"CLI.FRA", "CLI.DEU", "CLI.USA", "CLI.JPN"}
    assert all(o.date >= datetime.date(2025, 1, 1) for o in observations)
    assert all(95 < o.value < 105 for o in observations)


def test_oecd_catalog_concepts_all_parse(oecd_api: requests_mock.Mocker) -> None:
    concepts = ["CLI", "BIZ_CONF", "CONS_CONF", "CPI_YOY", "CORE_CPI_YOY", "UNEMP_RATE", "GDP_YOY", "IP_YOY", "RETAIL_YOY", "Y10", "Y3M"]
    # CPI for EU members (FRA, DEU) is owned by Eurostat and US core CPI by FRED;
    # JPN keeps both with OECD but the recorded CPI fixtures only hold FRA/DEU/USA.
    entries = select_series(MacroQuery(concepts=concepts, entities=["FRA", "DEU", "JPN", "USA"]), sources=["OECD"])
    assert {s.entity for s in entries if s.concept == "CPI_YOY"} == {"JPN", "USA"}
    assert {s.entity for s in entries if s.concept == "CORE_CPI_YOY"} == {"JPN"}
    observations = OecdSource(pause=0).read_observations(entries, start=datetime.date(2025, 6, 1))
    got = {o.series_id.split(".")[0] for o in observations}
    assert got == set(concepts) - {"CORE_CPI_YOY"}
    ip = [o for o in observations if o.series_id == "IP_YOY.FRA"]
    assert ip and all(abs(o.value) < 30 for o in ip)  # transformed to y/y %
    assert series_by_id()["Y10.FRA"].source == "OECD"


def test_oecd_handles_no_records(macro_data_dir: Path) -> None:
    entries = select_series(MacroQuery(concepts=["CLI"], entities=["FRA"]))
    with requests_mock.Mocker() as req:
        req.get(re.compile(r"https://sdmx\.oecd\.org/.*"), text="NoRecordsFound")
        assert OecdSource(pause=0).read_observations(entries) == []


@pytest.mark.network
def test_oecd_live() -> None:
    entries = select_series(MacroQuery(concepts=["CLI"], entities=["FRA", "USA"]))
    observations = OecdSource().read_observations(entries, start=datetime.date.today() - datetime.timedelta(days=120))
    assert {o.series_id for o in observations} == {"CLI.FRA", "CLI.USA"}
