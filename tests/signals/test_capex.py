import datetime
from pathlib import Path

import pandas as pd
import pytest

from bearish.database.crud import BearishDb
from bearish.models.financials.base import Financials
from bearish.models.financials.cash_flow import CashFlow, QuarterlyCashFlow
from bearish.signals.capex import (
    AGGREGATE_SYMBOL,
    aggregate_capex,
    build_capex_signals,
    capex_signals,
    derive_fourth_quarters,
    read_quarterly_capex,
)

D = datetime.date


def _q(symbol: str, day: datetime.date, capex: float, filed: datetime.date, source: str = "SEC") -> QuarterlyCashFlow:
    return QuarterlyCashFlow(symbol=symbol, source=source, date=day, capital_expenditure=-capex, filed_date=filed)


def _a(symbol: str, day: datetime.date, capex: float, filed: datetime.date) -> CashFlow:
    return CashFlow(symbol=symbol, source="SEC", date=day, capital_expenditure=-capex, filed_date=filed)


@pytest.fixture
def db(tmp_path: Path) -> BearishDb:
    database = BearishDb(database_path=tmp_path / "capex.db")
    database.write_financials(
        [
            Financials(
                quarterly_cash_flows=[
                    # MSFT-like fiscal year ending June: three 10-Q quarters, Q4 only in the 10-K
                    _q("AAA", D(2024, 9, 30), 10, D(2024, 10, 30)),
                    _q("AAA", D(2024, 12, 31), 12, D(2025, 1, 29)),
                    _q("AAA", D(2025, 3, 31), 14, D(2025, 4, 30)),
                    _q("AAA", D(2025, 9, 30), 20, D(2025, 10, 29)),
                    # Yahoo duplicate of an SEC quarter must lose to SEC
                    _q("AAA", D(2025, 9, 30), 999, D(2025, 10, 1), source="Yfinance"),
                    # calendar-year filer
                    _q("BBB", D(2024, 9, 30), 5, D(2024, 11, 5)),
                    _q("BBB", D(2025, 6, 30), 6, D(2025, 8, 5)),
                    _q("BBB", D(2025, 9, 30), 7, D(2025, 11, 5)),
                ],
                cash_flows=[_a("AAA", D(2025, 6, 30), 52, D(2025, 7, 30))],
            )
        ]
    )
    return database


def test_fourth_quarter_is_derived_from_the_annual_filing(db: BearishDb) -> None:
    quarterly = read_quarterly_capex(db)
    aaa = quarterly[quarterly["symbol"] == "AAA"].set_index("date")
    assert aaa.loc[D(2025, 6, 30), "capex"] == pytest.approx(52 - 10 - 12 - 14)
    assert aaa.loc[D(2025, 6, 30), "known"] == D(2025, 7, 30)
    assert aaa.loc[D(2025, 9, 30), "capex"] == 20  # SEC preferred over Yahoo
    assert aaa.loc[D(2025, 9, 30), "source"] == "SEC"


def test_q4_not_derived_without_three_quarters() -> None:
    quarterly = pd.DataFrame(
        [{"symbol": "X", "source": "SEC", "date": D(2025, 3, 31), "known": D(2025, 4, 30), "capex": 5.0}]
    )
    annual = pd.DataFrame(
        [{"symbol": "X", "source": "SEC", "date": D(2025, 6, 30), "known": D(2025, 7, 30), "capex": 20.0}]
    )
    assert len(derive_fourth_quarters(quarterly, annual)) == 1


def test_capex_signals_growth_is_known_when_both_inputs_are(db: BearishDb) -> None:
    signals = {(s.symbol, s.signal, s.date): s for s in capex_signals(read_quarterly_capex(db))}
    growth = signals[("AAA", "CAPEX_YOY", D(2025, 9, 30))]
    assert growth.value == pytest.approx(100.0)  # 20 vs 10
    assert growth.as_of == D(2025, 10, 29)
    assert ("AAA", "CAPEX_YOY", D(2024, 9, 30)) not in signals
    assert signals[("BBB", "CAPEX_USD", D(2025, 9, 30))].as_of == D(2025, 11, 5)


def test_aggregate_requires_every_member(db: BearishDb) -> None:
    signals = {(s.signal, s.date): s for s in aggregate_capex(read_quarterly_capex(db), members=("AAA", "BBB"))}
    assert {d for _, d in signals} == {D(2024, 9, 30), D(2025, 6, 30), D(2025, 9, 30)}
    assert signals[("CAPEX_USD", D(2025, 9, 30))].value == 27
    assert signals[("CAPEX_USD", D(2025, 9, 30))].as_of == D(2025, 11, 5)  # last member's filing
    assert signals[("CAPEX_YOY", D(2025, 9, 30))].value == pytest.approx((27 / 15 - 1) * 100)


def test_build_capex_signals_writes_point_in_time(db: BearishDb) -> None:
    signals = build_capex_signals(db, members=("AAA", "BBB"))
    assert db.write_ticker_signals(signals) == len(signals)
    assert db.write_ticker_signals(signals) == 0
    known_early = db.read_ticker_signals(symbols=[AGGREGATE_SYMBOL], signals=["CAPEX_USD"], as_of=D(2025, 11, 1))
    assert D(2025, 9, 30) not in {s.date for s in known_early}
