"""Event-study engine: returns of an asset over trading-day windows around events.

Windows are offsets in *trading days* relative to the anchor, which is the
last close on or before the event date (US election results arrive after the
election-day close, so day 0 is the pre-result close). A window ``(a, b)``
returns ``close[t0 + b] / close[t0 + a] - 1`` in percent. Windows that would
start before the series begins or end after its last close are skipped, so
events before an asset's inception and windows still in the future simply
produce no row.

Summaries report n, mean, median, hit rate (share of positive returns),
standard deviation, a t-statistic and a 95 % bootstrap confidence interval of
the mean (fixed seed, so reruns are reproducible). With roughly twenty
midterms per asset, read the interval before the mean.
"""

import datetime
import logging
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import requests

from bearish.interface.interface import BearishDbBase
from bearish.signals.models import EventReturn, MarketEvent

logger = logging.getLogger(__name__)

Window = Tuple[int, int]

DEFAULT_WINDOWS: Tuple[Window, ...] = ((-60, 0), (-20, 0), (0, 20), (0, 60), (0, 120), (0, 250))
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 42
PRICE_TABLES = ("price", "priceindex", "priceetf", "pricecommodity")


def window_label(window: Window) -> str:
    start, end = window
    return f"{start:+d}..{end:+d}"


def _normalise(prices: pd.Series) -> pd.Series:
    series = pd.to_numeric(prices, errors="coerce").dropna()
    index = pd.to_datetime(series.index)
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)
    series.index = index.normalize()
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series[series > 0]


def _anchor(prices: pd.Series, day: datetime.date) -> Optional[int]:
    """Position of the last close on or before ``day``; None before the series starts."""
    position = int(prices.index.searchsorted(pd.Timestamp(day), side="right")) - 1
    return position if position >= 0 else None


def _window_return(
    prices: pd.Series, anchor: int, window: Window
) -> Optional[Tuple[float, datetime.date, datetime.date]]:
    start, end = anchor + window[0], anchor + window[1]
    if start < 0 or end >= len(prices):
        return None
    value = (float(prices.iloc[end]) / float(prices.iloc[start]) - 1.0) * 100.0
    return value, prices.index[start].date(), prices.index[end].date()


def event_window_returns(  # noqa: PLR0913
    prices: pd.Series,
    event: MarketEvent,
    asset: str,
    windows: Sequence[Window] = DEFAULT_WINDOWS,
    benchmark: Optional[pd.Series] = None,
    benchmark_name: Optional[str] = None,
    as_of: Optional[datetime.date] = None,
) -> List[EventReturn]:
    """Returns of ``prices`` over each window around ``event`` (and of the benchmark on the same dates)."""
    series = _normalise(prices)
    if series.empty or event.date < series.index[0].date():
        return []
    anchor = _anchor(series, event.date)
    if anchor is None:
        return []
    bench = _normalise(benchmark) if benchmark is not None else None
    as_of = as_of or datetime.date.today()
    rows: List[EventReturn] = []
    for window in windows:
        measured = _window_return(series, anchor, window)
        if measured is None:
            continue
        ret, start_date, end_date = measured
        bench_ret: Optional[float] = None
        if bench is not None:
            start_pos, end_pos = _anchor(bench, start_date), _anchor(bench, end_date)
            if start_pos is not None and end_pos is not None and bench.index[start_pos].date() == start_date:
                bench_ret = (float(bench.iloc[end_pos]) / float(bench.iloc[start_pos]) - 1.0) * 100.0
        rows.append(
            EventReturn(
                event_id=event.event_id,
                asset=asset,
                window=window_label(window),
                start_date=start_date,
                end_date=end_date,
                ret=ret,
                benchmark=benchmark_name if bench_ret is not None else None,
                benchmark_ret=bench_ret,
                excess_ret=ret - bench_ret if bench_ret is not None else None,
                as_of=as_of,
            )
        )
    return rows


def bootstrap_ci(values: np.ndarray, level: float = 0.95, samples: int = BOOTSTRAP_SAMPLES) -> Tuple[float, float]:
    if len(values) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    means = rng.choice(values, size=(samples, len(values)), replace=True).mean(axis=1)
    tail = (1.0 - level) / 2.0 * 100.0
    low, high = np.percentile(means, [tail, 100.0 - tail])
    return float(low), float(high)


def describe(values: Iterable[float]) -> Dict[str, float]:
    array = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    n = len(array)
    if n == 0:
        return {"n": 0.0}
    std = float(array.std(ddof=1)) if n > 1 else float("nan")
    low, high = bootstrap_ci(array)
    return {
        "n": float(n),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "hit_rate": float((array > 0).mean()),
        "std": std,
        "t_stat": float(array.mean() / (std / np.sqrt(n))) if n > 1 and std > 0 else float("nan"),
        "ci_low": low,
        "ci_high": high,
    }


def summarise_returns(
    returns: Sequence[EventReturn],
    events: Optional[Sequence[MarketEvent]] = None,
    group_tags: Sequence[str] = (),
    value: str = "ret",
) -> pd.DataFrame:
    """Summary per (group, asset, window).

    Group ``all`` covers every event; each tag in ``group_tags`` adds a group
    of the events carrying it and one (``not_<tag>``) of those that don't.
    ``value`` is ``ret`` or ``excess_ret``.
    """
    tags: Mapping[str, set[str]] = {e.event_id: e.tag_set() for e in events or []}
    groups: List[Tuple[str, Optional[str], bool]] = [("all", None, True)]
    for group_tag in group_tags:
        groups += [(group_tag, group_tag, True), (f"not_{group_tag}", group_tag, False)]
    records: List[Dict[str, object]] = []
    frame = pd.DataFrame([r.model_dump() for r in returns])
    if frame.empty:
        return pd.DataFrame()
    for (asset, window), rows in frame.groupby(["asset", "window"], sort=False):
        for name, tag, present in groups:
            if tag is None:
                selected = rows
            else:
                mask = rows["event_id"].map(lambda event_id, t=tag: t in tags.get(event_id, set())) == present
                selected = rows[mask]
            stats = describe(selected[value].dropna().tolist())
            if stats["n"] == 0:
                continue
            records.append({"group": name, "asset": asset, "window": window, **stats})
    return pd.DataFrame.from_records(records)


# --- price sources ----------------------------------------------------------------


def prices_from_db(db: BearishDbBase, symbol: str, table: str = "priceindex") -> pd.Series:
    """Close prices for ``symbol`` from one of bearish's price tables."""
    if table not in PRICE_TABLES:
        raise ValueError(f"Unknown price table {table}; expected one of {PRICE_TABLES}")
    quoted = symbol.replace("'", "''")
    frame = db.read_query(f"SELECT date, close FROM {table} WHERE symbol = '{quoted}' ORDER BY date")
    if frame.empty:
        return pd.Series(dtype=float)
    return _normalise(pd.Series(frame["close"].to_numpy(), index=pd.to_datetime(frame["date"])))


def prices_from_factor(db: BearishDbBase, market: str = "FF_MKT.USA", risk_free: str = "FF_RF.USA") -> pd.Series:
    """Total-return index (start = 100) from Ken French daily market excess return + risk-free, in percent."""
    frame = db.read_query(
        "SELECT o.series_id, o.date, o.value FROM macrolatest o "
        f"WHERE o.series_id IN ('{market}', '{risk_free}') ORDER BY o.date"
    )
    if frame.empty:
        return pd.Series(dtype=float)
    wide = frame.pivot_table(index="date", columns="series_id", values="value").sort_index()
    if market not in wide:
        return pd.Series(dtype=float)
    daily = wide[market] + wide.get(risk_free, 0.0)
    index = (1.0 + daily.dropna() / 100.0).cumprod() * 100.0
    index.index = pd.to_datetime(index.index)
    return _normalise(index)


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; bearish; +https://github.com/andoludo/bearish)"}
_YAHOO_START = -1325635200  # 1928-01-01, before the first ^GSPC close Yahoo serves


def prices_from_yahoo_chart(symbol: str, timeout: int = 60) -> pd.Series:
    """Adjusted daily closes from Yahoo's chart endpoint (no cookie/crumb, so it survives yfinance rate limits)."""
    response = requests.get(
        YAHOO_CHART_URL.format(symbol=symbol),
        params={
            "period1": str(_YAHOO_START),
            "period2": str(int(datetime.datetime.now(datetime.UTC).timestamp())),
            "interval": "1d",
            "events": "div,split",
        },
        headers=YAHOO_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    result = (response.json().get("chart", {}).get("result") or [None])[0]
    if not result or not result.get("timestamp"):
        return pd.Series(dtype=float)
    indicators = result.get("indicators", {})
    closes = (indicators.get("adjclose") or indicators.get("quote") or [{}])[0]
    values = closes.get("adjclose") or closes.get("close") or []
    timezone = result.get("meta", {}).get("exchangeTimezoneName") or "America/New_York"
    index = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert(timezone).tz_localize(None)
    return _normalise(pd.Series(values, index=index, dtype=float))


def prices_from_yfinance(symbol: str) -> pd.Series:
    """Full daily close history from Yahoo Finance (^GSPC goes back to 1927).

    Uses yfinance first and falls back to the chart endpoint when yfinance is
    rate limited or fails.
    """
    try:
        import yfinance as yf  # type: ignore

        history = yf.Ticker(symbol).history(period="max", auto_adjust=True)
        if not history.empty:
            return _normalise(history["Close"])
    except Exception as e:  # rate limits surface as several exception types
        logger.info(f"yfinance failed for {symbol} ({e}); using the Yahoo chart endpoint")
    return prices_from_yahoo_chart(symbol)
