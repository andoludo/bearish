import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import requests_mock

from bearish.database.crud import BearishDb
from bearish.macro.catalog._builder import series
from bearish.macro.models import Observation
from bearish.signals.event_study import (
    YAHOO_CHART_URL,
    bootstrap_ci,
    event_window_returns,
    prices_from_db,
    prices_from_factor,
    prices_from_yahoo_chart,
    summarise_returns,
    window_label,
)
from bearish.signals.models import MarketEvent

D = datetime.date


def _event(event_id: str, day: datetime.date, tags: str = "midterm") -> MarketEvent:
    return MarketEvent(
        event_id=event_id,
        event_type="election",
        name=event_id,
        date=day,
        tags=tags,
        source="test",
        as_of=D(2026, 10, 23),
    )


@pytest.fixture
def prices() -> pd.Series:
    days = pd.bdate_range("2020-01-01", periods=400)
    return pd.Series(np.linspace(100.0, 499.0, len(days)), index=days)


def test_window_returns_match_hand_computation(prices: pd.Series) -> None:
    event = _event("E1", D(2020, 6, 6))  # a Saturday: anchor is Friday 5 June's close
    rows = {r.window: r for r in event_window_returns(prices, event, "X", [(-5, 0), (0, 10)], as_of=D(2026, 1, 1))}
    anchor = prices.index.get_loc(pd.Timestamp("2020-06-05"))
    expected = (prices.iloc[anchor + 10] / prices.iloc[anchor] - 1) * 100
    assert rows["+0..+10"].ret == pytest.approx(expected)
    assert rows["+0..+10"].start_date == D(2020, 6, 5)
    assert rows["-5..+0"].end_date == D(2020, 6, 5)
    assert window_label((-60, 0)) == "-60..+0"


def test_events_before_history_and_windows_past_the_end_are_skipped(prices: pd.Series) -> None:
    assert event_window_returns(prices, _event("OLD", D(1999, 1, 1)), "X") == []
    late = event_window_returns(prices, _event("LATE", prices.index[-5].date()), "X", [(-20, 0), (0, 20)])
    assert [r.window for r in late] == ["-20..+0"]


def test_benchmark_and_excess_return(prices: pd.Series) -> None:
    benchmark = prices * 0 + 100.0  # flat benchmark
    rows = event_window_returns(
        prices, _event("E", D(2020, 3, 2)), "X", [(0, 20)], benchmark=benchmark, benchmark_name="B"
    )
    assert rows[0].benchmark == "B"
    assert rows[0].benchmark_ret == pytest.approx(0.0)
    assert rows[0].excess_ret == pytest.approx(rows[0].ret)


def test_summary_groups_and_bootstrap(prices: pd.Series) -> None:
    events = [
        _event("A", D(2020, 2, 3), "midterm,divided"),
        _event("B", D(2020, 4, 1), "midterm,divided"),
        _event("C", D(2020, 6, 1), "midterm,unified"),
        _event("Z", D(1990, 1, 1), "midterm,divided"),  # before the series: no rows
    ]
    returns = [r for e in events for r in event_window_returns(prices, e, "X", [(0, 20)])]
    summary = summarise_returns(returns, events, group_tags=("divided",)).set_index("group")
    assert summary.loc["all", "n"] == 3
    assert summary.loc["divided", "n"] == 2
    assert summary.loc["not_divided", "n"] == 1
    assert summary.loc["all", "hit_rate"] == 1.0
    assert summary.loc["all", "ci_low"] <= summary.loc["all", "mean"] <= summary.loc["all", "ci_high"]
    assert summarise_returns([], events).empty


def test_bootstrap_ci_is_reproducible() -> None:
    values = np.array([1.0, -2.0, 3.0, 4.0, 0.5])
    assert bootstrap_ci(values) == bootstrap_ci(values)
    low, high = bootstrap_ci(values)
    assert low < values.mean() < high


def test_prices_from_db_and_factor(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "es.db")
    assert prices_from_db(db, "^GSPC").empty
    with pytest.raises(ValueError):
        prices_from_db(db, "X", table="equity")
    mkt = series("FF_MKT", "USA", "KenFrench", "f|Mkt-RF", "D")
    rf = series("FF_RF", "USA", "KenFrench", "f|RF", "D")
    db.write_macro_series([mkt, rf])
    days = [D(2026, 1, 2), D(2026, 1, 5), D(2026, 1, 6)]
    db.write_observations(
        [
            Observation(series_id=mkt.series_id, date=d, value=v, as_of=D(2026, 2, 1))
            for d, v in zip(days, [1.0, -1.0, 2.0], strict=True)
        ]
        + [Observation(series_id=rf.series_id, date=d, value=0.0, as_of=D(2026, 2, 1)) for d in days]
    )
    index = prices_from_factor(db)
    assert index.iloc[-1] == pytest.approx(100 * 1.01 * 0.99 * 1.02)


def test_yahoo_chart_fallback_parses_adjusted_closes() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"exchangeTimezoneName": "America/New_York"},
                    "timestamp": [1762525800, 1762785000],
                    "indicators": {"quote": [{"close": [1.0, 2.0]}], "adjclose": [{"adjclose": [10.0, 11.0]}]},
                }
            ]
        }
    }
    with requests_mock.Mocker() as req:
        req.get(YAHOO_CHART_URL.format(symbol="^GSPC"), json=payload)
        closes = prices_from_yahoo_chart("^GSPC")
    assert closes.tolist() == [10.0, 11.0]
    assert closes.index[0] == pd.Timestamp("2025-11-07")
