"""Command-line interface."""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import typer

from bearish.repository import SqliteRepository
from bearish.service import BearishService
from bearish.sources.yfinance_source import YFinanceSource

logger = logging.getLogger(__name__)
app = typer.Typer(help="Fetch financial data and persist it in SQLite.")


def build_service(db_path: Path) -> BearishService:
    """Default factory; tests replace this to inject a fake source."""
    return BearishService(SqliteRepository(db_path), sources=[YFinanceSource()])


@app.command("sync-assets")
def sync_assets(
    db: Path = typer.Argument(..., help="SQLite database path."),
    symbol: list[str] = typer.Option(..., "--symbol", "-s", help="Symbol to fetch."),
) -> None:
    """Pull asset metadata for the given symbols."""
    service = build_service(db)
    assets = service.sync_assets(symbol)
    typer.echo(f"saved {len(assets)} asset(s) to {db}")


@app.command("sync-prices")
def sync_prices(
    db: Path = typer.Argument(...),
    symbol: list[str] = typer.Option(..., "--symbol", "-s"),
    start: dt.datetime | None = typer.Option(None, formats=["%Y-%m-%d"]),
    end: dt.datetime | None = typer.Option(None, formats=["%Y-%m-%d"]),
) -> None:
    """Pull OHLCV history for the given symbols."""
    service = build_service(db)
    result = service.sync_prices(
        symbol,
        start=start.date() if start else None,
        end=end.date() if end else None,
    )
    total = sum(len(v) for v in result.values())
    typer.echo(f"saved {total} price row(s) for {len(result)} symbol(s) to {db}")


@app.command("sync-statements")
def sync_statements(
    db: Path = typer.Argument(...),
    symbol: list[str] = typer.Option(..., "--symbol", "-s"),
) -> None:
    """Pull financial statements for the given symbols."""
    service = build_service(db)
    result = service.sync_statements(symbol)
    total = sum(len(v) for v in result.values())
    typer.echo(f"saved {total} statement(s) for {len(result)} symbol(s) to {db}")


@app.command("sync-all")
def sync_all(
    db: Path = typer.Argument(...),
    symbol: list[str] = typer.Option(..., "--symbol", "-s"),
) -> None:
    """Pull assets, prices, and statements for the given symbols."""
    service = build_service(db)
    service.sync_all(symbol)
    typer.echo(f"sync-all complete for {len(symbol)} symbol(s) → {db}")


if __name__ == "__main__":
    app()
