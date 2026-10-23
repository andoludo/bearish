import datetime
from pathlib import Path

import pytest

from bearish.database.crud import BearishDb
from bearish.signals.models import CongressTrade, EventReturn, MarketEvent, PredictionQuote, TickerSignal

D = datetime.date


@pytest.fixture
def db(tmp_path: Path) -> BearishDb:
    return BearishDb(database_path=tmp_path / "signals.db")


def test_events_filter_by_type_and_whole_tag(db: BearishDb) -> None:
    db.write_events(
        [
            MarketEvent(event_id="US_MIDTERM_2022", event_type="election", name="2022 midterms", date=D(2022, 11, 8), country="USA", tags="midterm,divided", source="curated", as_of=D(2026, 10, 23)),
            MarketEvent(event_id="US_PRES_2024", event_type="election", name="2024 presidential", date=D(2024, 11, 5), country="USA", tags="presidential,unified", source="curated", as_of=D(2026, 10, 23)),
            MarketEvent(event_id="FOMC_2026-09-17", event_type="fomc", name="FOMC", date=D(2026, 9, 17), tags="fomc", source="curated", as_of=D(2026, 10, 23)),
        ]
    )
    assert [e.event_id for e in db.read_events(event_type="election")] == ["US_MIDTERM_2022", "US_PRES_2024"]
    assert [e.event_id for e in db.read_events(tag="midterm")] == ["US_MIDTERM_2022"]
    assert db.read_events(tag="mid") == []  # whole-tag match only
    assert db.read_events(tag="divided")[0].tag_set() == {"midterm", "divided"}


def test_event_returns_round_trip(db: BearishDb) -> None:
    row = EventReturn(event_id="US_MIDTERM_2022", asset="^GSPC", window="0d..+250d", start_date=D(2022, 11, 8), end_date=D(2023, 11, 8), ret=12.5, as_of=D(2026, 10, 23))
    db.write_event_returns([row, row])
    assert db.read_event_returns(event_id="US_MIDTERM_2022")[0].ret == 12.5
    assert db.read_event_returns(asset="XLK") == []


def test_ticker_signals_are_point_in_time(db: BearishDb) -> None:
    def sig(value: float, as_of: datetime.date, day: datetime.date = D(2026, 6, 30)) -> TickerSignal:
        return TickerSignal(symbol="nvda", signal="THEME_MENTIONS:ai", date=day, value=value, as_of=as_of, source="SEC")

    assert db.write_ticker_signals([sig(3, D(2026, 7, 1)), sig(5, D(2026, 7, 1), D(2026, 9, 30))]) == 2
    assert db.write_ticker_signals([sig(3, D(2026, 8, 1))]) == 0  # unchanged refetch
    assert db.write_ticker_signals([sig(4, D(2026, 8, 1))]) == 1  # revision
    latest = {s.date: s.value for s in db.read_ticker_signals(symbols=["NVDA"])}
    assert latest == {D(2026, 6, 30): 4, D(2026, 9, 30): 5}
    known_july = {s.date: s.value for s in db.read_ticker_signals(signal_prefix="THEME_MENTIONS", as_of=D(2026, 7, 15))}
    assert known_july == {D(2026, 6, 30): 3, D(2026, 9, 30): 5}
    frame = db.read_ticker_signal_frame(signal_prefix="THEME_")
    assert list(frame.columns) == ["THEME_MENTIONS:ai"]
    assert frame.loc[("NVDA", D(2026, 6, 30)), "THEME_MENTIONS:ai"] == 4
    assert db.read_ticker_signal_frame(signals=["NOPE"]).empty


def test_congress_trades_and_prediction_quotes(db: BearishDb) -> None:
    trade = CongressTrade(doc_id="20031234", line_no=1, chamber="House", member="Jane Doe", symbol="NVDA", asset_description="NVIDIA Corp", transaction_type="P", transaction_date=D(2026, 9, 1), filed_date=D(2026, 9, 20), amount_min=15001, amount_max=50000, source="HouseClerk")
    db.write_congress_trades([trade, trade])
    assert len(db.read_congress_trades(symbol="NVDA")) == 1
    assert db.read_congress_trades(member="Jane Doe")[0].amount_max == 50000

    quote = PredictionQuote(platform="Polymarket", market_id="m1", outcome="Democrats", as_of=D(2026, 10, 23), question="Which party wins the House in 2026?", category="election", probability=0.62, tags="midterm,house")
    db.write_prediction_quotes([quote, quote.model_copy(update={"as_of": D(2026, 10, 24), "probability": 0.64})])
    history = db.read_prediction_quotes(category="election")
    assert [q.probability for q in history] == [0.62, 0.64]
    assert db.read_prediction_quotes(platform="Kalshi") == []
