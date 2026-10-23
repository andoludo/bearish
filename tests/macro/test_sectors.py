from pathlib import Path

import pytest

from bearish.database.crud import BearishDb
from bearish.macro.pipelines.linking import write_sector_references
from bearish.macro.sectors import (
    GICS_INDUSTRIES,
    GICS_SECTORS,
    industry_from,
    is_known_group,
    sector_aliases,
    sector_from,
    sector_of_industry,
)

# Yahoo sector names as yfinance / yahooquery store them in equity.sector.
YAHOO_SECTORS = [
    "Technology", "Consumer Cyclical", "Financial Services", "Healthcare", "Basic Materials",
    "Consumer Defensive", "Communication Services", "Industrials", "Energy", "Real Estate", "Utilities",
]
# Yahoo ETF sector_weightings keys.
YAHOO_WEIGHT_KEYS = [
    "realestate", "consumer_cyclical", "basic_materials", "consumer_defensive", "technology",
    "communication_services", "financial_services", "utilities", "industrials", "energy", "healthcare",
]


@pytest.mark.parametrize("spelling", YAHOO_SECTORS + YAHOO_WEIGHT_KEYS + list(GICS_SECTORS))
def test_every_known_sector_spelling_resolves(spelling: str) -> None:
    assert sector_from(spelling) in GICS_SECTORS


def test_sector_mapping_examples() -> None:
    assert sector_from("Technology") == "Information Technology"
    assert sector_from("Consumer Cyclical") == "Consumer Discretionary"
    assert sector_from("Consumer Defensive") == "Consumer Staples"
    assert sector_from("  basic materials ") == "Materials"
    assert sector_from("Financial Services") == "Financials"
    assert sector_from(None) is None
    assert sector_from("Not a sector") is None


def test_industry_mapping_examples() -> None:
    assert industry_from("Oil & Gas E&P") == "Oil, Gas & Consumable Fuels"
    assert industry_from("Semiconductors") == "Semiconductors & Semiconductor Equipment"
    assert industry_from("Airlines") == "Passenger Airlines"
    assert industry_from("Farm Products") == "Agricultural Products"
    assert industry_from("Oil, Gas & Consumable Fuels") == "Oil, Gas & Consumable Fuels"
    assert sector_of_industry("Banks - Regional") == "Financials"
    assert industry_from("Unknown industry") is None


def test_every_industry_belongs_to_a_sector() -> None:
    assert set(GICS_INDUSTRIES.values()) <= set(GICS_SECTORS)
    assert all(is_known_group(name) for name in GICS_INDUSTRIES)
    assert not is_known_group("Technology")  # a spelling, not a canonical name


def test_aliases_are_unique_per_level() -> None:
    aliases = sector_aliases()
    keys = [(a.alias, a.level) for a in aliases]
    assert len(keys) == len(set(keys))
    assert all(a.alias == a.alias.casefold() for a in aliases)


def test_equity_sector_view_resolves_fixture_assets(bearish_db_with_assets: BearishDb) -> None:
    assert write_sector_references(bearish_db_with_assets) == len(sector_aliases())
    frame = bearish_db_with_assets.read_query(
        "SELECT symbol, sector, industry, gics_sector, gics_industry FROM equitysector"
    )
    assert not frame.empty
    with_sector = frame[frame["sector"].notna()]
    unresolved = with_sector[with_sector["gics_sector"].isna()]["sector"].unique().tolist()
    assert not unresolved, unresolved
    assert set(with_sector["gics_sector"]) <= set(GICS_SECTORS)


def test_sector_aliases_roundtrip(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "s.db")
    write_sector_references(db)
    sectors = db.read_sector_aliases(level="sector")
    assert {a.name for a in sectors} == set(GICS_SECTORS)
    assert {a.name for a in db.read_sector_aliases(level="industry")} == set(GICS_INDUSTRIES)
