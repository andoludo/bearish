"""Tests for the yfinance source.

These tests rely on a fake yfinance module injected into ``sys.modules`` so
they never hit the network. The fake mimics the surface of yfinance that
the source actually uses.
"""
from __future__ import annotations

import datetime as dt
import sys
import types
from typing import Any

import pandas as pd
import pytest

from bearish.exceptions import SourceError


class _FakeTicker:
    def __init__(self, symbol: str, behaviour: dict[str, Any]) -> None:
        self.symbol = symbol
        self._behaviour = behaviour
        self.info = behaviour.get("info", {})
        self.financials = behaviour.get("financials", pd.DataFrame())
        self.balance_sheet = behaviour.get("balance_sheet", pd.DataFrame())
        self.cashflow = behaviour.get("cashflow", pd.DataFrame())

    def history(self, **_: Any) -> pd.DataFrame:
        if self._behaviour.get("raise_history"):
            raise RuntimeError("network down")
        return self._behaviour.get("history", pd.DataFrame())


@pytest.fixture()
def fake_yfinance(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    behaviours: dict[str, dict[str, Any]] = {}

    def _ticker(symbol: str) -> _FakeTicker:
        return _FakeTicker(symbol, behaviours.get(symbol.upper(), {}))

    fake = types.ModuleType("yfinance")
    fake.Ticker = _ticker  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    # the source imports lazily so we just need it in sys.modules.
    return behaviours


def test_fetch_prices_converts_dataframe_to_price_objects(
    fake_yfinance: dict[str, Any],
) -> None:
    from bearish.sources.yfinance_source import YFinanceSource

    df = pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [12.0, 13.0],
            "Low": [9.0, 10.0],
            "Close": [11.0, 12.0],
            "Volume": [1000, 1100],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )
    fake_yfinance["AAPL"] = {"history": df}

    prices = YFinanceSource().fetch_prices("AAPL")
    assert [p.date for p in prices] == [dt.date(2024, 1, 2), dt.date(2024, 1, 3)]
    assert prices[0].close == 11.0
    assert prices[0].source == "yfinance"


def test_fetch_prices_skips_rows_with_nan(fake_yfinance: dict[str, Any]) -> None:
    from bearish.sources.yfinance_source import YFinanceSource

    df = pd.DataFrame(
        {
            "Open": [10.0, float("nan")],
            "High": [12.0, 13.0],
            "Low": [9.0, 10.0],
            "Close": [11.0, 12.0],
            "Volume": [1000, 1100],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )
    fake_yfinance["AAPL"] = {"history": df}

    prices = YFinanceSource().fetch_prices("AAPL")
    assert len(prices) == 1


def test_fetch_prices_wraps_errors_as_source_error(
    fake_yfinance: dict[str, Any],
) -> None:
    from bearish.sources.yfinance_source import YFinanceSource

    fake_yfinance["AAPL"] = {"raise_history": True}
    with pytest.raises(SourceError):
        YFinanceSource().fetch_prices("AAPL")


def test_fetch_assets_uses_info_metadata(fake_yfinance: dict[str, Any]) -> None:
    from bearish.sources.yfinance_source import YFinanceSource

    fake_yfinance["AAPL"] = {
        "info": {
            "shortName": "Apple Inc.",
            "exchange": "NMS",
            "country": "United States",
            "currency": "USD",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "quoteType": "EQUITY",
        }
    }

    assets = YFinanceSource().fetch_assets(["AAPL"])
    assert len(assets) == 1
    asset = assets[0]
    assert asset.symbol == "AAPL"
    assert asset.name == "Apple Inc."
    assert asset.sector == "Technology"


def test_fetch_assets_returns_empty_when_no_symbols_given() -> None:
    from bearish.sources.yfinance_source import YFinanceSource

    assert YFinanceSource().fetch_assets(None) == []
    assert YFinanceSource().fetch_assets([]) == []


def test_fetch_statements_pivots_dataframes(fake_yfinance: dict[str, Any]) -> None:
    from bearish.sources.yfinance_source import YFinanceSource

    period_end = pd.Timestamp("2024-12-31")
    fake_yfinance["AAPL"] = {
        "financials": pd.DataFrame(
            {period_end: {"Total Revenue": 400.0, "Net Income": 100.0}}
        ),
        "balance_sheet": pd.DataFrame(
            {period_end: {"Total Assets": 350.0, "Total Liab": 280.0}}
        ),
        "cashflow": pd.DataFrame(
            {period_end: {"Operating Cash Flow": 110.0}}
        ),
    }

    statements = YFinanceSource().fetch_statements("AAPL")
    assert len(statements) == 1
    s = statements[0]
    assert s.symbol == "AAPL"
    assert s.period_end == dt.date(2024, 12, 31)
    assert s.revenue == 400.0
    assert s.net_income == 100.0
    assert s.total_assets == 350.0
    assert s.total_liabilities == 280.0
    assert s.operating_cash_flow == 110.0
