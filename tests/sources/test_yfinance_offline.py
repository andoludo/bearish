"""Offline tests for the yfinance source adapters (no network access).

Live-API behaviour is covered in test_yfinance.py (network-marked); these
tests exercise the mapping/validation layer against fake payloads.
"""
import datetime

import pandas as pd
import pytest

import bearish.sources.yfinance as yfinance_source
from bearish.sources.yfinance import yFinancePrice, yFinanceSource


def _download_frame(ticker: str, with_actions: bool) -> pd.DataFrame:
    fields = ["Open", "High", "Low", "Close", "Volume"]
    rows = {
        "Open": [10.0, 11.0],
        "High": [12.0, 13.0],
        "Low": [9.0, 10.0],
        "Close": [11.0, 12.0],
        "Volume": [1000.0, 1100.0],
    }
    if with_actions:
        fields += ["Dividends", "Stock Splits"]
        rows["Dividends"] = [0.0, 0.25]
        rows["Stock Splits"] = [0.0, 4.0]
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    columns = pd.MultiIndex.from_product([[ticker], fields])
    frame = pd.DataFrame(index=index, columns=columns, dtype=float)
    for field, values in rows.items():
        frame[(ticker, field)] = values
    frame.index.name = "Date"
    return frame


@pytest.fixture()
def fake_download(monkeypatch):
    """Patch yf.download inside the source module; records call kwargs."""
    state = {"frame": None, "kwargs": []}

    def _download(tickers, **kwargs):
        state["kwargs"].append(kwargs)
        return state["frame"]

    monkeypatch.setattr(yfinance_source.yf, "download", _download)
    return state


def test_read_series_maps_dividends_and_stock_splits(fake_download) -> None:
    fake_download["frame"] = _download_frame("AAPL", with_actions=True)
    prices = yFinanceSource(pause=0)._read_series(["AAPL"], "5d")

    assert len(prices) == 2
    assert prices[1].dividends == 0.25
    assert prices[1].stock_splits == 4.0
    assert prices[0].dividends == 0.0


def test_read_series_requests_actions(fake_download) -> None:
    fake_download["frame"] = _download_frame("AAPL", with_actions=True)
    yFinanceSource(pause=0)._read_series(["AAPL"], "5d")

    assert fake_download["kwargs"], "yf.download was not called"
    assert all(kwargs.get("actions") is True for kwargs in fake_download["kwargs"])


def test_read_series_without_action_columns_still_validates(fake_download) -> None:
    # Recorded fixtures (and some providers) lack the action columns entirely;
    # rows must still validate with dividends/stock_splits = None.
    fake_download["frame"] = _download_frame("AAPL", with_actions=False)
    prices = yFinanceSource(pause=0)._read_series(["AAPL"], "5d")

    assert len(prices) == 2
    assert all(price.dividends is None for price in prices)
    assert all(price.stock_splits is None for price in prices)


def test_price_alias_maps_action_columns_directly() -> None:
    price = yFinancePrice(
        **{
            "symbol": "AAPL",
            "Date": datetime.date(2024, 1, 2),
            "Open": 10.0,
            "High": 12.0,
            "Low": 9.0,
            "Close": 11.0,
            "Volume": 1000.0,
            "Dividends": 0.24,
            "Stock Splits": 2.0,
        }
    )
    assert price.dividends == 0.24
    assert price.stock_splits == 2.0


class _FakeEarningsTicker:
    """Mimics the yf.Ticker surface used by yFinanceEarningsDate.from_ticker."""

    def __init__(self, frame: pd.DataFrame, symbol: str = "AAPL") -> None:
        self.ticker = symbol
        self.earnings_dates = frame


def _earnings_frame(extra_columns: bool = False) -> pd.DataFrame:
    import json
    from pathlib import Path

    fixture = json.loads(
        Path(__file__)
        .parents[1]
        .joinpath("data/sources/yfinance/earnings_dates_AAPL.json")
        .read_text()
    )
    rows = fixture["rows"]
    frame = pd.DataFrame(rows).set_index(pd.to_datetime([r["date"] for r in rows]))
    frame = frame.drop(columns=["date"])
    # one future row, dated dynamically so the test never rots
    future = pd.Timestamp(datetime.date.today() + datetime.timedelta(days=90))
    frame.loc[future] = {"EPS Estimate": 3.1, "Reported EPS": None, "Surprise(%)": None}
    if extra_columns:
        frame["Revenue Estimate"] = 1.0e11
        frame["Reported Revenue"] = 1.1e11
    return frame


def test_earnings_dates_sets_is_forward() -> None:
    from bearish.sources.yfinance import yFinanceEarningsDate

    rows = yFinanceEarningsDate.from_ticker(_FakeEarningsTicker(_earnings_frame()))
    assert len(rows) == 4
    forward = [r for r in rows if r.is_forward]
    past = [r for r in rows if not r.is_forward]
    assert len(forward) == 1
    assert forward[0].eps_reported is None
    assert len(past) == 3
    assert all(r.eps_estimate is not None for r in rows)


def test_earnings_dates_maps_revenue_columns_when_present() -> None:
    from bearish.sources.yfinance import yFinanceEarningsDate

    rows = yFinanceEarningsDate.from_ticker(
        _FakeEarningsTicker(_earnings_frame(extra_columns=True))
    )
    assert all(r.revenue_estimate == 1.0e11 for r in rows)
    assert all(r.revenue_reported == 1.1e11 for r in rows)


def test_earnings_dates_without_revenue_columns_yield_none() -> None:
    from bearish.sources.yfinance import yFinanceEarningsDate

    rows = yFinanceEarningsDate.from_ticker(_FakeEarningsTicker(_earnings_frame()))
    assert all(r.revenue_estimate is None for r in rows)
    assert all(r.revenue_reported is None for r in rows)


def test_earnings_dates_roundtrip_through_database(tmp_path) -> None:
    from pathlib import Path

    from bearish.database.crud import BearishDb
    from bearish.models.base import Ticker
    from bearish.models.financials.base import Financials
    from bearish.models.query.query import AssetQuery, Symbols
    from bearish.sources.yfinance import yFinanceEarningsDate

    rows = yFinanceEarningsDate.from_ticker(_FakeEarningsTicker(_earnings_frame()))
    db = BearishDb(database_path=tmp_path / "bear.db")
    db.write_financials([Financials(earnings_date=rows)])
    db.write_financials([Financials(earnings_date=rows)])  # idempotent upsert

    loaded = db.read_financials(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    ).earnings_date
    assert len(loaded) == len(rows)
    assert {r.is_forward for r in loaded} == {True, False}
