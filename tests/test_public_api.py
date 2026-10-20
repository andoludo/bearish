"""Regression tests for the public API surface.

The bullish package (https://github.com/andoludo/bullish) depends on the
imports below. This module fails loudly if any of them disappear or move,
so refactoring bearish cannot silently break its downstream consumers.
"""
import datetime
import tempfile
from pathlib import Path


def test_bullish_import_contract() -> None:
    from bearish.database.crud import BearishDb  # noqa: F401
    from bearish.database.schemas import (  # noqa: F401
        EarningsDateORM,
        EquityORM,
        PriceORM,
    )
    from bearish.interface.interface import BearishDbBase  # noqa: F401
    from bearish.main import Bearish  # noqa: F401
    from bearish.models.assets.equity import BaseEquity  # noqa: F401
    from bearish.models.base import (  # noqa: F401
        DataSourceBase,
        FinancialsTracker,
        PriceTracker,
        Ticker,
        TrackerQuery,
    )
    from bearish.models.financials.balance_sheet import (  # noqa: F401
        BalanceSheet,
        QuarterlyBalanceSheet,
    )
    from bearish.models.financials.base import (  # noqa: F401
        Financials,
        FinancialsWithDate,
    )
    from bearish.models.financials.cash_flow import (  # noqa: F401
        CashFlow,
        QuarterlyCashFlow,
    )
    from bearish.models.financials.metrics import (  # noqa: F401
        FinancialMetrics,
        QuarterlyFinancialMetrics,
    )
    from bearish.models.price.price import Price  # noqa: F401
    from bearish.models.price.prices import Prices  # noqa: F401
    from bearish.models.query.query import AssetQuery, Symbols  # noqa: F401
    from bearish.models.sec.sec import Secs  # noqa: F401
    from bearish.types import (  # noqa: F401
        SeriesLength,
        Sources,
        TickerOnlySources,
    )


def test_star_import_of_schemas() -> None:
    # bullish/utils/checks.py does `from bearish.database.schemas import *`
    namespace: dict = {}
    exec("from bearish.database.schemas import *", namespace)
    assert any(name.endswith("ORM") for name in namespace)


def test_bearish_db_is_subclassable_with_engine_override() -> None:
    # BullishDb subclasses BearishDb, declares `database_path: Path`,
    # and overrides the `_engine` cached property.
    from bearish.database.crud import BearishDb

    assert "database_path" in BearishDb.model_fields
    assert hasattr(BearishDb, "_engine")


def test_fresh_database_is_created_via_alembic() -> None:
    import sqlite3

    from bearish.database.crud import BearishDb

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "bear.db"
        db = BearishDb(database_path=db_path)
        _ = db._engine
        with sqlite3.connect(db_path) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type=\'table\'"
                )
            }
    assert "alembic_version" in tables
    for expected in ("equity", "price", "financialmetrics", "balancesheet",
                     "cashflow", "pricetracker", "financialstracker", "sources"):
        assert expected in tables, f"missing table {expected}"


def test_price_roundtrip_through_database() -> None:
    from bearish.database.crud import BearishDb
    from bearish.models.base import Ticker
    from bearish.models.price.price import Price
    from bearish.models.query.query import AssetQuery, Symbols

    price = Price(
        symbol="AAPL",
        source="Yfinance",
        date=datetime.date.today(),
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1_000_000,
    )
    with tempfile.TemporaryDirectory() as tmp:
        db = BearishDb(database_path=Path(tmp) / "bear.db")
        db.write_series([price])
        series = db.read_series(
            AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")])), months=1
        )
    assert series
    assert series[0].symbol == "AAPL"
    assert series[0].close == 104.0


def test_tracker_roundtrip_through_database() -> None:
    from bearish.database.crud import BearishDb
    from bearish.models.base import PriceTracker, TrackerQuery

    tracker = PriceTracker(
        symbol="AAPL", source="Yfinance", exchange="NASDAQ",
        date=datetime.date(2024, 1, 2),
    )
    with tempfile.TemporaryDirectory() as tmp:
        db = BearishDb(database_path=Path(tmp) / "bear.db")
        db.write_trackers([tracker])
        trackers = db.read_tracker(TrackerQuery(), PriceTracker)
    assert trackers


def test_cli_exposes_master_commands() -> None:
    from typer.testing import CliRunner

    from bearish.main import app

    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("run", "tickers", "prices", "financials", "sec", "update"):
        assert command in result.output, f"missing CLI command {command}"
