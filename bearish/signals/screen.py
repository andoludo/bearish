"""Early-winner screen: companies whose fundamentals, ownership and attention
are all turning up before the price fully reflects it.

Every input is filtered to what was public on ``as_of``:

* statements by ``filed_date`` (Yahoo rows without one: the date fetched);
* 13F summaries by ``latest_filed_date`` (the last report aggregated);
* insider trades by Form 4 ``filed_date``;
* ticker signals (theme mentions, short interest, capex) by vintage ``as_of``;
* prices by trading date.

Components (raw value -> cross-sectional z-score, winsorised at the 5th/95th
percentiles; a component a symbol lacks is NaN and left out of its composite):

====================== ======= ==================================================
component              weight  definition
====================== ======= ==================================================
revenue_acceleration    0.20   y/y revenue growth of the latest quarter minus the
                               same growth one year earlier (percentage points)
gross_margin_change     0.15   gross margin now minus a year earlier (pp)
holders_growth          0.10   13F holders now / previous quarter - 1
net_new_holders         0.10   (new - closed 13F holders) / previous holders
insider_net_buying      0.10   signed log10(1 + |open-market buys - sells|), USD,
                               Form 4 filed in the last 182 days
theme_mention_growth    0.10   log(1 + theme mentions in the last 4 quarters)
                               - log(1 + mentions in the 4 before)
short_interest_change  -0.05   % change in short interest over ~3 months
                               (negative weight: falling shorts score higher)
relative_strength_6m    0.075  6-month return minus ^GSPC's (pp)
relative_strength_12m   0.075  12-month return minus ^GSPC's (pp)
ai_capex_tailwind       0.05   hyperscaler capex y/y (%) for companies with AI
                               theme mentions in the last 4 quarters, else 0
====================== ======= ==================================================

composite = sum(weight * z) / sum(|weight|) over the components a symbol has;
``coverage`` counts them. R&D intensity is not included: neither the SEC
mapping nor Yahoo stores an R&D line in bearish today.
"""

import datetime
import logging
import math
from typing import Dict, List, Optional, Sequence, cast

import numpy as np
import pandas as pd

from bearish.interface.interface import BearishDbBase
from bearish.signals.capex import AGGREGATE_SYMBOL
from bearish.signals.themes import AI_THEMES, theme_signal

logger = logging.getLogger(__name__)

COMPONENT_WEIGHTS: Dict[str, float] = {
    "revenue_acceleration": 0.20,
    "gross_margin_change": 0.15,
    "holders_growth": 0.10,
    "net_new_holders": 0.10,
    "insider_net_buying": 0.10,
    "theme_mention_growth": 0.10,
    "short_interest_change": -0.05,
    "relative_strength_6m": 0.075,
    "relative_strength_12m": 0.075,
    "ai_capex_tailwind": 0.05,
}
BENCHMARK = "^GSPC"
YEAR = datetime.timedelta(days=365)
MATCH_TOLERANCE_DAYS = 25
INSIDER_WINDOW = datetime.timedelta(days=182)
SHORT_LOOKBACK = datetime.timedelta(days=90)
SOURCE_PREFERENCE = {"SEC": 0, "Yfinance": 1, "YahooQuery": 2}


def _in_clause(symbols: Sequence[str]) -> str:
    return ",".join("'" + s.upper().replace("'", "''") + "'" for s in symbols)


def _closest(frame: pd.DataFrame, day: datetime.date, column: str = "date") -> Optional[pd.Series]:
    if frame.empty:
        return None
    distance = frame[column].map(lambda d: abs((d - day).days))
    if distance.min() > MATCH_TOLERANCE_DAYS:
        return None
    return cast(pd.Series, frame.loc[distance.idxmin()])


# --- components ------------------------------------------------------------------


def fundamentals_components(db: BearishDbBase, symbols: Sequence[str], as_of: datetime.date) -> pd.DataFrame:
    frame = db.read_query(
        "SELECT symbol, source, date, created_at, filed_date, total_revenue, gross_profit "
        f"FROM quarterlyfinancialmetrics WHERE total_revenue IS NOT NULL AND symbol IN ({_in_clause(symbols)})"
    )
    result = pd.DataFrame(index=pd.Index(sorted(symbols), name="symbol"))
    if frame.empty:
        return result
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["known"] = pd.to_datetime(frame["filed_date"]).fillna(pd.to_datetime(frame["created_at"])).dt.date
    frame = frame[frame["known"] <= as_of]
    frame["rank"] = frame["source"].map(SOURCE_PREFERENCE).fillna(len(SOURCE_PREFERENCE))
    frame = frame.sort_values("rank").drop_duplicates(["symbol", "date"]).sort_values("date")
    acceleration: Dict[str, float] = {}
    margin_change: Dict[str, float] = {}
    for symbol, group in frame.groupby("symbol"):
        group = group.reset_index(drop=True)  # noqa: PLW2901
        latest = group.iloc[-1]
        year_ago = _closest(group, latest["date"] - YEAR)
        two_years_ago = _closest(group, latest["date"] - 2 * YEAR)
        if year_ago is not None and year_ago["total_revenue"] > 0:
            growth_now = latest["total_revenue"] / year_ago["total_revenue"] - 1.0
            if two_years_ago is not None and two_years_ago["total_revenue"] > 0:
                growth_then = year_ago["total_revenue"] / two_years_ago["total_revenue"] - 1.0
                acceleration[str(symbol)] = (growth_now - growth_then) * 100.0
            if pd.notna(latest["gross_profit"]) and pd.notna(year_ago["gross_profit"]) and latest["total_revenue"] > 0:
                margin_now = latest["gross_profit"] / latest["total_revenue"]
                margin_then = year_ago["gross_profit"] / year_ago["total_revenue"]
                margin_change[str(symbol)] = (margin_now - margin_then) * 100.0
    result["revenue_acceleration"] = pd.Series(acceleration, dtype=float)
    result["gross_margin_change"] = pd.Series(margin_change, dtype=float)
    return result


def ownership_components(db: BearishDbBase, symbols: Sequence[str], as_of: datetime.date) -> pd.DataFrame:
    frame = db.read_query(
        "SELECT symbol, period, holders, prev_holders, new_holders, closed_holders, latest_filed_date "
        f"FROM holding13fsummary WHERE symbol IN ({_in_clause(symbols)})"
    )
    result = pd.DataFrame(index=pd.Index(sorted(symbols), name="symbol"))
    if frame.empty:
        return result
    frame["latest_filed_date"] = pd.to_datetime(frame["latest_filed_date"]).dt.date
    frame = frame[frame["latest_filed_date"] <= as_of]
    if frame.empty:
        return result
    latest_period = frame.groupby("symbol")["period"].transform("max")
    frame = frame[frame["period"] == latest_period]
    totals = frame.groupby("symbol")[["holders", "prev_holders", "new_holders", "closed_holders"]].sum(min_count=1)
    previous = totals["prev_holders"].where(totals["prev_holders"] > 0)
    result["holders_growth"] = totals["holders"] / previous - 1.0
    result["net_new_holders"] = (totals["new_holders"] - totals["closed_holders"]) / previous
    return result


def insider_component(db: BearishDbBase, symbols: Sequence[str], as_of: datetime.date) -> pd.DataFrame:
    frame = db.read_query(
        "SELECT symbol, filed_date, transaction_date, transaction_code, value, is_derivative "
        f"FROM insidertransaction WHERE transaction_code IN ('P', 'S') AND symbol IN ({_in_clause(symbols)})"
    )
    result = pd.DataFrame(index=pd.Index(sorted(symbols), name="symbol"))
    if frame.empty:
        return result
    frame["filed_date"] = pd.to_datetime(frame["filed_date"]).dt.date
    frame["transaction_date"] = pd.to_datetime(frame["transaction_date"]).dt.date
    frame = frame[
        (frame["filed_date"] <= as_of)
        & (frame["transaction_date"] > as_of - INSIDER_WINDOW)
        & (~frame["is_derivative"].astype(bool))
        & frame["value"].notna()
    ]
    signed = frame["value"].where(frame["transaction_code"] == "P", -frame["value"])
    net = signed.groupby(frame["symbol"]).sum()
    result["insider_net_buying"] = net.map(lambda v: math.copysign(math.log10(1.0 + abs(v)), v))
    return result


def signal_components(db: BearishDbBase, symbols: Sequence[str], as_of: datetime.date) -> pd.DataFrame:
    result = pd.DataFrame(index=pd.Index(sorted(symbols), name="symbol"))
    wanted = {s.upper() for s in symbols}
    mentions = [
        s
        for s in db.read_ticker_signals(signal_prefix="THEME_MENTIONS:", as_of=as_of)
        if s.symbol in wanted and s.date <= as_of
    ]
    recent: Dict[str, float] = {}
    prior: Dict[str, float] = {}
    ai_recent: Dict[str, float] = {}
    ai_signals = {theme_signal(key) for key in AI_THEMES}
    for item in mentions:
        if item.date > as_of - YEAR:
            recent[item.symbol] = recent.get(item.symbol, 0.0) + item.value
            if item.signal in ai_signals:
                ai_recent[item.symbol] = ai_recent.get(item.symbol, 0.0) + item.value
        elif item.date > as_of - 2 * YEAR:
            prior[item.symbol] = prior.get(item.symbol, 0.0) + item.value
    covered = set(recent) | set(prior)
    result["theme_mention_growth"] = pd.Series(
        {s: math.log1p(recent.get(s, 0.0)) - math.log1p(prior.get(s, 0.0)) for s in covered}, dtype=float
    )

    shorts = [
        s
        for s in db.read_ticker_signals(signals=["SHORT_INTEREST"], as_of=as_of)
        if s.symbol in wanted and s.date <= as_of
    ]
    change: Dict[str, float] = {}
    by_symbol: Dict[str, List[tuple[datetime.date, float]]] = {}
    for item in shorts:
        by_symbol.setdefault(item.symbol, []).append((item.date, item.value))
    for symbol, points in by_symbol.items():
        points.sort()
        last_day, last_value = points[-1]
        earlier = [value for day, value in points if day <= last_day - SHORT_LOOKBACK]
        if earlier and earlier[-1] > 0:
            change[symbol] = (last_value / earlier[-1] - 1.0) * 100.0
    result["short_interest_change"] = pd.Series(change, dtype=float)

    capex = [
        s
        for s in db.read_ticker_signals(symbols=[AGGREGATE_SYMBOL], signals=["CAPEX_YOY"], as_of=as_of)
        if s.date <= as_of
    ]
    if capex:
        tailwind = max(capex, key=lambda s: s.date).value
        result["ai_capex_tailwind"] = [tailwind if ai_recent.get(s, 0.0) > 0 else 0.0 for s in result.index]
    return result


def _close_on(prices: pd.DataFrame, day: datetime.date) -> Optional[float]:
    window = prices[(prices["date"] <= day) & (prices["date"] > day - datetime.timedelta(days=10))]
    return None if window.empty else float(window.iloc[-1]["close"])


def momentum_components(db: BearishDbBase, symbols: Sequence[str], as_of: datetime.date) -> pd.DataFrame:
    result = pd.DataFrame(index=pd.Index(sorted(symbols), name="symbol"))
    start = as_of - YEAR - datetime.timedelta(days=15)
    prices = db.read_query(
        f"SELECT symbol, date, close FROM price WHERE symbol IN ({_in_clause(symbols)}) "
        f"AND date >= '{start.isoformat()}' AND date <= '{as_of.isoformat()} 23:59:59'"
    )
    benchmark = db.read_query(
        f"SELECT symbol, date, close FROM priceindex WHERE symbol = '{BENCHMARK}' "
        f"AND date >= '{start.isoformat()}' AND date <= '{as_of.isoformat()} 23:59:59'"
    )
    if prices.empty:
        return result
    for frame in (prices, benchmark):
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"]).dt.date
    prices = prices.sort_values("date")
    benchmark = benchmark.sort_values("date") if not benchmark.empty else benchmark

    def window_return(frame: pd.DataFrame, days: int) -> Optional[float]:
        if frame.empty:
            return None
        now, then = _close_on(frame, as_of), _close_on(frame, as_of - datetime.timedelta(days=days))
        if now is None or then is None or then <= 0:
            return None
        return (now / then - 1.0) * 100.0

    for label, days in (("relative_strength_6m", 182), ("relative_strength_12m", 365)):
        bench = window_return(benchmark, days) or 0.0
        values = {}
        for symbol, group in prices.groupby("symbol"):
            ret = window_return(group, days)
            if ret is not None:
                values[str(symbol)] = ret - bench
        result[label] = pd.Series(values, dtype=float)
    return result


# --- scoring ---------------------------------------------------------------------


def zscore(values: pd.Series) -> pd.Series:
    """Winsorise at the 5th/95th percentiles, then standardise; constant or single values score 0."""
    present = values.dropna()
    if present.empty:
        return values
    clipped = values.clip(present.quantile(0.05), present.quantile(0.95))
    std = clipped.std(ddof=0)
    if len(present) < 2 or not np.isfinite(std) or std == 0:  # noqa: PLR2004
        return clipped.where(clipped.isna(), 0.0)
    return (clipped - clipped.mean()) / std


def score(components: pd.DataFrame, weights: Dict[str, float] = COMPONENT_WEIGHTS) -> pd.DataFrame:
    scored = components.copy()
    numerator = pd.Series(0.0, index=scored.index)
    denominator = pd.Series(0.0, index=scored.index)
    coverage = pd.Series(0, index=scored.index)
    for name, weight in weights.items():
        if name not in scored:
            scored[name] = np.nan
        z = zscore(scored[name].astype(float))
        scored[f"z_{name}"] = z
        present = z.notna()
        numerator = numerator + (weight * z).where(present, 0.0)
        denominator = denominator + present * abs(weight)
        coverage = coverage + present.astype(int)
    scored["composite"] = (numerator / denominator.where(denominator > 0)).astype(float)
    scored["coverage"] = coverage
    return scored.sort_values(["composite", "coverage"], ascending=[False, False], na_position="last")


def default_universe(db: BearishDbBase, as_of: datetime.date) -> List[str]:
    frame = db.read_query(
        "SELECT DISTINCT symbol FROM quarterlyfinancialmetrics "
        f"WHERE COALESCE(filed_date, created_at) <= '{as_of.isoformat()}'"
    )
    return sorted(frame["symbol"].astype(str)) if not frame.empty else []


def market_cap_filter(
    db: BearishDbBase, symbols: Sequence[str], min_market_cap: Optional[float], max_market_cap: Optional[float]
) -> List[str]:
    """Keep symbols inside the market-cap band (latest stored value; not point-in-time)."""
    if min_market_cap is None and max_market_cap is None:
        return list(symbols)
    frame = db.read_query(
        "SELECT symbol, MAX(market_capitalization) AS cap FROM equity "
        f"WHERE market_capitalization IS NOT NULL AND symbol IN ({_in_clause(symbols)}) GROUP BY symbol"
    )
    caps = dict(zip(frame["symbol"], frame["cap"], strict=True)) if not frame.empty else {}
    return [
        s
        for s in symbols
        if s in caps
        and (min_market_cap is None or caps[s] >= min_market_cap)
        and (max_market_cap is None or caps[s] <= max_market_cap)
    ]


def early_winner_screen(
    db: BearishDbBase,
    as_of: datetime.date,
    universe: Optional[List[str]] = None,
    min_market_cap: Optional[float] = None,
    max_market_cap: Optional[float] = None,
) -> pd.DataFrame:
    """Score ``universe`` (default: every symbol with statements known on ``as_of``) as of a date."""
    symbols = sorted({s.upper() for s in universe}) if universe else default_universe(db, as_of)
    symbols = market_cap_filter(db, symbols, min_market_cap, max_market_cap)
    if not symbols:
        return pd.DataFrame(columns=[*COMPONENT_WEIGHTS, "composite", "coverage"])
    parts = [
        fundamentals_components(db, symbols, as_of),
        ownership_components(db, symbols, as_of),
        insider_component(db, symbols, as_of),
        signal_components(db, symbols, as_of),
        momentum_components(db, symbols, as_of),
    ]
    components = pd.concat(parts, axis=1)
    components = components.loc[:, ~components.columns.duplicated()]
    scored = score(components)
    scored["as_of"] = as_of
    return scored
