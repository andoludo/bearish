"""Theme mentions in SEC filings via EDGAR full-text search (EFTS).

``https://efts.sec.gov/LATEST/search-index`` searches the text of every
EDGAR document filed since 2001. For a theme and a calendar quarter one query
(``"phrase one" OR "phrase two"``, forms 10-K/10-Q/8-K, filing-date range) is
paginated 100 hits at a time. Hits are *documents* (a filing's main document
and each exhibit), so they are de-duplicated by accession number: the counts
are numbers of filings, not of documents.

From one market-wide pass per (theme, quarter) two measures are built:

* per company: ``TickerSignal(signal="THEME_MENTIONS:<theme>")`` = filings
  that quarter mentioning the theme, for every filer (CIK -> ticker through
  ``sec_cik_mapper``), optionally restricted to given symbols;
* market-wide: ``THEME_FILINGS.<THEME>`` observations for the macro store =
  all filings mentioning the theme that quarter.

EFTS stops paginating at 10,000 hits. When a quarter exceeds that, the
market-wide count falls back to the reported total (documents, an upper
bound) and per-company counts cover the first 10,000 hits only; this is
logged and visible as ``FilingHits.truncated``.
"""

import datetime
import logging
import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import requests
from pydantic import BaseModel, Field
from sec_cik_mapper import StockMapper  # type: ignore
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from bearish.macro.catalog._builder import series
from bearish.macro.models import MacroSeries, Observation
from bearish.signals.models import TickerSignal
from bearish.signals.themes import Theme, theme_signal
from bearish.sources.edgar_filings import HEADERS

logger = logging.getLogger(__name__)

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
FORMS = "10-K,10-Q,8-K"
PAGE_SIZE = 100
EFTS_MAX_HITS = 10_000
# SEC fair-access limit is 10 requests per second.
DEFAULT_PAUSE = 0.15


class RetryableError(Exception):
    """EFTS answered 429 or 5xx."""


class FilingHit(BaseModel):
    adsh: str
    ciks: Tuple[str, ...]
    file_date: datetime.date
    form: str


class FilingHits(BaseModel):
    theme: str
    quarter_end: datetime.date
    hits: List[FilingHit] = Field(default_factory=list)
    total_documents: int = 0
    truncated: bool = False

    def filings(self) -> int:
        if self.truncated:
            return self.total_documents
        return len({hit.adsh for hit in self.hits})

    def filings_per_cik(self) -> Dict[str, int]:
        per_cik: Dict[str, Set[str]] = defaultdict(set)
        for hit in self.hits:
            for cik in hit.ciks:
                per_cik[cik].add(hit.adsh)
        return {cik: len(accessions) for cik, accessions in per_cik.items()}


def quarters(start: datetime.date, end: datetime.date) -> List[Tuple[datetime.date, datetime.date]]:
    """Calendar quarters overlapping [start, end] as (first day, last day), clipped to ``end``."""
    result: List[Tuple[datetime.date, datetime.date]] = []
    year, quarter = start.year, (start.month - 1) // 3
    while True:
        first = datetime.date(year, 3 * quarter + 1, 1)
        if first > end:
            return result
        next_first = datetime.date(year + (quarter + 1) // 4, (3 * (quarter + 1)) % 12 + 1, 1)
        result.append((first, min(next_first - datetime.timedelta(days=1), end)))
        year, quarter = next_first.year, (next_first.month - 1) // 3


def quarter_end(day: datetime.date) -> datetime.date:
    first_of_next = datetime.date(day.year + (day.month - 1) // 9, ((day.month - 1) // 3 * 3 + 3) % 12 + 1, 1)
    return first_of_next - datetime.timedelta(days=1)


def parse_hits(payload: Dict[str, Any]) -> Tuple[List[FilingHit], int, bool]:
    """Hits on one page, the total reported by EFTS and whether it is a lower bound."""
    block = payload.get("hits", {})
    total = block.get("total", {})
    hits = []
    for item in block.get("hits", []):
        source = item.get("_source", {})
        adsh = source.get("adsh") or str(item.get("_id", "")).split(":", 1)[0]
        if not adsh or not source.get("file_date"):
            continue
        hits.append(
            FilingHit(
                adsh=adsh,
                ciks=tuple(str(cik).zfill(10) for cik in source.get("ciks", [])),
                file_date=datetime.date.fromisoformat(source["file_date"]),
                form=source.get("form", ""),
            )
        )
    return hits, int(total.get("value", 0)), total.get("relation") == "gte"


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, RetryableError)),
)
def _search(params: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    response = requests.get(EFTS_URL, params=params, headers=HEADERS, timeout=timeout)
    if response.status_code == 429 or response.status_code >= 500:  # noqa: PLR2004
        raise RetryableError(f"EFTS returned {response.status_code}")
    response.raise_for_status()
    payload: Dict[str, Any] = response.json()
    if "hits" not in payload:
        # EFTS occasionally answers 200 with an error body under load.
        raise RetryableError(f"EFTS returned no hits block: {str(payload)[:200]}")
    return payload


def fetch_theme_hits(
    theme: Theme,
    start: datetime.date,
    end: datetime.date,
    ciks: Optional[List[str]] = None,
    pause: float = DEFAULT_PAUSE,
) -> FilingHits:
    """Every filing hit for ``theme`` filed in [start, end], paginated up to the EFTS cap."""
    params: Dict[str, Any] = {
        "q": theme.edgar_query(),
        "forms": FORMS,
        "dateRange": "custom",
        "startdt": start.isoformat(),
        "enddt": end.isoformat(),
    }
    if ciks:
        params["ciks"] = ",".join(cik.zfill(10) for cik in ciks)
    result = FilingHits(theme=theme.key, quarter_end=quarter_end(end))
    offset = 0
    while True:
        page, total, lower_bound = parse_hits(_search({**params, "from": offset}))
        result.total_documents = total
        result.hits.extend(page)
        offset += PAGE_SIZE
        if not page or offset >= total or offset >= EFTS_MAX_HITS:
            break
        time.sleep(pause)
    if total > EFTS_MAX_HITS or lower_bound:
        result.truncated = True
        logger.warning(f"EFTS capped {theme.key} {start}..{end}: {total}+ documents, per-company counts are partial")
    return result


def cik_to_symbols(mapper: Optional[StockMapper] = None) -> Dict[str, Tuple[str, ...]]:
    mapper = mapper if mapper is not None else StockMapper()
    raw: Dict[str, Iterable[str]] = dict(mapper.cik_to_tickers)  # type: ignore[operator]
    return {str(cik).zfill(10): tuple(sorted(tickers)) for cik, tickers in raw.items()}


def ticker_signals(
    hits: FilingHits,
    cik_symbols: Dict[str, Tuple[str, ...]],
    as_of: datetime.date,
    symbols: Optional[Set[str]] = None,
) -> List[TickerSignal]:
    """Per-company quarterly mention counts; a symbol in ``symbols`` with no hit gets an explicit 0."""
    counts: Dict[str, int] = {}
    for cik, filings in hits.filings_per_cik().items():
        for symbol in cik_symbols.get(cik, ()):
            if symbols is None or symbol in symbols:
                counts[symbol] = max(counts.get(symbol, 0), filings)
    for symbol in symbols or ():
        counts.setdefault(symbol, 0)
    return [
        TickerSignal(
            symbol=symbol,
            signal=theme_signal(hits.theme),
            date=hits.quarter_end,
            value=float(count),
            as_of=as_of,
            source="SEC",
        )
        for symbol, count in sorted(counts.items())
    ]


def theme_filings_series(theme: Theme) -> MacroSeries:
    return series(
        "THEME_FILINGS",
        theme.key.upper(),
        "EDGAR",
        f"efts:{theme.key}",
        "Q",
        entity_type="theme",
        description=f"SEC filings (10-K/10-Q/8-K) per quarter mentioning: {theme.label}",
    )


def theme_filings_observation(theme: Theme, hits: FilingHits, as_of: datetime.date) -> Observation:
    # Macro convention: periods are stored on their first day.
    first_day = datetime.date(hits.quarter_end.year, hits.quarter_end.month - 2, 1)
    return Observation(
        series_id=theme_filings_series(theme).series_id,
        date=first_day,
        value=float(hits.filings()),
        as_of=as_of,
    )


def fetch_theme_mentions(  # noqa: PLR0913
    themes: Iterable[Theme],
    start: datetime.date,
    end: Optional[datetime.date] = None,
    symbols: Optional[List[str]] = None,
    pause: float = DEFAULT_PAUSE,
    mapper: Optional[StockMapper] = None,
) -> Tuple[List[TickerSignal], List[Observation]]:
    """Quarterly theme mentions per company and market-wide, for every quarter in [start, end]."""
    end = end or datetime.date.today()
    as_of = datetime.date.today()
    cik_symbols = cik_to_symbols(mapper)
    wanted = {symbol.upper() for symbol in symbols} if symbols else None
    signals: List[TickerSignal] = []
    observations: List[Observation] = []
    for theme in themes:
        for first, last in quarters(start, end):
            hits = fetch_theme_hits(theme, first, last, pause=pause)
            signals.extend(ticker_signals(hits, cik_symbols, as_of, wanted))
            observations.append(theme_filings_observation(theme, hits, as_of))
            time.sleep(pause)
    return signals, observations
