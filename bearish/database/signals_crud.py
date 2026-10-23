"""Persistence for events, event returns, ticker signals, congressional trades
and prediction-market quotes."""

import datetime
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Engine, and_, func, insert
from sqlmodel import Session, col, select

from bearish.database.schemas import (
    CongressTradeORM,
    EventReturnORM,
    MarketEventORM,
    PredictionQuoteORM,
    TickerSignalORM,
)
from bearish.signals.models import CongressTrade, EventReturn, MarketEvent, PredictionQuote, TickerSignal
from bearish.utils.utils import batch

BATCH_SIZE = 5000
REVISION_TOLERANCE = 1e-9


class SignalsCrudMixin:
    def _signals_engine(self) -> Engine:
        return self._engine  # type: ignore[attr-defined,no-any-return]

    def _signals_upsert(self, orm: type, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        with Session(self._signals_engine()) as session:
            for chunk in batch(rows, BATCH_SIZE):
                session.exec(insert(orm).prefix_with("OR REPLACE"), params=chunk)
            session.commit()

    # events -----------------------------------------------------------------

    def _write_events(self, events: List[MarketEvent]) -> None:
        self._signals_upsert(MarketEventORM, [e.model_dump() for e in events])

    def _read_events(self, event_type: Optional[str] = None, tag: Optional[str] = None) -> List[MarketEvent]:
        statement = select(MarketEventORM)
        if event_type is not None:
            statement = statement.where(col(MarketEventORM.event_type) == event_type)
        if tag is not None:
            # tags are a comma-separated list; match a whole tag
            statement = statement.where(func.instr("," + col(MarketEventORM.tags) + ",", f",{tag},") > 0)
        statement = statement.order_by(col(MarketEventORM.date))
        with Session(self._signals_engine()) as session:
            return [MarketEvent.model_validate(row.model_dump()) for row in session.exec(statement).all()]

    def _write_event_returns(self, returns: List[EventReturn]) -> None:
        self._signals_upsert(EventReturnORM, [r.model_dump() for r in returns])

    def _read_event_returns(self, event_id: Optional[str] = None, asset: Optional[str] = None) -> List[EventReturn]:
        statement = select(EventReturnORM)
        if event_id is not None:
            statement = statement.where(col(EventReturnORM.event_id) == event_id)
        if asset is not None:
            statement = statement.where(col(EventReturnORM.asset) == asset)
        with Session(self._signals_engine()) as session:
            return [EventReturn.model_validate(row.model_dump()) for row in session.exec(statement).all()]

    # ticker signals (point-in-time) ------------------------------------------

    def _latest_ticker_values(
        self, session: Session, keys: List[Tuple[str, str]]
    ) -> Dict[Tuple[str, str, datetime.date], float]:
        latest: Dict[Tuple[str, str, datetime.date], float] = {}
        for symbol, signal in keys:
            vintages = (
                select(
                    col(TickerSignalORM.date),
                    func.max(col(TickerSignalORM.as_of)).label("as_of"),
                )
                .where(col(TickerSignalORM.symbol) == symbol, col(TickerSignalORM.signal) == signal)
                .group_by(col(TickerSignalORM.date))
                .subquery()
            )
            statement = (
                select(col(TickerSignalORM.date), col(TickerSignalORM.value))
                .join(
                    vintages,
                    and_(
                        col(TickerSignalORM.date) == vintages.c.date,
                        col(TickerSignalORM.as_of) == vintages.c.as_of,
                    ),
                )
                .where(col(TickerSignalORM.symbol) == symbol, col(TickerSignalORM.signal) == signal)
            )
            for day, value in session.exec(statement).all():
                latest[(symbol, signal, day)] = value
        return latest

    def _write_ticker_signals(self, signals: List[TickerSignal]) -> int:
        """Store a vintage only when a value is new or revised; returns rows written."""
        if not signals:
            return 0
        grouped: Dict[Tuple[str, str], List[TickerSignal]] = defaultdict(list)
        for item in signals:
            grouped[(item.symbol, item.signal)].append(item)
        with Session(self._signals_engine()) as session:
            latest = self._latest_ticker_values(session, list(grouped))
            changed = [
                item.model_dump()
                for item in signals
                if (key := (item.symbol, item.signal, item.date)) not in latest
                or not math.isclose(latest[key], item.value, rel_tol=REVISION_TOLERANCE, abs_tol=REVISION_TOLERANCE)
            ]
        self._signals_upsert(TickerSignalORM, changed)
        return len(changed)

    def _read_ticker_signals(
        self,
        symbols: Optional[List[str]] = None,
        signals: Optional[List[str]] = None,
        signal_prefix: Optional[str] = None,
        start: Optional[datetime.date] = None,
        as_of: Optional[datetime.date] = None,
    ) -> List[TickerSignal]:
        vintages = select(
            col(TickerSignalORM.symbol),
            col(TickerSignalORM.signal),
            col(TickerSignalORM.date),
            func.max(col(TickerSignalORM.as_of)).label("as_of"),
        )
        if as_of is not None:
            vintages = vintages.where(col(TickerSignalORM.as_of) <= as_of)
        vintages_sq = vintages.group_by(
            col(TickerSignalORM.symbol), col(TickerSignalORM.signal), col(TickerSignalORM.date)
        ).subquery()
        statement = select(TickerSignalORM).join(
            vintages_sq,
            and_(
                col(TickerSignalORM.symbol) == vintages_sq.c.symbol,
                col(TickerSignalORM.signal) == vintages_sq.c.signal,
                col(TickerSignalORM.date) == vintages_sq.c.date,
                col(TickerSignalORM.as_of) == vintages_sq.c.as_of,
            ),
        )
        if symbols:
            statement = statement.where(col(TickerSignalORM.symbol).in_([s.upper() for s in symbols]))
        if signals:
            statement = statement.where(col(TickerSignalORM.signal).in_(signals))
        if signal_prefix:
            statement = statement.where(col(TickerSignalORM.signal).startswith(signal_prefix))
        if start is not None:
            statement = statement.where(col(TickerSignalORM.date) >= start)
        statement = statement.order_by(
            col(TickerSignalORM.symbol), col(TickerSignalORM.signal), col(TickerSignalORM.date)
        )
        with Session(self._signals_engine()) as session:
            return [TickerSignal.model_validate(row.model_dump()) for row in session.exec(statement).all()]

    # congress trades & prediction quotes --------------------------------------

    def _write_congress_trades(self, trades: List[CongressTrade]) -> None:
        self._signals_upsert(CongressTradeORM, [t.model_dump() for t in trades])

    def _read_congress_trades(self, symbol: Optional[str] = None, member: Optional[str] = None) -> List[CongressTrade]:
        statement = select(CongressTradeORM)
        if symbol is not None:
            statement = statement.where(col(CongressTradeORM.symbol) == symbol)
        if member is not None:
            statement = statement.where(col(CongressTradeORM.member) == member)
        with Session(self._signals_engine()) as session:
            return [CongressTrade.model_validate(row.model_dump()) for row in session.exec(statement).all()]

    def _write_prediction_quotes(self, quotes: List[PredictionQuote]) -> None:
        self._signals_upsert(PredictionQuoteORM, [q.model_dump() for q in quotes])

    def _read_prediction_quotes(
        self, category: Optional[str] = None, platform: Optional[str] = None
    ) -> List[PredictionQuote]:
        statement = select(PredictionQuoteORM)
        if category is not None:
            statement = statement.where(col(PredictionQuoteORM.category) == category)
        if platform is not None:
            statement = statement.where(col(PredictionQuoteORM.platform) == platform)
        statement = statement.order_by(col(PredictionQuoteORM.as_of))
        with Session(self._signals_engine()) as session:
            return [PredictionQuote.model_validate(row.model_dump()) for row in session.exec(statement).all()]
