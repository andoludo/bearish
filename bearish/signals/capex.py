"""Capital expenditure signals, per company and for the hyperscalers together.

Reads the cash-flow statements already stored by the financials sources
(SEC XBRL preferred, Yahoo as fallback) and writes:

* ``CAPEX_USD`` — quarterly capital expenditure as a positive amount;
* ``CAPEX_YOY`` — growth against the same fiscal quarter a year earlier, %;
* the same two signals for symbol ``HYPERSCALERS``: the sum over the
  hyperscaler set for calendar quarters where every member reported
  (fiscal quarters such as Oracle's Feb/May/Aug/Nov are mapped onto the
  calendar quarter they end in).

SEC quarterly cash flows come from 10-Qs only, so the fourth fiscal quarter
is derived as the 10-K annual amount minus the three 10-Q quarters of that
fiscal year. Point-in-time: ``as_of`` is the statement's ``filed_date``
(for a derived Q4, the 10-K's) and, for Yahoo rows without one, the date the
row was fetched; a growth rate is known once both of its inputs are.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

import pandas as pd

from bearish.interface.interface import BearishDbBase
from bearish.signals.models import TickerSignal
from bearish.signals.sources.edgar_themes import quarter_end

logger = logging.getLogger(__name__)

HYPERSCALERS: Tuple[str, ...] = ("MSFT", "GOOGL", "AMZN", "META", "ORCL")
AGGREGATE_SYMBOL = "HYPERSCALERS"
SOURCE_PREFERENCE = ("SEC", "Yfinance", "YahooQuery")
YEAR_TOLERANCE_DAYS = 25
SIGNAL_SOURCE = "bearish"


def _query(table: str, symbols: Optional[Sequence[str]]) -> str:
    where = "capital_expenditure IS NOT NULL"
    if symbols:
        quoted = ",".join(f"'{s.upper()}'" for s in symbols)
        where += f" AND symbol IN ({quoted})"
    return f"SELECT symbol, source, date, created_at, filed_date, capital_expenditure FROM {table} WHERE {where}"


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "source", "date", "known", "capex"])
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    known = pd.to_datetime(frame["filed_date"]).fillna(pd.to_datetime(frame["created_at"]))
    frame["known"] = known.dt.date
    frame["capex"] = frame["capital_expenditure"].astype(float).abs()
    rank = {source: index for index, source in enumerate(SOURCE_PREFERENCE)}
    frame["rank"] = frame["source"].map(rank).fillna(len(rank))
    frame = frame.sort_values("rank").drop_duplicates(["symbol", "date"], keep="first")
    return frame[["symbol", "source", "date", "known", "capex"]].sort_values(["symbol", "date"]).reset_index(drop=True)


Row = Dict[str, Any]


def _records(frame: pd.DataFrame) -> List[Row]:
    return cast(List[Row], frame.to_dict("records"))


def derive_fourth_quarters(quarterly: pd.DataFrame, annual: pd.DataFrame) -> pd.DataFrame:
    """Q4 = annual - three quarters of the same fiscal year, where Q4 is missing."""
    quarter_rows = _records(quarterly)
    derived: List[Row] = []
    for year in _records(annual):
        own = [q for q in quarter_rows if q["symbol"] == year["symbol"]]
        if any(q["date"] == year["date"] for q in own):
            continue
        fiscal_start = year["date"] - datetime.timedelta(days=360)
        inside = [q for q in own if fiscal_start < q["date"] < year["date"]]
        if len(inside) != 3:  # noqa: PLR2004
            continue
        value = float(year["capex"]) - sum(float(q["capex"]) for q in inside)
        if value < 0:
            logger.warning(f"Derived negative Q4 capex for {year['symbol']} {year['date']}; skipped")
            continue
        derived.append(
            {
                "symbol": year["symbol"],
                "source": f"{year['source']}:derived",
                "date": year["date"],
                "known": year["known"],
                "capex": value,
            }
        )
    if not derived:
        return quarterly
    return pd.concat([quarterly, pd.DataFrame(derived)], ignore_index=True).sort_values(["symbol", "date"])


def read_quarterly_capex(db: BearishDbBase, symbols: Optional[Sequence[str]] = None) -> pd.DataFrame:
    quarterly = _prepare(db.read_query(_query("quarterlycashflow", symbols)))
    annual = _prepare(db.read_query(_query("cashflow", symbols)))
    return derive_fourth_quarters(quarterly, annual).reset_index(drop=True)


def _year_ago(rows: List[Row], day: datetime.date) -> Optional[Row]:
    target = day - datetime.timedelta(days=365)
    candidates = [(abs((row["date"] - target).days), row) for row in rows]
    if not candidates:
        return None
    distance, row = min(candidates, key=lambda item: item[0])
    return row if distance <= YEAR_TOLERANCE_DAYS else None


def capex_signals(quarterly: pd.DataFrame) -> List[TickerSignal]:
    by_symbol: Dict[str, List[Row]] = {}
    for row in _records(quarterly):
        by_symbol.setdefault(str(row["symbol"]), []).append(row)
    signals: List[TickerSignal] = []
    for symbol, rows in by_symbol.items():
        rows.sort(key=lambda row: row["date"])
        for row in rows:
            signals.append(
                TickerSignal(
                    symbol=symbol,
                    signal="CAPEX_USD",
                    date=row["date"],
                    value=float(row["capex"]),
                    as_of=row["known"],
                    source=SIGNAL_SOURCE,
                )
            )
            previous = _year_ago(rows, row["date"])
            if previous is None or float(previous["capex"]) <= 0:
                continue
            signals.append(
                TickerSignal(
                    symbol=symbol,
                    signal="CAPEX_YOY",
                    date=row["date"],
                    value=(float(row["capex"]) / float(previous["capex"]) - 1.0) * 100.0,
                    as_of=max(row["known"], previous["known"]),
                    source=SIGNAL_SOURCE,
                )
            )
    return signals


def aggregate_capex(quarterly: pd.DataFrame, members: Sequence[str] = HYPERSCALERS) -> List[TickerSignal]:
    """Sum of member capex per calendar quarter, only where every member reported."""
    per_quarter: Dict[datetime.date, Dict[str, Row]] = {}
    for row in _records(quarterly[quarterly["symbol"].isin(members)]):
        per_quarter.setdefault(quarter_end(row["date"]), {})[str(row["symbol"])] = row
    totals: Dict[datetime.date, Tuple[float, datetime.date]] = {
        quarter: (sum(float(r["capex"]) for r in rows.values()), max(r["known"] for r in rows.values()))
        for quarter, rows in per_quarter.items()
        if len(rows) == len(members)
    }
    signals: List[TickerSignal] = []
    for quarter, (value, known) in sorted(totals.items()):
        signals.append(
            TickerSignal(
                symbol=AGGREGATE_SYMBOL,
                signal="CAPEX_USD",
                date=quarter,
                value=value,
                as_of=known,
                source=SIGNAL_SOURCE,
            )
        )
        previous = totals.get(datetime.date(quarter.year - 1, quarter.month, quarter.day))
        if previous is not None and previous[0] > 0:
            signals.append(
                TickerSignal(
                    symbol=AGGREGATE_SYMBOL,
                    signal="CAPEX_YOY",
                    date=quarter,
                    value=(value / previous[0] - 1.0) * 100.0,
                    as_of=max(known, previous[1]),
                    source=SIGNAL_SOURCE,
                )
            )
    return signals


def build_capex_signals(
    db: BearishDbBase, symbols: Optional[Sequence[str]] = None, members: Sequence[str] = HYPERSCALERS
) -> List[TickerSignal]:
    wanted = sorted({*(symbols or []), *members}) if symbols else None
    quarterly = read_quarterly_capex(db, wanted)
    per_company = capex_signals(quarterly if symbols is None else quarterly[quarterly["symbol"].isin(wanted or [])])
    return per_company + aggregate_capex(quarterly, members)
