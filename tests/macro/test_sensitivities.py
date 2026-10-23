from collections import Counter
from pathlib import Path

from bearish.database.crud import BearishDb
from bearish.macro.commodities import commodities_by_code
from bearish.macro.sectors import is_known_group
from bearish.macro.sensitivities import SECTOR_COMMODITY_SENSITIVITIES, write_sector_sensitivities

def test_sensitivities_reference_known_sectors_and_commodities() -> None:
    assert SECTOR_COMMODITY_SENSITIVITIES
    unknown_sectors = {s.sector for s in SECTOR_COMMODITY_SENSITIVITIES if not is_known_group(s.sector)}
    assert not unknown_sectors, unknown_sectors
    unknown_commodities = {s.commodity for s in SECTOR_COMMODITY_SENSITIVITIES} - set(commodities_by_code())
    assert not unknown_commodities, unknown_commodities
    duplicates = [k for k, n in Counter((s.sector, s.commodity) for s in SECTOR_COMMODITY_SENSITIVITIES).items() if n > 1]
    assert not duplicates, duplicates
    assert all(s.rationale for s in SECTOR_COMMODITY_SENSITIVITIES)


def test_required_pairs_present() -> None:
    signs = {(s.sector, s.commodity): s.direction for s in SECTOR_COMMODITY_SENSITIVITIES}
    assert signs[("Energy", "BRENT")] == 1
    assert signs[("Passenger Airlines", "BRENT")] == -1
    assert signs[("Metals & Mining", "COPPER")] == 1
    assert signs[("Utilities", "NATGAS_HH")] == -1
    assert signs[("Consumer Staples", "WHEAT")] == -1
    assert signs[("Chemicals", "NATGAS_HH")] == -1
    assert signs[("Automobiles", "PALLADIUM")] == -1
    assert signs[("Agricultural Products", "CORN")] == 1


def test_write_sector_sensitivities(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "s.db")
    assert write_sector_sensitivities(db) == len(SECTOR_COMMODITY_SENSITIVITIES)
    assert len(db.read_sector_sensitivities(commodity="BRENT")) >= 5
