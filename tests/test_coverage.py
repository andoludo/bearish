import datetime
from pathlib import Path

from bearish.coverage import COVERED_TABLES, compute_coverage, write_coverage
from bearish.database.crud import BearishDb
from bearish.models.assets.index_members import IndexMember
from bearish.models.coverage import Coverage
from bearish.models.financials.base import Financials
from bearish.models.financials.metrics import FinancialMetrics
from bearish.models.price.price import Price
from bearish.models.sec.filing import Filing

AS_OF = datetime.date(2026, 10, 23)


class YfPrice(Price):
    __source__ = "Yfinance"


def _price(symbol: str, day: int) -> Price:
    return YfPrice(symbol=symbol, date=datetime.date(2026, 10, day), open=1, high=1, low=1, close=1.0, volume=10)


def _populate(db: BearishDb) -> None:
    db.write_series([_price("NVDA", 1), _price("NVDA", 20), _price("AAPL", 5)])
    db.write_financials(
        [
            Financials(
                financial_metrics=[
                    FinancialMetrics(symbol="NVDA", source="SEC", date=datetime.date(2024, 1, 28), net_income=1.0),
                    FinancialMetrics(symbol="NVDA", source="SEC", date=datetime.date(2025, 1, 26), net_income=2.0),
                    FinancialMetrics(symbol="NVDA", source="Yfinance", date=datetime.date(2025, 1, 26), net_income=2.0),
                ]
            )
        ]
    )
    db.write_filings(
        [
            Filing(
                symbol="NVDA", cik="1", form_type="10-K", period_end=datetime.date(2025, 1, 26),
                filed_date=datetime.date(2025, 2, 26), accession_number="a-1",
            )
        ]
    )
    db.write_index_members([IndexMember(index_symbol="^GSPC", symbol="NVDA", as_of=AS_OF)])


def test_compute_coverage_counts_rows_and_date_span(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "c.db")
    _populate(db)
    rows = compute_coverage(db, as_of=AS_OF)
    by_key = {(r.symbol, r.table_name, r.source): r for r in rows}

    price = by_key[("NVDA", "price", "Yfinance")]
    assert (price.first_date, price.last_date, price.rows) == (datetime.date(2026, 10, 1), datetime.date(2026, 10, 20), 2)
    assert by_key[("AAPL", "price", "Yfinance")].rows == 1
    # one row per source
    assert by_key[("NVDA", "financialmetrics", "SEC")].rows == 2
    assert by_key[("NVDA", "financialmetrics", "Yfinance")].rows == 1
    # tables without a source column use the empty string
    filing = by_key[("NVDA", "filing", "")]
    assert filing.first_date == filing.last_date == datetime.date(2025, 2, 26)
    assert by_key[("NVDA", "indexmember", "Wikipedia")].rows == 1
    assert all(r.as_of == AS_OF for r in rows)
    # empty tables produce nothing
    assert not any(r.table_name == "balancesheet" for r in rows)


def test_compute_coverage_restricted_to_symbols(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "c.db")
    _populate(db)
    rows = compute_coverage(db, symbols=["AAPL"], as_of=AS_OF)
    assert {r.symbol for r in rows} == {"AAPL"}
    assert compute_coverage(db, symbols=["O'NEIL"], as_of=AS_OF) == []


def test_write_coverage_full_census_replaces_and_partial_upserts(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "c.db")
    _populate(db)
    written = write_coverage(db)
    assert written == len(db.read_coverage())
    assert {r.table_name for r in db.read_coverage("NVDA")} == {"price", "financialmetrics", "filing", "indexmember"}

    # a stale row disappears on the next full census
    db.write_coverage(
        [Coverage(symbol="GONE", table_name="price", source="X", first_date=AS_OF, last_date=AS_OF, rows=1, as_of=AS_OF)],
        replace=False,
    )
    assert db.read_coverage("GONE")
    write_coverage(db)
    assert db.read_coverage("GONE") == []

    # a partial census keeps the other symbols
    assert write_coverage(db, symbols=["AAPL"]) == 1
    assert db.read_coverage("NVDA")
    assert db.read_coverage(table_name="price") and all(r.table_name == "price" for r in db.read_coverage(table_name="price"))


def test_covered_tables_exist_in_a_fresh_database(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "c.db")
    existing = set(db.read_query("SELECT name FROM sqlite_master WHERE type = 'table'")["name"])
    missing = [t.name for t in COVERED_TABLES if t.name not in existing]
    assert not missing, missing
    assert compute_coverage(db) == []
