"""Fetch 10-K / 10-Q filing metadata from the SEC EDGAR submissions API.

Raw-data fetcher only: it records which statements were filed when
(accession number, form type, period of report, filed date). No metric is
computed here; joining filings onto statements beyond the exact
(symbol, period_end) filed_date backfill is downstream (bullish) work.
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
FILING_FORMS = ("10-K", "10-Q")


def parse_submissions(payload: Dict[str, Any], symbol: str, cik: str) -> List[Filing]:
    """Turn one EDGAR submissions JSON payload into Filing rows.

    Only 10-K/10-Q forms are kept, and rows without a period of report are
    skipped (the period is what statements are matched on).
    """
    recent = payload.get("filings", {}).get("recent", {})
    filings = []
    rows = zip(
        recent.get("accessionNumber", []),
        recent.get("form", []),
        recent.get("reportDate", []),
        recent.get("filingDate", []),
        strict=True,
    )
    for accession_number, form, report_date, filing_date in rows:
        if form not in FILING_FORMS or not report_date or not filing_date:
            continue
        filings.append(
            Filing(
                symbol=symbol,
                cik=cik,
                form_type=form,
                period_end=datetime.strptime(report_date, "%Y-%m-%d").date(),
                filed_date=datetime.strptime(filing_date, "%Y-%m-%d").date(),
                accession_number=accession_number,
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
    """Fetch 10-K/10-Q filing metadata for symbols with a known CIK.

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
