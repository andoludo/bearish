import datetime
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series
from bearish.macro.models import MacroQuery
from bearish.macro.sources.epu import EPU_URL, EpuSource, parse_epu_workbook
from bearish.macro.sources.gdpnow import GDPNOW_URL, GdpNowSource, parse_gdpnow_workbook
from bearish.macro.sources.gpr import GPR_URL, GprSource, parse_gpr_workbook

# --- EPU -------------------------------------------------------------------


def test_parse_epu_workbook_drops_footnotes(macro_data_dir: Path) -> None:
    frame = parse_epu_workbook((macro_data_dir / "epu" / "All_Country_Data.xlsx").read_bytes())
    assert "GEPU_current" in frame.columns and "France" in frame.columns
    assert frame.index.is_monotonic_increasing
    assert all(day == 1 for day in frame.index.day)


def test_epu_reads_global_and_country_columns(macro_data_dir: Path) -> None:
    entries = select_series(MacroQuery(entities=["WLD", "FRA", "USA", "GBR", "KOR"]), sources=["EPU"])
    assert {e.series_id for e in entries} == {"EPU.WLD", "EPU.FRA", "EPU.USA", "EPU.GBR", "EPU.KOR"}
    with requests_mock.Mocker() as req:
        req.get(EPU_URL, content=(macro_data_dir / "epu" / "All_Country_Data.xlsx").read_bytes())
        observations = EpuSource(pause=0).read_observations(entries, start=datetime.date(2025, 1, 1))
        assert req.call_count == 1
    assert {o.series_id for o in observations} == {e.series_id for e in entries}
    assert all(o.date >= datetime.date(2025, 1, 1) and 10 < o.value < 2000 for o in observations)


def test_epu_ignores_other_sources() -> None:
    assert EpuSource(pause=0).read_observations(select_series(sources=["ECB"])[:2]) == []


# --- GPR -------------------------------------------------------------------


def test_parse_gpr_workbook(macro_data_dir: Path) -> None:
    frame = parse_gpr_workbook((macro_data_dir / "gpr" / "data_gpr_export.xlsx").read_bytes())
    assert {"GPR", "GPRC_FRA", "GPRC_USA"} <= set(frame.columns)
    assert frame.index.is_monotonic_increasing


def test_gpr_reads_global_and_country_columns(macro_data_dir: Path) -> None:
    entries = select_series(MacroQuery(entities=["WLD", "FRA", "USA", "CHN", "DEU"]), sources=["GPR"])
    assert {e.series_id for e in entries} == {"GPR.WLD", "GPR.FRA", "GPR.USA", "GPR.CHN", "GPR.DEU"}
    with requests_mock.Mocker() as req:
        req.get(GPR_URL, content=(macro_data_dir / "gpr" / "data_gpr_export.xlsx").read_bytes())
        observations = GprSource(pause=0).read_observations(entries, start=datetime.date(2025, 1, 1))
        assert req.call_count == 1
    assert {o.series_id for o in observations} == {e.series_id for e in entries}
    world = [o for o in observations if o.series_id == "GPR.WLD"]
    assert world and all(50 < o.value < 500 for o in world)


def test_gpr_catalog_only_lists_countries_in_export() -> None:
    assert not [e for e in select_series(sources=["GPR"]) if e.entity == "SGP"]
    assert [e for e in select_series(sources=["GPR"]) if e.entity == "JPN"]


# --- GDPNow ----------------------------------------------------------------


def test_parse_gdpnow_combines_archive_and_current_quarter(macro_data_dir: Path) -> None:
    content = (macro_data_dir / "gdpnow" / "GDPTrackingModelDataAndForecasts.xlsx").read_bytes()
    values = parse_gdpnow_workbook(content, "GDP Nowcast")
    assert values.index.is_monotonic_increasing and values.index.is_unique
    assert values.index.min() < datetime.datetime(2026, 7, 29) < values.index.max()  # spans both sheets
    assert all(-10 < v < 15 for v in values)
    assert parse_gdpnow_workbook(content, "Nope").empty


def test_gdpnow_source(macro_data_dir: Path) -> None:
    entries = select_series(sources=["AtlantaFed"])
    assert [e.series_id for e in entries] == ["GDP_NOWCAST.USA"]
    with requests_mock.Mocker() as req:
        req.get(GDPNOW_URL, content=(macro_data_dir / "gdpnow" / "GDPTrackingModelDataAndForecasts.xlsx").read_bytes())
        observations = GdpNowSource(pause=0).read_observations(entries, start=datetime.date(2026, 8, 1))
    assert observations
    assert all(o.date >= datetime.date(2026, 8, 1) for o in observations)
    assert observations[-1].as_of == datetime.date.today()


@pytest.mark.network
def test_epu_live() -> None:
    assert EpuSource().read_observations(select_series(MacroQuery(series_ids=["EPU.WLD"])), start=datetime.date(2025, 1, 1))


@pytest.mark.network
def test_gpr_live() -> None:
    assert GprSource().read_observations(select_series(MacroQuery(series_ids=["GPR.WLD"])), start=datetime.date(2025, 1, 1))


@pytest.mark.network
def test_gdpnow_live() -> None:
    assert GdpNowSource().read_observations(select_series(sources=["AtlantaFed"]), start=datetime.date(2025, 1, 1))
