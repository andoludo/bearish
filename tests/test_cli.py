"""Tests for the CLI."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import bearish.cli as cli_module
from bearish.cli import app
from bearish.models import Asset, AssetKind
from bearish.repository import SqliteRepository
from bearish.service import BearishService
from bearish.sources.memory import InMemorySource


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def fake_service_factory(monkeypatch: pytest.MonkeyPatch) -> list[BearishService]:
    """Replace cli.build_service with a factory using an InMemorySource."""
    captured: list[BearishService] = []
    sources = [
        InMemorySource(
            name="m",
            assets=[Asset(symbol="AAPL", name="Apple", kind=AssetKind.EQUITY)],
        )
    ]

    def factory(db: Path) -> BearishService:
        service = BearishService(SqliteRepository(db), sources=sources)
        captured.append(service)
        return service

    monkeypatch.setattr(cli_module, "build_service", factory)
    return captured


def test_sync_assets_command_writes_to_db(
    runner: CliRunner, tmp_path: Path, fake_service_factory: list[BearishService]
) -> None:
    db = tmp_path / "db.sqlite"
    result = runner.invoke(app, ["sync-assets", str(db), "--symbol", "AAPL"])
    assert result.exit_code == 0, result.output

    repo = SqliteRepository(db)
    assets = repo.load_assets()
    assert [a.symbol for a in assets] == ["AAPL"]


def test_sync_assets_prints_count(
    runner: CliRunner, tmp_path: Path, fake_service_factory: list[BearishService]
) -> None:
    result = runner.invoke(
        app, ["sync-assets", str(tmp_path / "db.sqlite"), "--symbol", "AAPL"]
    )
    assert "1" in result.output


def test_top_level_help_lists_commands(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("sync-assets", "sync-prices", "sync-statements", "sync-all"):
        assert cmd in result.output
