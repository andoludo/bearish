"""SQLite-backed persistence for the common data model.

A thin wrapper around the standard-library ``sqlite3`` module — no ORM,
no Alembic. The schema is created on first use and upserts use
``INSERT ... ON CONFLICT DO UPDATE`` so calls are idempotent.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from bearish.models import Asset, AssetKind, FinancialStatement, Period, Price

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    symbol   TEXT PRIMARY KEY,
    name     TEXT,
    exchange TEXT,
    country  TEXT,
    currency TEXT,
    kind     TEXT NOT NULL,
    sector   TEXT,
    industry TEXT
);

CREATE TABLE IF NOT EXISTS prices (
    symbol  TEXT NOT NULL,
    date    TEXT NOT NULL,
    open    REAL NOT NULL,
    high    REAL NOT NULL,
    low     REAL NOT NULL,
    close   REAL NOT NULL,
    volume  REAL NOT NULL,
    source  TEXT NOT NULL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS statements (
    symbol             TEXT NOT NULL,
    period_end         TEXT NOT NULL,
    period             TEXT NOT NULL,
    source             TEXT NOT NULL,
    revenue            REAL,
    net_income         REAL,
    total_assets       REAL,
    total_liabilities  REAL,
    operating_cash_flow REAL,
    PRIMARY KEY (symbol, period_end, period)
);
"""


class SqliteRepository:
    """Persist and query the common data model in a SQLite database."""

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        # ``:memory:`` databases live only as long as their connection, so for
        # that one case we keep a single persistent connection.
        self._shared: sqlite3.Connection | None = (
            self._open() if self._path == ":memory:" else None
        )
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self._shared is not None:
            yield self._shared
            self._shared.commit()
            return
        conn = self._open()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save_assets(self, assets: Sequence[Asset]) -> None:
        if not assets:
            return
        rows = [
            (
                a.symbol,
                a.name,
                a.exchange,
                a.country,
                a.currency,
                a.kind.value,
                a.sector,
                a.industry,
            )
            for a in assets
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO assets
                    (symbol, name, exchange, country, currency, kind, sector, industry)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name=excluded.name,
                    exchange=excluded.exchange,
                    country=excluded.country,
                    currency=excluded.currency,
                    kind=excluded.kind,
                    sector=excluded.sector,
                    industry=excluded.industry
                """,
                rows,
            )

    def load_assets(
        self,
        symbols: Iterable[str] | None = None,
        kind: AssetKind | None = None,
    ) -> list[Asset]:
        clauses, params = [], []
        if symbols is not None:
            wanted = [s.upper() for s in symbols]
            placeholders = ",".join("?" * len(wanted))
            clauses.append(f"symbol IN ({placeholders})")
            params.extend(wanted)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind.value)

        sql = "SELECT * FROM assets"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY symbol"

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            Asset(
                symbol=r["symbol"],
                name=r["name"],
                exchange=r["exchange"],
                country=r["country"],
                currency=r["currency"],
                kind=AssetKind(r["kind"]),
                sector=r["sector"],
                industry=r["industry"],
            )
            for r in rows
        ]

    def save_prices(self, prices: Sequence[Price]) -> None:
        if not prices:
            return
        rows = [
            (
                p.symbol,
                p.date.isoformat(),
                p.open,
                p.high,
                p.low,
                p.close,
                p.volume,
                p.source,
            )
            for p in prices
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO prices
                    (symbol, date, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume,
                    source=excluded.source
                """,
                rows,
            )

    def load_prices(
        self,
        symbol: str,
        start: dt.date | None = None,
        end: dt.date | None = None,
    ) -> list[Price]:
        clauses = ["symbol = ?"]
        params: list[object] = [symbol.upper()]
        if start is not None:
            clauses.append("date >= ?")
            params.append(start.isoformat())
        if end is not None:
            clauses.append("date <= ?")
            params.append(end.isoformat())

        sql = "SELECT * FROM prices WHERE " + " AND ".join(clauses) + " ORDER BY date"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            Price(
                symbol=r["symbol"],
                date=dt.date.fromisoformat(r["date"]),
                open=r["open"],
                high=r["high"],
                low=r["low"],
                close=r["close"],
                volume=r["volume"],
                source=r["source"],
            )
            for r in rows
        ]

    def save_statements(self, statements: Sequence[FinancialStatement]) -> None:
        if not statements:
            return
        rows = [
            (
                s.symbol,
                s.period_end.isoformat(),
                s.period,
                s.source,
                s.revenue,
                s.net_income,
                s.total_assets,
                s.total_liabilities,
                s.operating_cash_flow,
            )
            for s in statements
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO statements
                    (symbol, period_end, period, source,
                     revenue, net_income, total_assets,
                     total_liabilities, operating_cash_flow)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, period_end, period) DO UPDATE SET
                    source=excluded.source,
                    revenue=excluded.revenue,
                    net_income=excluded.net_income,
                    total_assets=excluded.total_assets,
                    total_liabilities=excluded.total_liabilities,
                    operating_cash_flow=excluded.operating_cash_flow
                """,
                rows,
            )

    def load_statements(
        self, symbol: str, period: Period | None = None
    ) -> list[FinancialStatement]:
        clauses = ["symbol = ?"]
        params: list[object] = [symbol.upper()]
        if period is not None:
            clauses.append("period = ?")
            params.append(period)

        sql = (
            "SELECT * FROM statements WHERE "
            + " AND ".join(clauses)
            + " ORDER BY period_end"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            FinancialStatement(
                symbol=r["symbol"],
                period_end=dt.date.fromisoformat(r["period_end"]),
                period=r["period"],
                source=r["source"],
                revenue=r["revenue"],
                net_income=r["net_income"],
                total_assets=r["total_assets"],
                total_liabilities=r["total_liabilities"],
                operating_cash_flow=r["operating_cash_flow"],
            )
            for r in rows
        ]

    def symbols_with_prices(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT symbol FROM prices ORDER BY symbol"
            ).fetchall()
        return [r["symbol"] for r in rows]
