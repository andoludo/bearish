"""Shared pytest fixtures."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from bearish.models import Asset, AssetKind, FinancialStatement, Price


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "bearish.db"


@pytest.fixture()
def sample_asset() -> Asset:
    return Asset(
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        country="US",
        currency="USD",
        kind=AssetKind.EQUITY,
        sector="Technology",
        industry="Consumer Electronics",
    )


@pytest.fixture()
def sample_prices() -> list[Price]:
    base = dt.date(2024, 1, 1)
    return [
        Price(
            symbol="AAPL",
            date=base + dt.timedelta(days=i),
            open=100 + i,
            high=105 + i,
            low=99 + i,
            close=104 + i,
            volume=1_000_000 + i,
            source="memory",
        )
        for i in range(3)
    ]


@pytest.fixture()
def sample_statement() -> FinancialStatement:
    return FinancialStatement(
        symbol="AAPL",
        period_end=dt.date(2024, 12, 31),
        period="annual",
        source="memory",
        revenue=400_000_000_000,
        net_income=100_000_000_000,
        total_assets=350_000_000_000,
        total_liabilities=280_000_000_000,
        operating_cash_flow=110_000_000_000,
    )
