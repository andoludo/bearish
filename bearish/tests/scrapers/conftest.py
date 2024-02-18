import json
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def screener_investing() -> Path:
    return Path(__file__).parent / "data" / "screener_investing.json"


@pytest.fixture(scope="session")
def screener_trading() -> Path:
    return Path(__file__).parent / "data" / "screener_trading.json"


@pytest.fixture(scope="session")
def ticker_trading() -> Path:
    return json.loads(
        (Path(__file__).parent / "data" / "ticker_trading.json").read_text()
    )


@pytest.fixture(scope="session")
def investing_records(screener_investing: Path) -> list[dict]:
    return json.loads(screener_investing.read_text())


@pytest.fixture(scope="session")
def trading_records(screener_trading: Path) -> list[dict]:
    return json.loads(screener_trading.read_text())


@pytest.fixture(scope="session")
def investing_record(investing_records: list[dict]) -> dict:
    return investing_records[0]


@pytest.fixture(scope="session")
def trading_record(trading_records: list[dict]) -> dict:
    return trading_records[0]
