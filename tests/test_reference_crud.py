import datetime
from pathlib import Path

import pytest

from bearish.database.crud import BearishDb
from bearish.macro.commodities import COMMODITIES, CountryCommodityExposure
from bearish.macro.links import EtfExposure, SectorCommoditySensitivity, country_references
from bearish.models.sec.insider import InsiderTransaction


@pytest.fixture
def db(tmp_path: Path) -> BearishDb:
    return BearishDb(database_path=tmp_path / "ref.db")


def test_commodities_round_trip_keeps_tuples(db: BearishDb) -> None:
    db.write_commodities(list(COMMODITIES))
    db.write_commodities(list(COMMODITIES))
    stored = {c.code: c for c in db.read_commodities()}
    assert stored["COPPER"].hs_codes == ("7403", "2603")
    assert stored["COPPER"].sectors == ("Materials", "Industrials")
    assert len(stored) == len(COMMODITIES)


def test_country_references_and_equity_country_view(db: BearishDb) -> None:
    refs, aliases = country_references()
    db.write_country_references(refs, aliases)
    assert {r.iso3 for r in db.read_country_references()} >= {"USA", "FRA", "CHN"}
    aliases_frame = db.read_query("SELECT alias, iso3 FROM countryalias WHERE alias IN ('us', 'united kingdom')")
    assert set(aliases_frame["iso3"]) == {"USA", "GBR"}
    assert db.read_query("SELECT * FROM equitycountry").empty


def test_exposure_sensitivity_and_etf_tables(db: BearishDb) -> None:
    db.write_country_exposures(
        [CountryCommodityExposure(country="CHL", commodity="COPPER", direction="export", year=2024, value_usd=1e9, share=0.45)]
    )
    assert db.read_country_exposures(country="CHL")[0].share == 0.45
    assert db.read_country_exposures(commodity="GOLD") == []

    db.write_sector_sensitivities([SectorCommoditySensitivity(sector="Energy", commodity="BRENT", direction=1, strength="high")])
    assert db.read_sector_sensitivities(commodity="BRENT")[0].direction == 1

    db.write_etf_exposures([EtfExposure(symbol="GLD", entity_type="commodity", entity="GOLD", weight=1.0, method="name")])
    assert db.read_etf_exposures(symbol="GLD")[0].entity == "GOLD"
    assert db.read_etf_exposures(entity="GOLD")[0].symbol == "GLD"


def test_insider_transactions_round_trip(db: BearishDb) -> None:
    transaction = InsiderTransaction(
        symbol="AAPL",
        cik="0000320193",
        accession_number="0000320193-26-000001",
        line_no=1,
        filed_date=datetime.date(2026, 2, 3),
        transaction_date=datetime.date(2026, 2, 1),
        reporting_owner="COOK TIMOTHY D",
        owner_relationship="officer",
        officer_title="CEO",
        security_title="Common Stock",
        transaction_code="S",
        acquired_disposed="D",
        shares=1000,
        price=200.0,
        value=200000.0,
        shares_owned_after=5000,
    )
    db.write_insider_transactions([transaction, transaction])
    stored = db.read_insider_transactions(symbol="AAPL")
    assert len(stored) == 1
    assert stored[0].value == 200000.0
    assert db.read_insider_transactions(symbol="MSFT") == []
