import datetime
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.sipri import (
    SIPRI_FALLBACK_URL,
    SIPRI_PAGE_URL,
    SipriSource,
    newest_workbook_url,
    parse_milex_workbook,
    sipri_iso3,
)


@pytest.fixture
def workbook(macro_data_dir: Path) -> bytes:
    return (macro_data_dir / "sipri" / "SIPRI-Milex-trimmed.xlsx").read_bytes()


def test_newest_workbook_url(macro_data_dir: Path) -> None:
    page = (macro_data_dir / "sipri" / "milex_page_links.html").read_text()
    assert newest_workbook_url(page) == SIPRI_FALLBACK_URL
    two = '<a href="/sites/default/files/SIPRI-Milex-data-1949-2024.xlsx"></a><a href="//x/SIPRI-Milex-data-1949-2026.xlsx"></a>'
    assert newest_workbook_url(two) == "https://x/SIPRI-Milex-data-1949-2026.xlsx"
    assert newest_workbook_url("<html></html>") is None


def test_country_names_resolve() -> None:
    assert sipri_iso3("United States of America") == "USA"
    assert sipri_iso3("Korea, South") == "KOR"
    assert sipri_iso3("Europe") is None
    assert sipri_iso3(None) is None


def test_parse_workbook_units(workbook: bytes) -> None:
    tables = parse_milex_workbook(workbook)
    constant, share = tables["constant"], tables["share_gdp"]
    assert {"USA", "CHN", "RUS", "UKR", "ISR", "KOR", "WLD"} <= set(constant.columns)
    assert "WLD" not in share.columns
    year_2024 = datetime.datetime(2024, 1, 1)
    # constant US$ m.: the US spends ~1 trillion, the world ~2.7 trillion (regional totals are US$ b. x 1000)
    assert 800_000 < constant.loc[year_2024, "USA"] < 1_200_000
    assert 2_000_000 < constant.loc[year_2024, "WLD"] < 3_500_000
    # share of GDP stored in percent, not as a fraction
    assert 2 < share.loc[year_2024, "USA"] < 5
    assert share.loc[year_2024, "UKR"] > 20
    # unavailable markers ("...", "xxx") become missing, never zero
    assert not (constant == 0).any().any()


def test_sipri_source_uses_page_link(workbook: bytes, macro_data_dir: Path) -> None:
    entries = select_series(MacroQuery(entities=["USA", "UKR", "WLD"]), sources=["SIPRI"])
    assert {e.series_id for e in entries} == {"MILEX_USD.USA", "MILEX_USD.UKR", "MILEX_USD.WLD", "MILEX_GDP.USA", "MILEX_GDP.UKR"}
    assert series_by_id()["MILEX_USD.WLD"].frequency == "A"
    with requests_mock.Mocker() as req:
        req.get(SIPRI_PAGE_URL, text=(macro_data_dir / "sipri" / "milex_page_links.html").read_text())
        req.get(SIPRI_FALLBACK_URL, content=workbook)
        observations = SipriSource(pause=0).read_observations(entries, start=datetime.date(2020, 1, 1))
    by_series: dict = {}
    for observation in observations:
        by_series.setdefault(observation.series_id, {})[observation.date] = observation.value
    assert set(by_series) == {e.series_id for e in entries}
    assert min(by_series["MILEX_USD.USA"]) == datetime.date(2020, 1, 1)
    assert by_series["MILEX_GDP.UKR"][datetime.date(2023, 1, 1)] > 30


def test_sipri_falls_back_when_page_fails(workbook: bytes) -> None:
    entries = select_series(MacroQuery(series_ids=["MILEX_USD.USA"]))
    with requests_mock.Mocker() as req:
        req.get(SIPRI_PAGE_URL, status_code=503)
        req.get(re.compile(re.escape(SIPRI_FALLBACK_URL)), content=workbook)
        assert SipriSource(pause=0).read_observations(entries)


@pytest.mark.network
def test_sipri_live() -> None:
    observations = SipriSource().read_observations(
        select_series(MacroQuery(series_ids=["MILEX_GDP.USA"])), start=datetime.date(2020, 1, 1)
    )
    assert observations
    assert all(1 < o.value < 6 for o in observations)
