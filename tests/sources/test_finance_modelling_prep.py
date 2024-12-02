import json
from pathlib import Path
from time import sleep

import pytest
import requests_mock

from bearish.models.query.query import AssetQuery, Symbols
from bearish.sources.financial_modelling_prep import (
    read_api,
    compose_url,
    API_URL,
    FmpAssetsSource,
    FmpSource,
)


API_KEY = "test"

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


def test_fmp_equity(fmp_api_fixture: requests_mock.Mocker) -> None:
    fmp = FmpSource()
    fmp.set_api_key(API_KEY)
    assets = fmp._read_assets(AssetQuery(symbols=Symbols(equities=["AAPL"])))
    assert assets
    assert not assets.is_empty()


@pytest.mark.skip("requires API key")
def test_fmp_equity_integration() -> None:
    fmp = FmpSource()
    fmp.set_api_key("...")
    assets = fmp._read_assets(AssetQuery(symbols=Symbols(equities=["AGFB.BR"])))


def test_fmp_financials(fmp_api_fixture: requests_mock.Mocker) -> None:
    fmp = FmpSource()
    fmp.set_api_key(API_KEY)
    assets = fmp._read_financials("AAPL")
    assert assets
    assert not assets.is_empty()


def test_fmp_series(fmp_api_fixture: requests_mock.Mocker) -> None:
    fmp = FmpSource()
    fmp.set_api_key(API_KEY)
    prices = fmp.read_series("AAPL", "full")
    assert prices
