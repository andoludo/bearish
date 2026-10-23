import datetime
from pathlib import Path

import pytest
import requests_mock

from bearish.database.crud import BearishDb
from bearish.main import Bearish
from bearish.models.assets.index_members import IndexMember
from bearish.sources.wikipedia_index import (
    INDEX_PAGES,
    IndexPage,
    fetch_index_members,
    normalise_symbol,
    pages_for,
    parse_constituents,
)

DATA = Path(__file__).parents[1] / "data" / "sources" / "wikipedia"
AS_OF = datetime.date(2026, 10, 23)
SP500 = pages_for(["^GSPC"])[0]
DAX = pages_for(["^GDAXI"])[0]
FTSE = pages_for(["^FTSE"])[0]


def test_parse_sp500_uses_constituents_table_and_dash_share_classes() -> None:
    members = parse_constituents((DATA / "sp500.html").read_text(), SP500, AS_OF)
    assert [m.symbol for m in members] == ["MMM", "BRK-B", "NVDA"]  # duplicate and empty rows dropped
    assert all(m.index_symbol == "^GSPC" and m.as_of == AS_OF and m.source == "Wikipedia" for m in members)
    assert members[0].name == "3M"
    assert members[1].name == "Berkshire Hathaway"
    assert all(isinstance(m, IndexMember) for m in members)


def test_parse_dax_falls_back_to_first_table_with_a_ticker_column() -> None:
    members = parse_constituents((DATA / "dax.html").read_text(), DAX, AS_OF)
    assert [m.symbol for m in members] == ["ADS.DE", "SIE.DE", "SAP.DE"]
    assert members[0].name == "Adidas"


def test_parse_ftse_appends_exchange_suffix_once() -> None:
    members = parse_constituents((DATA / "ftse100.html").read_text(), FTSE, AS_OF)
    assert [m.symbol for m in members] == ["III.L", "SHEL.L", "LGEN.L"]
    assert members[1].name == "Shell plc"


def test_parse_without_constituent_table_is_empty() -> None:
    assert parse_constituents("<html><body><p>nothing</p></body></html>", SP500, AS_OF) == []
    assert parse_constituents((DATA / "sp500.html").read_text(), IndexPage(index_symbol="X", url="u", table_id="changes"), AS_OF) == []


def test_normalise_symbol() -> None:
    assert normalise_symbol("NYSE: MMM", SP500) == "MMM"
    assert normalise_symbol("brk.b", SP500) == "BRK-B"
    assert normalise_symbol("ADS.DE", DAX) == "ADS.DE"
    assert normalise_symbol("III", FTSE) == "III.L"
    assert normalise_symbol("III.L", FTSE) == "III.L"
    assert normalise_symbol(float("nan"), SP500) is None
    assert normalise_symbol("not a ticker at all", SP500) is None
    assert normalise_symbol("", SP500) is None


def test_pages_for_rejects_unknown_index() -> None:
    assert pages_for() == list(INDEX_PAGES)
    assert [p.index_symbol for p in pages_for(["^GDAXI", "^GSPC"])] == ["^GDAXI", "^GSPC"]
    with pytest.raises(ValueError, match="No constituent page"):
        pages_for(["^NOPE"])


def test_fetch_skips_failing_pages() -> None:
    with requests_mock.Mocker() as req:
        req.get(SP500.url, text=(DATA / "sp500.html").read_text())
        req.get(DAX.url, status_code=500)
        members = fetch_index_members([SP500, DAX], pause=0)
    assert {m.index_symbol for m in members} == {"^GSPC"}
    assert len(members) == 3


def test_index_members_roundtrip_latest_snapshot(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "m.db")
    older = AS_OF - datetime.timedelta(days=30)
    db.write_index_members(
        [
            IndexMember(index_symbol="^GSPC", symbol="MMM", as_of=older),
            IndexMember(index_symbol="^GSPC", symbol="OLD", as_of=older),
            IndexMember(index_symbol="^GSPC", symbol="MMM", as_of=AS_OF),
            IndexMember(index_symbol="^GSPC", symbol="NEW", as_of=AS_OF),
            IndexMember(index_symbol="^GDAXI", symbol="SAP.DE", as_of=older),
        ]
    )
    latest = db.read_index_members(index_symbol="^GSPC")
    assert sorted(m.symbol for m in latest) == ["MMM", "NEW"]
    assert len(db.read_index_members(index_symbol="^GSPC", latest=False)) == 4
    # a symbol's memberships keep each index's newest snapshot
    assert {m.index_symbol for m in db.read_index_members(symbol="MMM")} == {"^GSPC"}
    assert [m.symbol for m in db.read_index_members(index_symbol="^GDAXI")] == ["SAP.DE"]
    assert db.read_index_members(index_symbol="^FCHI") == []


def test_bearish_get_index_members(tmp_path: Path) -> None:
    bearish = Bearish(
        path=tmp_path / "m.db", asset_sources=[], detailed_asset_sources=[], financials_sources=[], price_sources=[]
    )
    with requests_mock.Mocker() as req:
        req.get(SP500.url, text=(DATA / "sp500.html").read_text())
        assert bearish.get_index_members(["^GSPC"]) == 3
    assert len(bearish._bearish_db.read_index_members(index_symbol="^GSPC")) == 3


@pytest.mark.network
def test_fetch_index_members_live() -> None:
    members = fetch_index_members(pages_for(["^GSPC", "^GDAXI", "^BFX"]))
    by_index = {}
    for member in members:
        by_index.setdefault(member.index_symbol, set()).add(member.symbol)
    assert len(by_index["^GSPC"]) > 490
    assert "NVDA" in by_index["^GSPC"] and "BRK-B" in by_index["^GSPC"]
    assert len(by_index["^GDAXI"]) >= 30 and all(s.endswith(".DE") for s in by_index["^GDAXI"])
    assert len(by_index["^BFX"]) >= 18
