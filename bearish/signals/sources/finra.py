"""FINRA short-selling data, keyless.

* **Consolidated short interest** (twice a month, settlement dates mid-month
  and month-end; published about a week later):
  ``POST https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest``
  with a ``domainFilters`` list of symbols and a ``dateRangeFilters`` range on
  ``settlementDate``; pages of up to 5,000 rows, total in the
  ``record-total`` response header. Produces ``SHORT_INTEREST`` (shares),
  ``DAYS_TO_COVER`` and ``SHORT_INTEREST_CHG`` (% vs the previous settlement).
* **Daily Reg SHO short volume** (consolidated NMS file per trading day):
  ``https://cdn.finra.org/equity/regsho/daily/CNMSshvol{YYYYMMDD}.txt``,
  pipe-separated ``Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market``.
  Produces ``SHORT_VOLUME_RATIO`` = ShortVolume / TotalVolume. Weekends and
  holidays have no file (404) and are skipped.

Short interest is dated on its settlement date but is only public on FINRA's
dissemination date, about eight business days later; ``as_of`` is therefore
``settlement + PUBLICATION_LAG`` (or the fetch date if earlier) so screens do
not see it before it was published.
"""

import datetime
import io
import logging
import time
from typing import Any, Dict, Iterable, List, Optional, Set

import pandas as pd
import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from bearish.signals.models import TickerSignal
from bearish.utils.utils import batch

logger = logging.getLogger(__name__)

SHORT_INTEREST_URL = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
SHORT_VOLUME_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{day:%Y%m%d}.txt"
HEADERS = {"User-Agent": "bearish (https://github.com/andoludo/bearish)", "Accept": "application/json"}
PAGE_LIMIT = 5000
SYMBOLS_PER_REQUEST = 200
PUBLICATION_LAG = datetime.timedelta(days=12)
SOURCE = "FINRA"


class RetryableError(Exception):
    """FINRA answered 429 or 5xx."""


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, RetryableError)),
)
def _post(body: Dict[str, Any], timeout: int = 60) -> requests.Response:
    response = requests.post(SHORT_INTEREST_URL, json=body, headers=HEADERS, timeout=timeout)
    if response.status_code == 429 or response.status_code >= 500:  # noqa: PLR2004
        raise RetryableError(f"FINRA returned {response.status_code}")
    response.raise_for_status()
    return response


def short_interest_rows(
    symbols: List[str], start: datetime.date, end: datetime.date, pause: float = 0.5
) -> List[Dict[str, Any]]:
    """Raw consolidated short-interest rows for ``symbols`` with settlement dates in [start, end]."""
    rows: List[Dict[str, Any]] = []
    for chunk in batch(sorted({s.upper() for s in symbols}), SYMBOLS_PER_REQUEST):
        offset = 0
        while True:
            body = {
                "limit": PAGE_LIMIT,
                "offset": offset,
                "domainFilters": [{"fieldName": "symbolCode", "values": chunk}],
                "dateRangeFilters": [
                    {"fieldName": "settlementDate", "startDate": start.isoformat(), "endDate": end.isoformat()}
                ],
            }
            response = _post(body)
            page: List[Dict[str, Any]] = response.json() if response.content else []
            rows.extend(page)
            total = int(response.headers.get("record-total", len(page)))
            offset += PAGE_LIMIT
            if not page or offset >= total:
                break
            time.sleep(pause)
        time.sleep(pause)
    return rows


def short_interest_signals(rows: Iterable[Dict[str, Any]], fetched_on: datetime.date) -> List[TickerSignal]:
    signals: List[TickerSignal] = []
    for row in rows:
        settlement = datetime.date.fromisoformat(str(row["settlementDate"])[:10])
        as_of = min(settlement + PUBLICATION_LAG, fetched_on)
        symbol = str(row["symbolCode"]).upper()
        values = {
            "SHORT_INTEREST": row.get("currentShortPositionQuantity"),
            "DAYS_TO_COVER": row.get("daysToCoverQuantity"),
            "SHORT_INTEREST_CHG": row.get("changePercent"),
        }
        for signal, value in values.items():
            if value is None:
                continue
            signals.append(
                TickerSignal(
                    symbol=symbol, signal=signal, date=settlement, value=float(value), as_of=as_of, source=SOURCE
                )
            )
    return signals


def fetch_short_interest(
    symbols: List[str], start: datetime.date, end: Optional[datetime.date] = None, pause: float = 0.5
) -> List[TickerSignal]:
    end = end or datetime.date.today()
    return short_interest_signals(short_interest_rows(symbols, start, end, pause), datetime.date.today())


def parse_short_volume(text: str, symbols: Optional[Set[str]] = None) -> List[TickerSignal]:
    """``SHORT_VOLUME_RATIO`` per symbol from one daily Reg SHO file (available the same evening)."""
    frame = pd.read_csv(io.StringIO(text), sep="|", dtype={"Date": str, "Symbol": str})
    frame = frame.dropna(subset=["Symbol", "ShortVolume", "TotalVolume"])
    frame = frame[pd.to_numeric(frame["TotalVolume"], errors="coerce") > 0]
    if symbols is not None:
        frame = frame[frame["Symbol"].str.upper().isin(symbols)]
    signals: List[TickerSignal] = []
    for record in frame.to_dict("records"):
        day = datetime.datetime.strptime(str(record["Date"]), "%Y%m%d").date()
        ratio = float(record["ShortVolume"]) / float(record["TotalVolume"])
        signals.append(
            TickerSignal(
                symbol=str(record["Symbol"]),
                signal="SHORT_VOLUME_RATIO",
                date=day,
                value=ratio,
                as_of=day,
                source=SOURCE,
            )
        )
    return signals


def fetch_short_volume(
    days: int = 20,
    symbols: Optional[List[str]] = None,
    end: Optional[datetime.date] = None,
    pause: float = 0.3,
) -> List[TickerSignal]:
    """Short-volume ratios for the last ``days`` calendar days (non-trading days are skipped)."""
    end = end or datetime.date.today()
    wanted = {s.upper() for s in symbols} if symbols else None
    signals: List[TickerSignal] = []
    for offset in range(days):
        day = end - datetime.timedelta(days=offset)
        if day.weekday() >= 5:  # noqa: PLR2004
            continue
        response = requests.get(SHORT_VOLUME_URL.format(day=day), headers=HEADERS, timeout=60)
        if response.status_code in (403, 404):
            logger.debug(f"No FINRA short volume file for {day}")
            continue
        response.raise_for_status()
        signals.extend(parse_short_volume(response.text, wanted))
        time.sleep(pause)
    return signals
