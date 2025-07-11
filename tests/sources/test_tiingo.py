import json
import os
from pathlib import Path

import pytest
import requests_mock

from bearish.models.base import Ticker
from bearish.sources.tiingo import TiingoSource, compute_url, read_api
from tests.sources.test_finance_modelling_prep import API_KEY

API_KEY = os.environ.get("TIINGO_API_KEY")


@pytest.mark.skip(reason="generate data")
def test_tiingo_data():
    path_data = Path(__file__).parents[1].joinpath("data/sources/tiingo/daily.json")
    path_data.write_text(json.dumps(read_api(API_KEY, "AAPL"), indent=4))


@pytest.fixture
def tiingo_api_fixture() -> requests_mock.Mocker:
    with requests_mock.Mocker() as req:
        req.get(
            compute_url("AAPL", "test"),
            text=Path(__file__)
            .parents[1]
            .joinpath("data/sources/tiingo/daily.json")
            .read_text(),
        )
        yield req


def test_tiingo_read_series(tiingo_api_fixture: requests_mock.Mocker) -> None:
    tiingo = TiingoSource()
    tiingo.set_api_key("test")
    prices = tiingo.read_series([Ticker(symbol="AAPL", exchange="NASDAQ")], "max")
    assert prices


def test_tiingo_read_series_5d() -> None:
    tiingo = TiingoSource()
    tiingo.set_api_key(API_KEY)
    prices = tiingo.read_series([Ticker(symbol="AAPL", exchange="NASDAQ")], "5d")
    assert prices
