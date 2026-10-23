import datetime
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.ofac import (
    SDN_ENHANCED_URL,
    OfacSource,
    monthly_counts,
    ofac_iso3,
    parse_designations,
)


@pytest.fixture
def sdn_xml(macro_data_dir: Path) -> bytes:
    return (macro_data_dir / "ofac" / "SDN_ENHANCED_trimmed.xml").read_bytes()


def test_country_names_resolve() -> None:
    assert ofac_iso3("Russia") == "RUS"
    assert ofac_iso3("Iran") == "IRN"
    assert ofac_iso3("Korea, North") == "PRK"
    assert ofac_iso3("United Arab Emirates") == "ARE"
    assert ofac_iso3(None) is None
    assert ofac_iso3("Atlantis") is None


def test_parse_designations_dates_and_country_attribution(sdn_xml: bytes) -> None:
    designations = parse_designations(sdn_xml)
    assert len(designations) == 47
    assert designations["date"].min() == datetime.date(1986, 12, 10)
    russia_2022 = designations[designations["date"].map(lambda d: d.strftime("%Y-%m")) == "2022-03"]
    assert len(russia_2022) == 25
    assert all("RUS" in countries for countries in russia_2022["countries"])
    # Entities without an address country fall back to nationality features or the program target.
    assert all(countries for countries in designations["countries"])


def test_monthly_counts_fill_gaps_with_zero(sdn_xml: bytes) -> None:
    counts = monthly_counts(parse_designations(sdn_xml), end=datetime.date(2026, 10, 23))
    assert counts.index.min().date() == datetime.date(1986, 12, 1)
    assert counts.index.max().date() == datetime.date(2026, 10, 1)
    assert counts.loc["2022-03-01", "RUS"] == 25
    assert counts.loc["2022-03-01", "WLD"] >= 25
    assert counts.loc["2020-01-01", "WLD"] == 0
    assert counts["WLD"].sum() == 47  # every entity counted once worldwide


def test_ofac_source_emits_monthly_series(sdn_xml: bytes) -> None:
    entries = select_series(sources=["OFAC"])
    assert series_by_id()["SANCTIONS_NEW.WLD"].entity_type == "global"
    assert "SANCTIONS_NEW.RUS" in {e.series_id for e in entries}
    with requests_mock.Mocker() as req:
        req.get(SDN_ENHANCED_URL, content=sdn_xml)
        observations = OfacSource(pause=0).read_observations(
            select_series(MacroQuery(series_ids=["SANCTIONS_NEW.RUS", "SANCTIONS_NEW.WLD", "SANCTIONS_NEW.CHN"])),
            start=datetime.date(2022, 1, 1),
        )
    by_series: dict = {}
    for observation in observations:
        by_series.setdefault(observation.series_id, {})[observation.date] = observation.value
    assert by_series["SANCTIONS_NEW.RUS"][datetime.date(2022, 3, 1)] == 25
    assert by_series["SANCTIONS_NEW.RUS"][datetime.date(2022, 4, 1)] == 0
    assert min(by_series["SANCTIONS_NEW.WLD"]) == datetime.date(2022, 1, 1)
    assert sum(by_series["SANCTIONS_NEW.CHN"].values()) == 6


@pytest.mark.network
def test_ofac_live() -> None:
    observations = OfacSource().read_observations(
        select_series(MacroQuery(series_ids=["SANCTIONS_NEW.RUS"])), start=datetime.date(2022, 1, 1)
    )
    by_date = {o.date: o.value for o in observations}
    assert by_date[datetime.date(2022, 3, 1)] > 100
