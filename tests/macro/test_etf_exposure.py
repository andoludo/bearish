import csv
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from bearish.macro.etf_exposure import exposures_for_etf
from bearish.models.assets.etfs import Etf

ETF_CSV = Path(__file__).parents[1] / "data" / "sources" / "financedatabase" / "etfs.csv"


def _etf(
    symbol: str,
    name: str,
    category: Optional[str] = None,
    sector_weightings: Optional[Dict[str, float]] = None,
    long_name: Optional[str] = None,
) -> Etf:
    return Etf(
        symbol=symbol,
        name=name,
        long_name=long_name,
        category=category,
        sector_weightings=sector_weightings,
        source="FinanceDatabase",
    )


def _by_type(etf: Etf) -> Dict[str, Dict[str, float]]:
    result: Dict[str, Dict[str, float]] = {}
    for exposure in exposures_for_etf(etf):
        result.setdefault(exposure.entity_type, {})[exposure.entity] = exposure.weight
    return result


@pytest.mark.parametrize(
    ("name", "category", "expected"),
    [
        ("SPDR Gold Shares", "Commodities Precious Metals", {"commodity": {"GOLD": 1.0}}),
        ("iShares MSCI Japan ETF", "Japan Stock", {"country": {"JPN": 1.0}}),
        ("Vanguard FTSE Emerging Markets ETF", "Diversified Emerging Mkts", {"region": {"EM": 1.0}}),
        ("iShares Core S&P 500 ETF", "Large Blend", {"country": {"USA": 1.0}}),
        ("iShares MSCI China ETF", "China Region", {"country": {"CHN": 1.0}}),
        ("Vanguard FTSE Europe ETF", "Europe Stock", {"region": {"EUR": 1.0}}),
        ("United States Oil Fund", "Commodities Energy", {"country": {"USA": 1.0}, "commodity": {"BRENT": 0.5, "WTI": 0.5}}),
        ("iShares MSCI Brazil ETF", "Latin America Stock", {"country": {"BRA": 1.0}}),
        ("iShares MSCI Pacific ex Japan ETF", "Pacific/Asia ex-Japan Stk", {"region": {"APXJ": 1.0}}),
    ],
)
def test_geo_and_commodity_from_name_and_category(name: str, category: str, expected: Dict[str, Dict[str, float]]) -> None:
    got = _by_type(_etf("X", name, category))
    for entity_type, entities in expected.items():
        assert got.get(entity_type) == pytest.approx(entities), (name, got)


def test_name_wins_over_category_for_geography() -> None:
    got = _by_type(_etf("X", "iShares MSCI Germany ETF", "Europe Stock"))
    assert got["country"] == {"DEU": 1.0}
    assert "region" not in got


def test_sector_from_weightings_and_from_category() -> None:
    weighted = _by_type(
        _etf("XLK", "Technology Select Sector SPDR", "Technology", {"technology": 0.7, "communication_services": 0.3})
    )
    assert weighted["sector"] == pytest.approx({"Information Technology": 0.7, "Communication Services": 0.3})
    by_category = _by_type(_etf("VHT", "Vanguard Health Care ETF", "Health"))
    assert by_category["sector"] == {"Health Care": 1.0}
    percent = _by_type(_etf("X", "Some Fund", None, {"energy": 60.0, "utilities": 40.0}))
    assert percent["sector"] == pytest.approx({"Energy": 0.6, "Utilities": 0.4})


def test_no_false_positives() -> None:
    assert _by_type(_etf("GS", "Goldman Sachs ActiveBeta", "Large Blend")).get("commodity") is None
    assert "country" not in _by_type(_etf("X", "Jordan Capital Growth Fund", "Mid-Cap Growth"))
    assert _by_type(_etf("BND", "VANGUARD BD IDX FD", None)) == {}


def test_fixture_etfs_parse_without_error() -> None:
    with ETF_CSV.open() as handle:
        rows: List[Dict[str, str]] = list(csv.DictReader(handle))
    parsed = 0
    for row in rows:
        etf = _etf(row["symbol"], row["name"], row.get("category") or None)
        exposures = exposures_for_etf(etf)
        assert all(0 < e.weight <= 1 for e in exposures)
        parsed += bool(exposures)
    # The FinanceDatabase ETF fixture has terse legal names; only a few are informative.
    assert parsed >= 2
