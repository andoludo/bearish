"""Technology-adoption series per theme: research output and corporate attention.

* ``ArxivSource`` — monthly number of arXiv papers whose abstract contains a
  theme phrase. One API call per theme-month (``max_results=1``: the API
  answers 500 to ``max_results=0``; the count is ``opensearch:totalResults``);
  arXiv asks for at most one request every
  three seconds, so the default window is the last 36 months.
* ``EdgarThemeSource`` — quarterly number of SEC filings mentioning a theme,
  from EDGAR full-text search (see ``bearish.signals.sources.edgar_themes``).
  The early-winner pipeline writes the same series alongside per-company
  counts from a single pass; this source lets ``bearish macro`` refresh the
  market-wide series on its own.

Catalog ``source_code``: ``arxiv:<theme>`` / ``efts:<theme>``.
"""

import datetime
import logging
import re
from typing import List, Optional

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.signals.sources.edgar_themes import fetch_theme_hits, quarters, theme_filings_observation
from bearish.signals.themes import THEMES

logger = logging.getLogger(__name__)

ARXIV_URL = "https://export.arxiv.org/api/query"
ARXIV_DEFAULT_MONTHS = 36
EDGAR_DEFAULT_QUARTERS = 8
_TOTAL = re.compile(r"<opensearch:totalResults[^>]*>(\d+)</opensearch:totalResults>")


def month_starts(start: datetime.date, end: datetime.date) -> List[datetime.date]:
    months = []
    current = datetime.date(start.year, start.month, 1)
    while current <= end:
        months.append(current)
        current = datetime.date(current.year + current.month // 12, current.month % 12 + 1, 1)
    return months


def month_end(first: datetime.date) -> datetime.date:
    following = datetime.date(first.year + first.month // 12, first.month % 12 + 1, 1)
    return following - datetime.timedelta(days=1)


def parse_total_results(feed: str) -> int:
    match = _TOTAL.search(feed)
    if match is None:
        raise ValueError("arXiv response has no opensearch:totalResults")
    return int(match.group(1))


def _theme_key(macro_series: MacroSeries) -> str:
    return macro_series.source_code.split(":", 1)[1]


class ArxivSource(AbstractMacroSource):
    __source__ = "arXiv"
    pause: float = 3.0

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        today = self.today()
        first = start or month_starts(today - datetime.timedelta(days=31 * ARXIV_DEFAULT_MONTHS), today)[0]
        observations: List[Observation] = []
        for macro_series in series:
            theme = THEMES.get(_theme_key(macro_series))
            query = theme.arxiv_query() if theme else None
            if query is None:
                logger.warning(f"No arXiv query for {macro_series.series_id}")
                continue
            for month in month_starts(first, today):
                window = f"[{month:%Y%m%d}0000 TO {month_end(month):%Y%m%d}2359]"
                feed = self._get(
                    ARXIV_URL,
                    params={"search_query": f"({query}) AND submittedDate:{window}", "max_results": 1},
                ).text
                observations.append(
                    Observation(
                        series_id=macro_series.series_id,
                        date=month,
                        value=float(parse_total_results(feed)),
                        as_of=today,
                    )
                )
        return observations


class EdgarThemeSource(AbstractMacroSource):
    __source__ = "EDGAR"
    pause: float = 0.15

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        today = self.today()
        first = start or today - datetime.timedelta(days=92 * EDGAR_DEFAULT_QUARTERS)
        observations: List[Observation] = []
        for macro_series in series:
            theme = THEMES.get(_theme_key(macro_series))
            if theme is None:
                logger.warning(f"Unknown theme for {macro_series.series_id}")
                continue
            for quarter_start, quarter_last in quarters(first, today):
                hits = fetch_theme_hits(theme, quarter_start, quarter_last, pause=self.pause)
                self.api_usage.add_api_calls(1)
                observations.append(theme_filings_observation(theme, hits, today))
        return observations
