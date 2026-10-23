"""Fetch-and-store orchestration for elections, FOMC meetings, prediction
markets, congressional trades and lobbying, plus the midterm event study."""

import datetime
import logging
from typing import Callable, Dict, List, Literal, Optional, Sequence

import pandas as pd

from bearish.interface.interface import BearishDbBase
from bearish.signals.elections import US_ELECTIONS, midterms
from bearish.signals.event_study import (
    DEFAULT_WINDOWS,
    Window,
    event_window_returns,
    prices_from_db,
    prices_from_factor,
    prices_from_yfinance,
    summarise_returns,
)
from bearish.signals.fomc import fetch_fomc_meetings
from bearish.signals.models import EventReturn, MarketEvent
from bearish.signals.sources.congress import HouseTradesResult, fetch_house_trades
from bearish.signals.sources.lobbying import fetch_lobbying
from bearish.signals.sources.prediction import (
    ELECTION_QUERIES,
    GEOPOLITICS_QUERIES,
    PredictionQuery,
    fetch_prediction_quotes,
)

logger = logging.getLogger(__name__)

PriceSource = Literal["yfinance", "db", "factor"]
BENCHMARK = "^GSPC"
SECTOR_SPDRS = ("XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC")
DEFAULT_ASSETS = (BENCHMARK, *SECTOR_SPDRS)
MIDTERM_GROUP_TAGS = ("divided", "pres_party_lost_house")


def write_election_events(db: BearishDbBase) -> int:
    db.write_events(list(US_ELECTIONS))
    return len(US_ELECTIONS)


def write_fomc_events(db: BearishDbBase, start_year: int = 1994) -> int:
    events = fetch_fomc_meetings(start_year)
    db.write_events(events)
    return len(events)


def _loader(db: BearishDbBase, price_source: PriceSource) -> Callable[[str], pd.Series]:
    if price_source == "yfinance":
        return prices_from_yfinance
    if price_source == "factor":
        return lambda asset: prices_from_factor(db, asset)
    return lambda asset: prices_from_db(db, asset, "priceindex" if asset.startswith("^") else "priceetf")


def run_event_study(  # noqa: PLR0913
    db: BearishDbBase,
    events: Sequence[MarketEvent],
    assets: Sequence[str] = DEFAULT_ASSETS,
    windows: Sequence[Window] = DEFAULT_WINDOWS,
    price_source: PriceSource = "yfinance",
    benchmark: Optional[str] = BENCHMARK,
    group_tags: Sequence[str] = (),
) -> pd.DataFrame:
    """Measure, store and summarise returns of ``assets`` around ``events``.

    The summary has one row per (measure, group, asset, window); ``measure`` is
    ``ret`` (raw return) or ``excess_ret`` (minus the benchmark over the same dates).
    """
    load = _loader(db, price_source)

    def safe_load(asset: str) -> Optional[pd.Series]:
        try:
            return load(asset)
        except Exception as e:  # one unavailable asset must not stop the study
            logger.warning(f"Could not load prices for {asset}: {e}")
            return None

    bench_prices = safe_load(benchmark) if benchmark else None
    returns: List[EventReturn] = []
    for asset in assets:
        prices = bench_prices if asset == benchmark and bench_prices is not None else safe_load(asset)
        if prices is None or prices.empty:
            logger.warning(f"No prices for {asset}; skipped in the event study")
            continue
        use_bench = bench_prices if asset != benchmark else None
        for event in events:
            returns.extend(
                event_window_returns(
                    prices,
                    event,
                    asset,
                    windows,
                    benchmark=use_bench,
                    benchmark_name=benchmark if use_bench is not None else None,
                )
            )
    db.write_event_returns(returns)
    frames = []
    for measure in ("ret", "excess_ret"):
        summary = summarise_returns(returns, events, group_tags, value=measure)
        if not summary.empty:
            frames.append(summary.assign(measure=measure))
    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    return result[["measure", *[c for c in result.columns if c != "measure"]]]


def run_midterm_study(
    db: BearishDbBase,
    assets: Sequence[str] = DEFAULT_ASSETS,
    windows: Sequence[Window] = DEFAULT_WINDOWS,
    price_source: PriceSource = "yfinance",
) -> pd.DataFrame:
    """Event study over every completed US midterm: all, divided vs unified after, president's party lost the House."""
    write_election_events(db)
    return run_event_study(db, midterms(), assets, windows, price_source, BENCHMARK, MIDTERM_GROUP_TAGS)


def write_prediction_quotes(
    db: BearishDbBase,
    queries: Sequence[PredictionQuery] = ELECTION_QUERIES + GEOPOLITICS_QUERIES,
    pause: float = 1.0,
) -> int:
    quotes = fetch_prediction_quotes(queries, pause=pause)
    db.write_prediction_quotes(quotes)
    return len(quotes)


def write_congress_trades(
    db: BearishDbBase,
    year: Optional[int] = None,
    since: Optional[datetime.date] = None,
    max_filings: int = 200,
    pause: float = 0.5,
) -> HouseTradesResult:
    result = fetch_house_trades(year or datetime.date.today().year, since=since, max_filings=max_filings, pause=pause)
    db.write_congress_trades(result.trades)
    return result


def _equity_names(db: BearishDbBase, symbols: Sequence[str]) -> Dict[str, str]:
    if not symbols:
        return {}
    quoted = ",".join("'" + s.replace("'", "''") + "'" for s in symbols)
    frame = db.read_query(f"SELECT symbol, name FROM equity WHERE symbol IN ({quoted}) AND name IS NOT NULL")
    return {str(row.symbol): str(row.name) for row in frame.itertuples(index=False)}


def write_lobbying(db: BearishDbBase, symbols: Sequence[str], years: Sequence[int], pause: float = 2.0) -> int:
    """``LOBBYING_USD`` ticker signals; company names from the equity table, else the SEC ticker file."""
    signals = fetch_lobbying(symbols, years, names=_equity_names(db, symbols), pause=pause)
    return db.write_ticker_signals(signals)
