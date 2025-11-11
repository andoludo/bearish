import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep

import pytest
import requests_mock

from bearish.models.base import Ticker
from bearish.models.query.query import AssetQuery, Symbols
from bearish.sources.financial_modelling_prep import (
    read_api,
    compose_url,
    API_URL,
    FmpAssetsSource,
    FmpSource,
)


API_KEY = os.getenv("FMP_API_KEY")

ENDPOINTS = [
    "stock",
    "etf",
    "profile",
    "quote",
    "income-statement",
    "balance-sheet-statement",
    "cash-flow-statement",
    "income-statement-as-reported",
    "balance-sheet-statement-as-reported",
    "cash-flow-statement-as-reported",
    "key-metrics-ttm",
    "ratios-ttm",
    "historical-price-full",
]
PARAMETERS = [
    ("list", None),
    ("list", None),
    ("AAPL", None),
    ("AAPL", None),
    ("AAPL", "annual"),
    ("AAPL", "annual"),
    ("AAPL", "annual"),
    ("AAPL", "annual"),
    ("AAPL", "annual"),
    ("AAPL", "annual"),
    ("AAPL", None),
    ("AAPL", None),
    ("AAPL", None),
]


@pytest.mark.skip(reason="generate data")
def test_fmp_data() -> None:
    for i, endpoint in enumerate(ENDPOINTS):
        path_data = (
            Path(__file__).parents[1].joinpath(f"data/sources/fmp/{endpoint}.json")
        )
        path_data.write_text(
            json.dumps(read_api(API_URL, endpoint, API_KEY, *PARAMETERS[i]), indent=4)
        )
        sleep(1)


@pytest.fixture
def fmp_api_fixture() -> requests_mock.Mocker:
    with requests_mock.Mocker() as req:
        fmp_api(req)
        yield req


def fmp_api(req: requests_mock.Mocker) -> None:
    for i, endpoint in enumerate(ENDPOINTS):
        req.get(
            compose_url(API_URL, endpoint, API_KEY, *PARAMETERS[i]),
            text=Path(__file__)
            .parents[1]
            .joinpath(f"data/sources/fmp/{endpoint}.json")
            .read_text(),
        )


def test_fmp_assets(fmp_api_fixture: requests_mock.Mocker) -> None:
    fmp_assets = FmpAssetsSource()
    fmp_assets.set_api_key(API_KEY)
    assets = fmp_assets._read_assets()
    assert assets
    assert not assets.is_empty()


@pytest.mark.skip("Non supported endpoint")
def test_fmp_assets_integration() -> None:
    fmp_assets = FmpAssetsSource()
    fmp_assets.set_api_key(API_KEY)
    assets = fmp_assets._read_assets()
    assert assets
    assert not assets.is_empty()


def test_fmp_equity(fmp_api_fixture: requests_mock.Mocker) -> None:
    fmp = FmpSource()
    fmp.set_api_key(API_KEY)
    assets = fmp._read_assets(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert assets
    assert not assets.is_empty()


@pytest.mark.skip("requires API key")
def test_fmp_equity_integration() -> None:
    fmp = FmpSource()
    fmp.set_api_key("...")
    assets = fmp._read_assets(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AGFB.BR")]))
    )
    assert assets


def test_fmp_financials(fmp_api_fixture: requests_mock.Mocker) -> None:
    fmp = FmpSource()
    fmp.set_api_key(API_KEY)
    assets = fmp._read_financials(["AAPL"])
    assert assets
    assert not assets[0].is_empty()


def test_fmp_series(fmp_api_fixture: requests_mock.Mocker) -> None:
    fmp = FmpSource()
    fmp.set_api_key(API_KEY)
    prices = fmp.read_series([Ticker(symbol="AAPL", exchange="NASDAQ")], "max")
    assert prices


def test_fmp_series_limited(fmp_api_fixture: requests_mock.Mocker) -> None:
    fmp = FmpSource()
    fmp.set_api_key(API_KEY)
    prices = fmp.read_series([Ticker(symbol="AAPL", exchange="NASDAQ")], "5d")
    assert prices


@pytest.mark.skip("Non supported endpoint")
def test_read_api() -> None:
    response_period = read_api(
        API_URL,
        "historical-price-full",
        API_KEY,
        "AAPL",
        from_="2025-01-01&to=2025-02-10",
    )
    assert response_period["historical"]
    assert len(response_period["historical"]) == 26
