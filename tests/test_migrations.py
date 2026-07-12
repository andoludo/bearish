"""Tests that Alembic migrations upgrade cleanly to head."""
import shutil
import sqlite3
from pathlib import Path

import pytest

from bearish.database.scripts.upgrade import upgrade

BEAR_DB = Path(__file__).parent / "data" / "bear.db"

NEW_SCHEMA_OBJECTS = {
    "filing",
    "pricetarget",
    "analystrecommendation",
}


def _table_names(db_path: Path) -> set:
    with sqlite3.connect(db_path) as conn:
        return {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }


def _columns(db_path: Path, table: str) -> set:
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def test_upgrade_head_on_fresh_database(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    upgrade(f"sqlite:///{db_path}")

    tables = _table_names(db_path)
    assert NEW_SCHEMA_OBJECTS <= tables
    assert "filed_date" in _columns(db_path, "financialmetrics")
    assert "filed_date" in _columns(db_path, "quarterlycashflow")
    assert "is_forward" in _columns(db_path, "earningsdate")
    assert "pe_ratio" not in _columns(db_path, "financialmetrics")
    assert "market_capitalization" not in _columns(db_path, "financialmetrics")
    assert "profit_margin" not in _columns(db_path, "quarterlyfinancialmetrics")


@pytest.mark.lfs
def test_upgrade_head_on_existing_database(tmp_path: Path) -> None:
    """Upgrade a copy of the recorded production-like database to head."""
    if not BEAR_DB.exists() or BEAR_DB.stat().st_size < 1_000_000:
        pytest.skip("bear.db LFS object not available")
    db_path = tmp_path / "bear.db"
    shutil.copy(BEAR_DB, db_path)

    upgrade(f"sqlite:///{db_path}")

    tables = _table_names(db_path)
    assert NEW_SCHEMA_OBJECTS <= tables
    assert "filed_date" in _columns(db_path, "financialmetrics")
    assert "is_forward" in _columns(db_path, "earningsdate")
    assert "pe_ratio" not in _columns(db_path, "financialmetrics")
    # pre-existing data survived the migration
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM price").fetchone()[0]
    assert count > 0
