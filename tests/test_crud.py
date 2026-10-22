import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import event

from bearish.database.crud import BearishDb
from bearish.models.price.price import Price

# SQLite's compiled default since 3.32; distro builds (e.g. Ubuntu) raise it to
# 250000, which hides the bug locally but not on python.org / uv Pythons.
DEFAULT_SQLITE_MAX_VARIABLES = 32766


def _cap_sqlite_variables(db: BearishDb, limit: int) -> None:
    @event.listens_for(db._engine, "connect")
    def _set_limit(dbapi_connection: sqlite3.Connection, _: Any) -> None:
        dbapi_connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, limit)

    db._engine.dispose()


def test_write_series_respects_sqlite_variable_limit(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "bear.db")
    _cap_sqlite_variables(db, DEFAULT_SQLITE_MAX_VARIABLES)
    start = date(2000, 1, 1)
    prices = [
        Price(
            symbol="AAPL",
            source="Tiingo",
            date=start + timedelta(days=offset),
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1.0,
        )
        for offset in range(5_000)
    ]

    db.write_series(prices)

    stored = db.read_query("SELECT COUNT(*) AS n FROM price")
    assert stored["n"].iloc[0] == len(prices)
