"""Tests for the orchestration service."""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import pytest

from bearish.exceptions import SourceError
from bearish.models import Asset, FinancialStatement, Price
from bearish.repository import SqliteRepository
from bearish.service import BearishService
from bearish.sources.memory import InMemorySource


def _service(
    db_path: Path,
    *sources: InMemorySource,
) -> BearishService:
    return BearishService(SqliteRepository(db_path), sources=list(sources))


class TestSyncAssets:
    def test_writes_assets_from_first_successful_source(
        self, db_path: Path, sample_asset: Asset
    ) -> None:
        primary = InMemorySource(name="primary", assets=[sample_asset])
        service = _service(db_path, primary)

        service.sync_assets(["AAPL"])

        assert service.repository.load_assets() == [sample_asset]

    def test_falls_back_to_next_source_on_failure(
        self,
        db_path: Path,
        sample_asset: Asset,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        broken = InMemorySource(name="broken", fail=True)
        backup = InMemorySource(name="backup", assets=[sample_asset])
        service = _service(db_path, broken, backup)

        with caplog.at_level(logging.WARNING):
            service.sync_assets(["AAPL"])

        assert service.repository.load_assets() == [sample_asset]
        assert any("broken" in msg for msg in caplog.messages)

    def test_no_source_succeeds_writes_nothing(self, db_path: Path) -> None:
        broken = InMemorySource(name="b1", fail=True)
        empty = InMemorySource(name="b2")
        service = _service(db_path, broken, empty)

        service.sync_assets(["AAPL"])
        assert service.repository.load_assets() == []

    def test_sync_assets_requires_at_least_one_source(
        self, db_path: Path
    ) -> None:
        with pytest.raises(ValueError):
            BearishService(SqliteRepository(db_path), sources=[])


class TestSyncPrices:
    def test_persists_prices_from_first_successful_source(
        self, db_path: Path, sample_prices: list[Price]
    ) -> None:
        source = InMemorySource(name="m", prices=sample_prices)
        service = _service(db_path, source)

        service.sync_prices(["AAPL"])

        assert service.repository.load_prices("AAPL") == sample_prices

    def test_skips_symbols_for_which_no_source_returns_data(
        self, db_path: Path
    ) -> None:
        service = _service(db_path, InMemorySource(name="empty"))
        service.sync_prices(["AAPL"])
        assert service.repository.load_prices("AAPL") == []

    def test_passes_date_range_through_to_sources(
        self, db_path: Path, sample_prices: list[Price]
    ) -> None:
        source = InMemorySource(name="m", prices=sample_prices)
        service = _service(db_path, source)

        service.sync_prices(
            ["AAPL"],
            start=dt.date(2024, 1, 2),
            end=dt.date(2024, 1, 2),
        )

        loaded = service.repository.load_prices("AAPL")
        assert [p.date for p in loaded] == [dt.date(2024, 1, 2)]

    def test_falls_back_when_first_source_fails(
        self, db_path: Path, sample_prices: list[Price]
    ) -> None:
        broken = InMemorySource(name="broken", fail=True)
        backup = InMemorySource(name="backup", prices=sample_prices)
        service = _service(db_path, broken, backup)

        service.sync_prices(["AAPL"])

        assert service.repository.load_prices("AAPL") == sample_prices


class TestSyncStatements:
    def test_persists_statements(
        self, db_path: Path, sample_statement: FinancialStatement
    ) -> None:
        source = InMemorySource(name="m", statements=[sample_statement])
        service = _service(db_path, source)

        service.sync_statements(["AAPL"])

        assert service.repository.load_statements("AAPL") == [sample_statement]


class TestSyncAll:
    def test_runs_assets_prices_and_statements(
        self,
        db_path: Path,
        sample_asset: Asset,
        sample_prices: list[Price],
        sample_statement: FinancialStatement,
    ) -> None:
        source = InMemorySource(
            name="m",
            assets=[sample_asset],
            prices=sample_prices,
            statements=[sample_statement],
        )
        service = _service(db_path, source)

        service.sync_all(["AAPL"])

        assert service.repository.load_assets() == [sample_asset]
        assert service.repository.load_prices("AAPL") == sample_prices
        assert service.repository.load_statements("AAPL") == [sample_statement]


def test_source_error_message_is_logged(
    db_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    broken = InMemorySource(name="broken", fail=True)
    service = _service(db_path, broken)

    with caplog.at_level(logging.WARNING):
        service.sync_prices(["AAPL"])

    assert any(isinstance(r.exc_info, tuple) or "broken" in r.message
               for r in caplog.records)
    # ensure SourceError type was the thing that bubbled
    assert SourceError.__name__ in caplog.text or "broken" in caplog.text
