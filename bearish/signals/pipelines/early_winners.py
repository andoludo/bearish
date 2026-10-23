"""Fetch-and-store orchestration for the early-winner signals and the screen."""

import datetime
import logging
from typing import Dict, List, Optional, Sequence

import pandas as pd

from bearish.interface.interface import BearishDbBase
from bearish.signals.capex import HYPERSCALERS, build_capex_signals
from bearish.signals.screen import early_winner_screen
from bearish.signals.sources.edgar_themes import fetch_theme_mentions, theme_filings_series
from bearish.signals.sources.finra import fetch_short_interest, fetch_short_volume
from bearish.signals.sources.usaspending import fetch_federal_awards
from bearish.signals.themes import themes_by_key

logger = logging.getLogger(__name__)


def write_theme_mentions(
    db: BearishDbBase,
    symbols: Optional[List[str]] = None,
    themes: Optional[Sequence[str]] = None,
    start: Optional[datetime.date] = None,
    end: Optional[datetime.date] = None,
) -> Dict[str, int]:
    """Quarterly theme mentions per company plus the market-wide THEME_FILINGS series.

    ``symbols=None`` stores counts for every filer that mentions a theme.
    """
    selected = themes_by_key(tuple(themes) if themes else None)
    start = start or datetime.date.today() - datetime.timedelta(days=2 * 365)
    signals, observations = fetch_theme_mentions(selected, start, end, symbols)
    db.write_macro_series([theme_filings_series(theme) for theme in selected])
    return {
        "ticker_signals": db.write_ticker_signals(signals),
        "observations": db.write_observations(observations),
    }


def write_capex_signals(db: BearishDbBase, symbols: Optional[Sequence[str]] = None) -> int:
    return db.write_ticker_signals(build_capex_signals(db, symbols, HYPERSCALERS))


def write_short_data(db: BearishDbBase, symbols: List[str], days: int = 20, history_days: int = 400) -> Dict[str, int]:
    """Short interest (``history_days`` back) and daily short-volume ratios (``days`` back)."""
    start = datetime.date.today() - datetime.timedelta(days=history_days)
    return {
        "short_interest": db.write_ticker_signals(fetch_short_interest(symbols, start)),
        "short_volume": db.write_ticker_signals(fetch_short_volume(days, symbols)),
    }


def company_names(db: BearishDbBase, symbols: Sequence[str]) -> Dict[str, str]:
    """Company names for symbols: the equity table first, the SEC ticker file as fallback."""
    quoted = ",".join("'" + s.upper().replace("'", "''") + "'" for s in symbols)
    frame = db.read_query(f"SELECT symbol, name FROM equity WHERE name IS NOT NULL AND symbol IN ({quoted})")
    names = {str(r.symbol): str(r.name) for r in frame.itertuples(index=False)} if not frame.empty else {}
    missing = [s.upper() for s in symbols if s.upper() not in names]
    if missing:
        from sec_cik_mapper import StockMapper  # type: ignore

        sec_names: Dict[str, str] = dict(StockMapper().ticker_to_company_name)  # type: ignore[operator]
        names.update({s: sec_names[s] for s in missing if s in sec_names})
    return names


def write_federal_awards(db: BearishDbBase, symbols: List[str], years: int = 2) -> int:
    start = datetime.date.today() - datetime.timedelta(days=365 * years)
    names = company_names(db, symbols)
    unknown = sorted({s.upper() for s in symbols} - set(names))
    if unknown:
        logger.warning(f"No company name for {unknown}; skipped for federal awards")
    return db.write_ticker_signals(fetch_federal_awards(names, start))


def run_screen(  # noqa: PLR0913
    db: BearishDbBase,
    as_of: Optional[datetime.date] = None,
    universe: Optional[List[str]] = None,
    min_market_cap: Optional[float] = None,
    max_market_cap: Optional[float] = None,
    top: Optional[int] = None,
) -> pd.DataFrame:
    """Refresh capex signals from stored statements, then score the universe."""
    write_capex_signals(db)
    frame = early_winner_screen(
        db, as_of or datetime.date.today(), universe, min_market_cap=min_market_cap, max_market_cap=max_market_cap
    )
    return frame.head(top) if top else frame
