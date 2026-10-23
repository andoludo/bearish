from collections import Counter

from bearish.macro.catalog import CONCEPTS, catalog, select_series, series_by_id
from bearish.macro.countries import COUNTRIES, REGIONS, country_from, iso3_from, priority_countries
from bearish.macro.models import MacroQuery


def test_catalog_is_not_empty_and_ids_are_unique() -> None:
    entries = catalog()
    assert entries
    duplicates = [series_id for series_id, count in Counter(s.series_id for s in entries).items() if count > 1]
    assert not duplicates, f"duplicate series ids: {duplicates}"


def test_every_entry_uses_a_known_concept_and_matching_category() -> None:
    for entry in catalog():
        assert entry.concept in CONCEPTS, entry.series_id
        assert entry.category == CONCEPTS[entry.concept].category, entry.series_id


def test_country_entities_are_known_iso3_codes() -> None:
    known = {country.iso3 for country in COUNTRIES} | set(REGIONS)
    unknown = {entry.entity for entry in catalog() if entry.entity_type in {"country", "region"}} - known
    assert not unknown, unknown


def test_select_series_filters() -> None:
    fra_inflation = select_series(MacroQuery(entities=["fra"], categories=["inflation"]))
    assert fra_inflation
    assert {s.entity for s in fra_inflation} == {"FRA"}
    assert {s.category for s in fra_inflation} == {"inflation"}
    assert select_series(sources=["FRED"])
    assert all(s.source == "FRED" for s in select_series(sources=["FRED"]))
    assert series_by_id()["CURVE_10_2.USA"].source == "FRED"


def test_country_lookup_accepts_codes_and_names() -> None:
    assert iso3_from("US") == "USA"
    assert iso3_from("United States") == "USA"
    assert iso3_from("united kingdom") == "GBR"
    assert iso3_from("Korea, Rep.") == "KOR"
    assert country_from("Atlantis") is None
    assert all(country.priority for country in priority_countries())
    assert {c.iso3 for c in COUNTRIES} >= {"USA", "CAN", "GBR", "DEU", "FRA", "ITA", "JPN", "CHN", "IND"}
