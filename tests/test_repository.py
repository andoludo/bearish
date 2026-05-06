"""Tests for the SQLite repository."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from bearish.models import Asset, AssetKind, FinancialStatement, Price
from bearish.repository import SqliteRepository


class TestSqliteRepository:
    def test_creates_schema_on_first_use(self, db_path: Path) -> None:
        SqliteRepository(db_path)
        assert db_path.exists()

    def test_save_and_load_assets(
        self, db_path: Path, sample_asset: Asset
    ) -> None:
        repo = SqliteRepository(db_path)
        repo.save_assets([sample_asset])
        loaded = repo.load_assets()
        assert loaded == [sample_asset]

    def test_save_assets_is_idempotent(
        self, db_path: Path, sample_asset: Asset
    ) -> None:
        repo = SqliteRepository(db_path)
        repo.save_assets([sample_asset])
        repo.save_assets([sample_asset])
        assert len(repo.load_assets()) == 1

    def test_save_assets_updates_existing_record(self, db_path: Path) -> None:
        repo = SqliteRepository(db_path)
        repo.save_assets([Asset(symbol="AAPL", name="Apple", sector="Tech")])
        repo.save_assets([Asset(symbol="AAPL", name="Apple Inc.", sector="Tech")])

        loaded = repo.load_assets()
        assert len(loaded) == 1
        assert loaded[0].name == "Apple Inc."

    def test_load_assets_filters_by_symbols_and_kind(self, db_path: Path) -> None:
        repo = SqliteRepository(db_path)
        repo.save_assets(
            [
                Asset(symbol="AAPL", kind=AssetKind.EQUITY),
                Asset(symbol="SPY", kind=AssetKind.ETF),
                Asset(symbol="MSFT", kind=AssetKind.EQUITY),
            ]
        )

        equities = repo.load_assets(kind=AssetKind.EQUITY)
        assert {a.symbol for a in equities} == {"AAPL", "MSFT"}

        only_aapl = repo.load_assets(symbols=["AAPL"])
        assert [a.symbol for a in only_aapl] == ["AAPL"]

    def test_save_and_load_prices(
        self, db_path: Path, sample_prices: list[Price]
    ) -> None:
        repo = SqliteRepository(db_path)
        repo.save_prices(sample_prices)
        loaded = repo.load_prices("AAPL")
        assert loaded == sample_prices

    def test_save_prices_is_idempotent_per_symbol_and_date(
        self, db_path: Path, sample_prices: list[Price]
    ) -> None:
        repo = SqliteRepository(db_path)
        repo.save_prices(sample_prices)
        repo.save_prices(sample_prices)
        assert len(repo.load_prices("AAPL")) == len(sample_prices)

    def test_load_prices_filters_by_date_range(
        self, db_path: Path, sample_prices: list[Price]
    ) -> None:
        repo = SqliteRepository(db_path)
        repo.save_prices(sample_prices)

        result = repo.load_prices(
            "AAPL",
            start=dt.date(2024, 1, 2),
            end=dt.date(2024, 1, 2),
        )
        assert [p.date for p in result] == [dt.date(2024, 1, 2)]

    def test_save_and_load_statements(
        self, db_path: Path, sample_statement: FinancialStatement
    ) -> None:
        repo = SqliteRepository(db_path)
        repo.save_statements([sample_statement])
        loaded = repo.load_statements("AAPL")
        assert loaded == [sample_statement]

    def test_save_statements_is_idempotent(
        self, db_path: Path, sample_statement: FinancialStatement
    ) -> None:
        repo = SqliteRepository(db_path)
        repo.save_statements([sample_statement])
        repo.save_statements([sample_statement])
        assert len(repo.load_statements("AAPL")) == 1

    def test_empty_lists_are_no_ops(self, db_path: Path) -> None:
        repo = SqliteRepository(db_path)
        repo.save_assets([])
        repo.save_prices([])
        repo.save_statements([])
        assert repo.load_assets() == []
        assert repo.load_prices("AAPL") == []
        assert repo.load_statements("AAPL") == []

    def test_known_symbols_returns_assets_with_recorded_prices(
        self, db_path: Path, sample_prices: list[Price]
    ) -> None:
        repo = SqliteRepository(db_path)
        repo.save_assets([Asset(symbol="AAPL"), Asset(symbol="MSFT")])
        repo.save_prices(sample_prices)
        assert repo.symbols_with_prices() == ["AAPL"]

    def test_can_be_opened_in_memory(self) -> None:
        repo = SqliteRepository(":memory:")
        repo.save_assets([Asset(symbol="AAPL")])
        assert [a.symbol for a in repo.load_assets()] == ["AAPL"]
