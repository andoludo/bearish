import datetime
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from bearish.database.crud import BearishDb
from bearish.database.schemas import PriceIndexORM
from bearish.models.financials.base import Financials
from bearish.models.financials.metrics import QuarterlyFinancialMetrics
from bearish.models.price.price import Price
from bearish.models.sec.holdings import Holding13FSummary
from bearish.models.sec.insider import InsiderTransaction
from bearish.signals.models import TickerSignal
from bearish.signals.screen import COMPONENT_WEIGHTS, early_winner_screen, score, zscore

D = datetime.date
AS_OF = D(2026, 4, 30)
QUARTERS = [
    D(2023, 12, 31),
    D(2024, 3, 31),
    D(2024, 6, 30),
    D(2024, 9, 30),
    D(2024, 12, 31),
    D(2025, 3, 31),
    D(2025, 6, 30),
    D(2025, 9, 30),
    D(2025, 12, 31),
]
# revenue per quarter; AAA accelerates, BBB decelerates, CCC flat, DDD only two quarters
REVENUE = {
    "AAA": [100, 100, 102, 104, 106, 110, 120, 135, 160],
    "BBB": [100, 100, 110, 121, 133, 140, 145, 148, 150],
    "CCC": [100] * 9,
}
MARGIN = {"AAA": [0.40] * 5 + [0.45, 0.50, 0.55, 0.60], "BBB": [0.50] * 5 + [0.48, 0.46, 0.44, 0.42], "CCC": [0.30] * 9}


def _metrics(
    symbol: str, day: datetime.date, revenue: float, margin: float, filed: datetime.date
) -> QuarterlyFinancialMetrics:
    return QuarterlyFinancialMetrics(
        symbol=symbol, source="SEC", date=day, total_revenue=revenue, gross_profit=revenue * margin, filed_date=filed
    )


def _summary(
    symbol: str, period: datetime.date, holders: int, prev: int, new: int, closed: int, filed: datetime.date
) -> Holding13FSummary:
    return Holding13FSummary(
        cusip=f"{symbol}0000000"[:9],
        period=period,
        symbol=symbol,
        issuer_name=symbol,
        holders=holders,
        total_shares=1e6,
        total_value=1e8,
        prev_holders=prev,
        new_holders=new,
        closed_holders=closed,
        latest_filed_date=filed,
    )


def _insider(
    symbol: str, line: int, code: str, value: float, traded: datetime.date, filed: datetime.date
) -> InsiderTransaction:
    return InsiderTransaction(
        symbol=symbol,
        cik="0000000001",
        accession_number=f"{symbol}-{line}",
        line_no=line,
        filed_date=filed,
        transaction_date=traded,
        reporting_owner="Someone",
        owner_relationship="officer",
        security_title="Common Stock",
        transaction_code=code,
        acquired_disposed="A" if code == "P" else "D",
        shares=1000,
        price=value / 1000,
        value=value,
    )


def _signal(symbol: str, signal: str, day: datetime.date, value: float, as_of: datetime.date) -> TickerSignal:
    return TickerSignal(symbol=symbol, signal=signal, date=day, value=value, as_of=as_of, source="test")


def _prices(symbol: str, closes: List[float]) -> List[Price]:
    days = [AS_OF - datetime.timedelta(days=365), AS_OF - datetime.timedelta(days=182), AS_OF]
    return [
        Price(symbol=symbol, source="Tiingo", date=day, open=c, high=c, low=c, close=c, volume=1)
        for day, c in zip(days, closes, strict=True)
    ]


@pytest.fixture
def db(tmp_path: Path) -> BearishDb:
    database = BearishDb(database_path=tmp_path / "screen.db")
    rows = [
        _metrics(symbol, day, revenue, margin, day + datetime.timedelta(days=40))
        for symbol in REVENUE
        for day, revenue, margin in zip(QUARTERS, REVENUE[symbol], MARGIN[symbol], strict=True)
    ]
    rows += [
        _metrics("DDD", QUARTERS[-2], 50, 0.2, D(2025, 11, 9)),
        _metrics("DDD", QUARTERS[-1], 55, 0.2, D(2026, 2, 9)),
    ]
    database.write_financials([Financials(quarterly_financial_metrics=rows)])
    database.write_holdings13f_summary(
        [
            _summary("AAA", D(2025, 12, 31), 300, 200, 120, 20, D(2026, 2, 14)),
            _summary("BBB", D(2025, 12, 31), 180, 200, 10, 30, D(2026, 2, 14)),
            _summary("CCC", D(2025, 12, 31), 200, 200, 15, 15, D(2026, 2, 14)),
        ]
    )
    database.write_insider_transactions(
        [
            _insider("AAA", 1, "P", 2_000_000, D(2026, 3, 1), D(2026, 3, 3)),
            _insider("BBB", 1, "S", 5_000_000, D(2026, 3, 1), D(2026, 3, 3)),
            _insider("CCC", 1, "S", 10_000, D(2025, 1, 1), D(2025, 1, 3)),  # outside the 6-month window
        ]
    )
    mentions = "THEME_MENTIONS:ai_accelerator"
    signals = [
        *[
            _signal("AAA", mentions, q, v, q + datetime.timedelta(days=5))
            for q, v in zip(QUARTERS, [0, 0, 0, 1, 1, 2, 4, 6, 9], strict=True)
        ],
        *[_signal("BBB", mentions, q, 3, q + datetime.timedelta(days=5)) for q in QUARTERS],
        _signal("AAA", "SHORT_INTEREST", D(2025, 12, 31), 10e6, D(2026, 1, 12)),
        _signal("AAA", "SHORT_INTEREST", D(2026, 3, 31), 6e6, D(2026, 4, 12)),
        _signal("BBB", "SHORT_INTEREST", D(2025, 12, 31), 10e6, D(2026, 1, 12)),
        _signal("BBB", "SHORT_INTEREST", D(2026, 3, 31), 14e6, D(2026, 4, 12)),
        _signal("HYPERSCALERS", "CAPEX_YOY", D(2025, 12, 31), 60.0, D(2026, 2, 5)),
    ]
    database.write_ticker_signals(signals)
    database.write_series(_prices("AAA", [10, 14, 25]) + _prices("BBB", [10, 11, 10]) + _prices("CCC", [10, 10, 10.5]))
    database.write_series(_prices("^GSPC", [100, 105, 110]), table=PriceIndexORM)
    return database


def test_zscore_winsorises_and_handles_degenerate_columns() -> None:
    z = zscore(pd.Series([1.0, 2.0, 3.0, 1000.0, np.nan]))
    assert z.isna().tolist() == [False, False, False, False, True]
    assert z.iloc[3] < 2.0  # the outlier is clipped before standardising
    assert zscore(pd.Series([5.0, 5.0])).tolist() == [0.0, 0.0]
    assert zscore(pd.Series([7.0])).tolist() == [0.0]


def test_score_ignores_missing_components() -> None:
    frame = pd.DataFrame(
        {"revenue_acceleration": [1.0, 2.0, np.nan], "insider_net_buying": [np.nan, 1.0, 2.0]}, index=["A", "B", "C"]
    )
    scored = score(frame)
    assert scored.loc["A", "coverage"] == 1
    assert scored.loc["B", "coverage"] == 2
    assert np.isfinite(scored["composite"]).all()


def test_screen_ranks_the_early_winner_first(db: BearishDb) -> None:
    frame = early_winner_screen(db, AS_OF, universe=["AAA", "BBB", "CCC", "DDD"])
    assert list(frame.index[:1]) == ["AAA"]
    assert frame.index[-1] in {"BBB", "DDD"}
    aaa = frame.loc["AAA"]
    # latest quarter known on 30 Apr 2026 is Dec 2025 (Mar 2026 is filed 10 May)
    assert aaa["revenue_acceleration"] == pytest.approx(((160 / 106 - 1) - (106 / 100 - 1)) * 100)
    assert frame.loc["BBB", "revenue_acceleration"] < 0
    assert aaa["gross_margin_change"] == pytest.approx(20.0)
    assert aaa["holders_growth"] == pytest.approx(0.5)
    assert aaa["net_new_holders"] == pytest.approx(0.5)
    assert aaa["insider_net_buying"] > 6
    assert frame.loc["BBB", "insider_net_buying"] < -6
    assert pd.isna(frame.loc["CCC", "insider_net_buying"])  # the only trade is older than 6 months
    assert aaa["theme_mention_growth"] > 0
    # BBB mentions the theme at a flat rate: 3 recent quarters vs 4 prior -> slightly negative
    assert frame.loc["BBB", "theme_mention_growth"] == pytest.approx(np.log1p(9) - np.log1p(12))
    assert aaa["short_interest_change"] == pytest.approx(-40.0)
    assert aaa["relative_strength_12m"] == pytest.approx(150.0 - 10.0)
    assert aaa["ai_capex_tailwind"] == 60.0
    assert frame.loc["CCC", "ai_capex_tailwind"] == 0.0
    assert pd.isna(frame.loc["DDD", "revenue_acceleration"])
    assert frame.loc["AAA", "coverage"] == len(COMPONENT_WEIGHTS)
    assert set(COMPONENT_WEIGHTS) <= set(frame.columns)
    assert (frame["as_of"] == AS_OF).all()


def test_screen_has_no_look_ahead(db: BearishDb) -> None:
    before = early_winner_screen(db, AS_OF, universe=["AAA", "BBB", "CCC", "DDD"])
    later = D(2026, 5, 20)
    # Everything below became public after AS_OF and must not move the scores.
    db.write_financials(
        [Financials(quarterly_financial_metrics=[_metrics("BBB", D(2026, 3, 31), 10_000, 0.9, D(2026, 5, 10))])]
    )
    db.write_holdings13f_summary([_summary("BBB", D(2026, 3, 31), 5_000, 180, 4_900, 80, D(2026, 5, 15))])
    db.write_insider_transactions([_insider("CCC", 2, "P", 9e9, D(2026, 4, 20), D(2026, 5, 2))])
    db.write_ticker_signals(
        [
            _signal("BBB", "THEME_MENTIONS:ai_accelerator", D(2025, 12, 31), 500, later),  # revision of a known date
            _signal("CCC", "SHORT_INTEREST", D(2026, 4, 30), 1.0, later),
            _signal("HYPERSCALERS", "CAPEX_YOY", D(2026, 3, 31), -90.0, later),
        ]
    )
    db.write_series(
        _prices("CCC", [1, 1, 1])[:0]
        + [Price(symbol="CCC", source="Tiingo", date=D(2026, 5, 15), open=99, high=99, low=99, close=99, volume=1)]
    )
    after = early_winner_screen(db, AS_OF, universe=["AAA", "BBB", "CCC", "DDD"])
    pdt.assert_frame_equal(before, after)
    # ... while a screen dated after publication does see them
    assert early_winner_screen(db, later, universe=["BBB"]).loc["BBB", "holders_growth"] > 20


def test_market_cap_filter_without_caps_returns_empty(db: BearishDb) -> None:
    frame = early_winner_screen(db, AS_OF, universe=["AAA"], min_market_cap=1e9)
    assert frame.empty


def test_run_screen_pipeline(db: BearishDb) -> None:
    from bearish.signals.pipelines.early_winners import run_screen

    frame = run_screen(db, as_of=AS_OF, universe=["AAA", "BBB", "CCC", "DDD"], top=2)
    assert list(frame.index) == ["AAA", frame.index[1]]
    assert len(frame) == 2
