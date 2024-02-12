import json
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture(scope="session")
def screener_investing():
    return Path(__file__).parent / "data" / "screener_investing.json"


@pytest.fixture(scope="session")
def screener_trading():
    return Path(__file__).parent / "data" / "screener_trading.json"

@pytest.fixture(scope="session")
def ticker_trading():
    return json.loads((Path(__file__).parent / "data" / "ticker_trading.json").read_text())






# @pytest.fixture(scope = "session")
# def trading_file_path():
#  return Path("/home/aan/Documents/stocks/tests/scrapers/output/trading_screener_2024_01_24_09_33.csv")
@pytest.fixture(scope="session")
def investing_records(screener_investing):
    return json.loads(screener_investing.read_text())


@pytest.fixture(scope="session")
def trading_records(screener_trading):
    return json.loads(screener_trading.read_text())


@pytest.fixture(scope="session")
def investing_record(investing_records):
    return investing_records[0]


@pytest.fixture(scope="session")
def trading_record(trading_records):
    return trading_records[0]
