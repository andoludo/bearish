"""Federal contract obligations per company from USAspending.gov (keyless).

For each symbol and calendar quarter one ``POST
/api/v2/search/spending_by_category/recipient/`` call (contracts: award types
A-D, action dates inside the quarter) returns obligations per recipient whose
name contains the company's search text. Recipient search is a substring
match, so results are filtered back to the company: a recipient is kept when
its normalised name equals the company's normalised name, or equals it
followed only by a known subsidiary qualifier (``ORACLE AMERICA``, ``PALANTIR
USG``, ``LOCKHEED MARTIN SPACE``), matched on the core name with legal
suffixes and a trailing generic word removed (``Palantir Technologies`` ->
``PALANTIR``). ``ORACLE ELEVATOR HOLDCO`` is dropped.
This is a heuristic: unusual subsidiary names are missed, which under- rather
than over-states awards.

Produces quarterly ``FED_AWARDS_USD`` TickerSignals (obligations net of
de-obligations, so a quarter can be negative). USAspending revises recent
quarters as agencies report; refetches are stored as new vintages.
"""

import datetime
import logging
import re
import time
from typing import Any, Dict, Iterable, List, Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from bearish.signals.models import TickerSignal
from bearish.signals.sources.edgar_themes import quarter_end, quarters

logger = logging.getLogger(__name__)

RECIPIENT_URL = "https://api.usaspending.gov/api/v2/search/spending_by_category/recipient/"
HEADERS = {"User-Agent": "bearish (https://github.com/andoludo/bearish)", "Content-Type": "application/json"}
CONTRACT_TYPES = ["A", "B", "C", "D"]
PAGE_LIMIT = 100
SOURCE = "USAspending"

_LEGAL_SUFFIXES = (
    "INCORPORATED",
    "INC",
    "CORPORATION",
    "CORP",
    "COMPANY",
    "CO",
    "LIMITED",
    "LTD",
    "LLC",
    "L L C",
    "PLC",
    "LP",
    "NV",
    "SA",
    "AG",
    "HOLDINGS",
    "HOLDING",
    "GROUP",
    "THE",
    "CLASS A",
    "CLASS B",
    "COMMON STOCK",
)
SUBSIDIARY_QUALIFIERS = {
    "AMERICA",
    "AMERICAS",
    "USA",
    "US",
    "USG",
    "FEDERAL",
    "FEDERAL SYSTEMS",
    "GOVERNMENT",
    "GOVERNMENT SERVICES",
    "GOVERNMENT SOLUTIONS",
    "HEALTH GOVERNMENT SERVICES",
    "PUBLIC SECTOR",
    "TECHNOLOGIES",
    "TECHNOLOGY",
    "SOLUTIONS",
    "SYSTEMS",
    "SERVICES",
    "INTERNATIONAL",
    "GLOBAL",
    "NORTH AMERICA",
    "DEFENSE",
    "SPACE",
    "AERONAUTICS",
    "MISSION SYSTEMS",
    "CLOUD",
    "SECURITY",
}
_NON_ALNUM = re.compile(r"[^A-Z0-9 ]+")
_SPACES = re.compile(r"\s+")


def normalise_name(name: str) -> str:
    """Upper-case, strip punctuation and trailing legal suffixes: 'Oracle Corp.' -> 'ORACLE'."""
    text = _SPACES.sub(" ", _NON_ALNUM.sub(" ", name.upper().replace("&", " AND "))).strip()
    changed = True
    while changed and text:
        changed = False
        for suffix in _LEGAL_SUFFIXES:
            if text.endswith(" " + suffix) or text == suffix:
                text = text[: -len(suffix)].strip()
                changed = True
    return text


def core_name(company: str) -> str:
    """Company name without legal suffixes or a trailing generic qualifier: 'Palantir Technologies' -> 'PALANTIR'."""
    name = normalise_name(company)
    for qualifier in sorted(SUBSIDIARY_QUALIFIERS, key=len, reverse=True):
        if name.endswith(" " + qualifier):
            return name[: -len(qualifier) - 1]
    return name


def belongs_to(recipient: str, company: str) -> bool:
    """True when the recipient is the company or one of its plainly named subsidiaries."""
    recipient_norm, core = normalise_name(recipient), core_name(company)
    if not core:
        return False
    if recipient_norm in (core, normalise_name(company)):
        return True
    if not recipient_norm.startswith(core + " "):
        return False
    return recipient_norm[len(core) + 1 :] in SUBSIDIARY_QUALIFIERS


class RetryableError(Exception):
    """USAspending answered 429 or 5xx."""


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, RetryableError)),
)
def _post(body: Dict[str, Any], timeout: int = 90) -> Dict[str, Any]:
    response = requests.post(RECIPIENT_URL, json=body, headers=HEADERS, timeout=timeout)
    if response.status_code == 429 or response.status_code >= 500:  # noqa: PLR2004
        raise RetryableError(f"USAspending returned {response.status_code}")
    response.raise_for_status()
    payload: Dict[str, Any] = response.json()
    return payload


def recipient_amounts(company: str, start: datetime.date, end: datetime.date) -> List[Dict[str, Any]]:
    body = {
        "filters": {
            "recipient_search_text": [core_name(company)],
            "time_period": [{"start_date": start.isoformat(), "end_date": end.isoformat()}],
            "award_type_codes": CONTRACT_TYPES,
        },
        "limit": PAGE_LIMIT,
        "page": 1,
    }
    results: List[Dict[str, Any]] = _post(body).get("results", [])
    return results


def company_total(results: Iterable[Dict[str, Any]], company: str) -> float:
    return float(
        sum(float(row.get("amount") or 0.0) for row in results if belongs_to(str(row.get("name", "")), company))
    )


def fetch_federal_awards(
    companies: Dict[str, str],
    start: datetime.date,
    end: Optional[datetime.date] = None,
    pause: float = 0.5,
) -> List[TickerSignal]:
    """Quarterly contract obligations for ``{symbol: company name}``."""
    end = end or datetime.date.today()
    as_of = datetime.date.today()
    signals: List[TickerSignal] = []
    for symbol, company in companies.items():
        for first, last in quarters(start, end):
            try:
                total = company_total(recipient_amounts(company, first, last), company)
            except requests.HTTPError as e:
                logger.error(f"USAspending failed for {symbol} {first}: {e}")
                continue
            signals.append(
                TickerSignal(
                    symbol=symbol,
                    signal="FED_AWARDS_USD",
                    date=quarter_end(last),
                    value=total,
                    as_of=as_of,
                    source=SOURCE,
                )
            )
            time.sleep(pause)
    return signals
