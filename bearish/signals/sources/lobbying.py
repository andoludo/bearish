"""Federal lobbying spend per company from the Lobbying Disclosure Act API.

``https://lda.gov/api/v1/filings/?client_name=...&filing_year=...`` (the
former lda.senate.gov address redirects there) lists quarterly LD-2 reports
(types Q1-Q4, amendments 1A-4A; semiannual MM/YE before 2008). Each report
names a registrant (the lobbying firm, or the company itself when lobbying
in-house) and a client:

* an outside firm reports the ``income`` it received from the client;
* a self-filing company reports its total ``expenses``, which by LDA rules
  already include what it paid outside firms.

So a quarter's spend is the self-filed expenses when the company files in
house, else the sum of the outside firms' income. Per (registrant, period)
the latest report wins, so an amendment replaces the original. The signal is
``LOBBYING_USD`` dated at the period end, with ``as_of`` = the posting date of
the newest report used: what was public at that time.

Clients are matched to symbols by normalised company name (legal suffixes and
punctuation removed, casefolded).
"""

import datetime
import logging
import re
import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import requests

from bearish.signals.models import TickerSignal

logger = logging.getLogger(__name__)

LDA_URL = "https://lda.gov/api/v1/filings/"
HEADERS = {"User-Agent": "bearish (https://github.com/andoludo/bearish)", "Accept": "application/json"}
SIGNAL = "LOBBYING_USD"
SOURCE = "LDA"
REPORT_TYPES = re.compile(r"^(Q[1-4]|[1-4]A|MM|MA|YE|YA)$")
_PERIOD_END = {
    "first_quarter": (3, 31),
    "second_quarter": (6, 30),
    "third_quarter": (9, 30),
    "fourth_quarter": (12, 31),
    "mid_year": (6, 30),
    "year_end": (12, 31),
}
_SUFFIXES = re.compile(
    r"\b(incorporated|inc|corporation|corp|company|co|llc|l\.l\.c|ltd|limited|plc|holdings?|group|the|n\.?v|s\.?a|ag|lp|l\.p)\b\.?",
    re.IGNORECASE,
)


def normalize_company_name(name: str) -> str:
    text = re.sub(r"\(.*?\)", " ", name)
    text = text.replace("&", " and ").replace(".com", " com")
    text = _SUFFIXES.sub(" ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def period_end(filing_year: int, filing_period: str) -> Optional[datetime.date]:
    month_day = _PERIOD_END.get(filing_period)
    return datetime.date(filing_year, *month_day) if month_day else None


def _amount(value: Any) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _posted(filing: Mapping[str, Any]) -> datetime.date:
    return datetime.datetime.fromisoformat(str(filing["dt_posted"])).date()


def quarterly_spend(filings: Iterable[Mapping[str, Any]], symbol: str, client_key: str) -> List[TickerSignal]:
    """Aggregate the LD-2 reports of one client into per-period spend signals."""
    latest: Dict[Tuple[datetime.date, str], Mapping[str, Any]] = {}
    for filing in filings:
        if not REPORT_TYPES.match(str(filing.get("filing_type") or "")):
            continue
        if normalize_company_name(str((filing.get("client") or {}).get("name") or "")) != client_key:
            continue
        end = period_end(int(filing["filing_year"]), str(filing.get("filing_period") or ""))
        if end is None:
            continue
        registrant = normalize_company_name(str((filing.get("registrant") or {}).get("name") or ""))
        key = (end, registrant)
        if key not in latest or _posted(filing) >= _posted(latest[key]):
            latest[key] = filing

    per_period: Dict[datetime.date, List[Mapping[str, Any]]] = defaultdict(list)
    for (end, _), filing in latest.items():
        per_period[end].append(filing)

    signals: List[TickerSignal] = []
    for end, reports in sorted(per_period.items()):
        in_house = [
            _amount(r.get("expenses"))
            for r in reports
            if normalize_company_name(str((r.get("registrant") or {}).get("name") or "")) == client_key
            and _amount(r.get("expenses")) is not None
        ]
        outside = [_amount(r.get("income")) for r in reports if _amount(r.get("income")) is not None]
        values = in_house or outside
        if not values:
            continue
        signals.append(
            TickerSignal(
                symbol=symbol,
                signal=SIGNAL,
                date=end,
                value=float(sum(v for v in values if v is not None)),
                as_of=max(_posted(r) for r in reports),
                source=SOURCE,
            )
        )
    return signals


def fetch_client_filings(
    client_name: str, year: int, pause: float = 2.0, timeout: int = 60, retries: int = 4
) -> List[Dict[str, Any]]:
    """Every LD filing for ``client_name`` (the API matches substrings) in ``year``, following pagination."""
    url: Optional[str] = LDA_URL
    params: Optional[Dict[str, Any]] = {"client_name": client_name, "filing_year": year, "page_size": 25}
    filings: List[Dict[str, Any]] = []
    attempt = 0
    while url:
        time.sleep(pause)
        response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        if response.status_code == 429 and attempt < retries:  # noqa: PLR2004
            attempt += 1
            retry_after = _amount(response.headers.get("Retry-After"))
            time.sleep(retry_after if retry_after is not None else 10.0 * attempt)
            continue
        response.raise_for_status()
        payload = response.json()
        filings.extend(payload.get("results") or [])
        url, params, attempt = payload.get("next"), None, 0
    return filings


def company_names(symbols: Sequence[str], names: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Company name per symbol: explicit names first, then the SEC ticker file."""
    resolved = {s: n for s, n in (names or {}).items() if n}
    missing = [s for s in symbols if s not in resolved]
    if missing:
        from sec_cik_mapper import StockMapper  # type: ignore

        mapping: Dict[str, str] = dict(StockMapper().ticker_to_company_name)  # type: ignore[operator]
        resolved.update({s: mapping[s.upper()] for s in missing if s.upper() in mapping})
    return resolved


def fetch_lobbying(
    symbols: Sequence[str],
    years: Sequence[int],
    names: Optional[Mapping[str, str]] = None,
    pause: float = 2.0,
) -> List[TickerSignal]:
    """``LOBBYING_USD`` per symbol and period for the given filing years."""
    signals: List[TickerSignal] = []
    for symbol, name in company_names(symbols, names).items():
        client_key = normalize_company_name(name)
        if not client_key:
            continue
        for year in years:
            try:
                filings = fetch_client_filings(client_key, year, pause=pause)
            except requests.RequestException as e:
                logger.warning(f"LDA lookup for {symbol} ({name}) {year} failed: {e}")
                continue
            signals.extend(quarterly_spend(filings, symbol, client_key))
    return signals
