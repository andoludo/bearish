"""Fetch 10-K / 10-Q / 8-K filing metadata from the SEC EDGAR submissions API.

Raw-data fetcher only: it records which filings were submitted when
(accession number, form type, period of report or event date, filed date)
and, for 8-Ks, the item codes EDGAR lists (``2.02`` results, ``4.02``
restatement, ``5.02`` officer departure, ...). No metric is computed here;
joining filings onto statements beyond the exact (symbol, period_end)
filed_date backfill is downstream (bullish) work.
"""
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from sec_cik_mapper import StockMapper  # type: ignore

from bearish.models.sec.filing import Filing
from bearish.types import DELAY

logger = logging.getLogger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
# SEC requires a descriptive User-Agent; same convention as models/sec/sec.py
HEADERS = {"User-Agent": "YourName Contact@Email.com", "Accept": "application/json"}
STATEMENT_FORMS = ("10-K", "10-Q")
EVENT_FORMS = ("8-K",)
FILING_FORMS = STATEMENT_FORMS + EVENT_FORMS


def _normalise_items(value: Optional[str]) -> Optional[str]:
    codes = [code.strip() for code in (value or "").split(",") if code.strip()]
    return ",".join(codes) or None


def parse_submissions(payload: Dict[str, Any], symbol: str, cik: str) -> List[Filing]:
    """Turn one EDGAR submissions JSON payload into Filing rows.

    10-K / 10-Q rows need a period of report (statements are matched on it);
    8-K rows use the report date as event date and fall back to the filing
    date when EDGAR gives none. Other forms are skipped.
    """
    recent = payload.get("filings", {}).get("recent", {})
    accession_numbers = recent.get("accessionNumber", [])
    filings = []
    rows = zip(
        accession_numbers,
        recent.get("form", []),
        recent.get("reportDate", []),
        recent.get("filingDate", []),
        recent.get("items", [None] * len(accession_numbers)),
        strict=True,
    )
    for accession_number, form, report_date, filing_date, items in rows:
        if form not in FILING_FORMS or not filing_date:
            continue
        if form in STATEMENT_FORMS and not report_date:
            continue
        filings.append(
            Filing(
                symbol=symbol,
                cik=cik,
                form_type=form,
                period_end=datetime.strptime(report_date or filing_date, "%Y-%m-%d").date(),
                filed_date=datetime.strptime(filing_date, "%Y-%m-%d").date(),
                accession_number=accession_number,
                items=_normalise_items(items) if form in EVENT_FORMS else None,
            )
        )
    return filings


def cik_for_symbol(symbol: str, mapper: Optional[StockMapper] = None) -> Optional[str]:
    mapper = mapper if mapper is not None else StockMapper()
    # sec_cik_mapper decorates the property in a way its own stubs mistype
    mapping: Dict[str, str] = dict(mapper.ticker_to_cik)  # type: ignore[operator]
    cik = mapping.get(symbol.upper())
    return str(cik).zfill(10) if cik else None


def fetch_filings(symbols: List[str], pause: float = DELAY) -> List[Filing]:
    """Fetch 10-K / 10-Q / 8-K filing metadata for symbols with a known CIK.

    Non-US symbols (no CIK) are skipped silently; per-symbol failures are
    logged and skipped so one bad ticker does not abort the run.
    """
    mapper = StockMapper()
    filings: List[Filing] = []
    for symbol in symbols:
        cik = cik_for_symbol(symbol, mapper)
        if cik is None:
            logger.debug(f"No CIK found for {symbol}; skipping EDGAR filings")
            continue
        try:
            response = requests.get(
                SUBMISSIONS_URL.format(cik=cik), headers=HEADERS, timeout=30
            )
            response.raise_for_status()
            filings.extend(parse_submissions(response.json(), symbol, cik))
        except Exception as e:
            logger.error(f"Error fetching EDGAR filings for {symbol}: {e}")
        time.sleep(pause)
    return filings
