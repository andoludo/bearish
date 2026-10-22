"""Golden (characterization) test for the end-to-end pipeline.

Runs the real Bearish pipeline offline — assets from FinanceDatabase and
InvestPy fixtures, prices from the Tiingo fixture — into a fresh SQLite
database, snapshots every table, and compares against the committed golden
file. Any change in fetching, normalisation, or persistence behaviour shows
up as a diff here.

To regenerate the snapshot after an intentional behaviour change:

    UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py
"""
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pytest
import requests_mock
import time_machine

from bearish.main import Bearish
from bearish.models.api_keys.api_keys import SourceApiKeys
from bearish.models.base import Ticker
from bearish.sources.financedatabase import FinanceDatabaseSource
from bearish.sources.investpy import InvestPySource
from bearish.sources.tiingo import TiingoSource, compute_url
from tests.conftest import DATA_DIR, mock_finance_database_urls, mock_investpy_urls

GOLDEN_PATH = Path(__file__).parent / "data" / "golden" / "pipeline_snapshot.json"

# Volatile columns that legitimately differ between runs.
VOLATILE_COLUMNS = {"created_at", "id"}

# Snapshot-style rows (assets) are stamped with ``date.today()``; freeze the
# clock so the golden file stays valid regardless of when the suite runs.
FROZEN_TODAY = "2026-07-12"


def _snapshot_database(db_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Dump every user table to sorted, JSON-serialisable rows."""
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT IN ('alembic_version', 'sqlite_sequence') ORDER BY name"
            )
        ]
        snapshot: Dict[str, List[Dict[str, Any]]] = {}
        for table in tables:
            rows = [
                {
                    key: row[key]
                    for key in row.keys()  # noqa: SIM118 - sqlite3.Row has no __iter__
                    if key not in VOLATILE_COLUMNS
                }
                for row in connection.execute(f'SELECT * FROM "{table}"')
            ]
            snapshot[table] = sorted(rows, key=lambda r: json.dumps(r, sort_keys=True, default=str))
    return snapshot


def _run_pipeline(db_path: Path) -> None:
    with requests_mock.Mocker() as req:
        mock_finance_database_urls(req, index=True)
        mock_investpy_urls(req)
        req.get(
            compute_url("AAPL", "test-key"),
            text=(DATA_DIR / "tiingo" / "daily.json").read_text(),
        )
        bearish = Bearish(
            path=db_path,
            api_keys=SourceApiKeys(keys={"Tiingo": "test-key"}),
            asset_sources=[FinanceDatabaseSource(), InvestPySource()],
            detailed_asset_sources=[],
            financials_sources=[],
            price_sources=[TiingoSource()],
        )
        bearish.write_assets()
        bearish.write_many_series([Ticker(symbol="AAPL", exchange="NASDAQ")], "max")


@time_machine.travel(FROZEN_TODAY, tick=False)
def test_golden_pipeline(tmp_path: Path) -> None:
    db_path = tmp_path / "bear.db"
    _run_pipeline(db_path)
    snapshot = _snapshot_database(db_path)

    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(json.dumps(snapshot, indent=2, sort_keys=True, default=str))
        pytest.skip(f"golden file regenerated at {GOLDEN_PATH}")

    assert GOLDEN_PATH.exists(), (
        "Golden file missing. Generate it with UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py"
    )
    golden = json.loads(GOLDEN_PATH.read_text())
    assert snapshot == golden, (
        "Pipeline output diverged from the golden snapshot. If the change is "
        "intentional, regenerate with UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py"
    )
