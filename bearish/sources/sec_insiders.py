"""Insider transactions from SEC Form 4 filings.

Raw-data fetcher: every transaction line of every Form 4 (and 4/A) a company
filed is stored as an ``InsiderTransaction``. Aggregating into buy/sell
signals is downstream work.
"""

import datetime
import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterator, List, Optional, Tuple

import requests
from sec_cik_mapper import StockMapper  # type: ignore

from bearish.models.sec.insider import InsiderTransaction
from bearish.sources.edgar_filings import HEADERS, SUBMISSIONS_URL, cik_for_symbol
from bearish.types import DELAY

logger = logging.getLogger(__name__)

SUBMISSIONS_PAGE_URL = "https://data.sec.gov/submissions/{name}"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/index.json"
INSIDER_FORMS = ("4", "4/A")
RELATIONSHIP_FLAGS = (
    ("isDirector", "director"),
    ("isOfficer", "officer"),
    ("isTenPercentOwner", "ten_percent_owner"),
    ("isOther", "other"),
)

FilingRef = Tuple[str, datetime.date, str]  # accession number, filed date, primary document


def _text(element: Optional[ET.Element], path: str) -> Optional[str]:
    """Text of ``path`` under ``element``, accepting the ``<x><value>..</value></x>`` wrapper."""
    if element is None:
        return None
    node = element.find(path)
    if node is None:
        return None
    value = node.find("value")
    text = (value.text if value is not None else node.text) or ""
    return text.strip() or None


def _float(element: Optional[ET.Element], path: str) -> Optional[float]:
    text = _text(element, path)
    if text is None:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _bool(element: Optional[ET.Element], path: str) -> bool:
    return (_text(element, path) or "").lower() in {"1", "true"}


def _owner(root: ET.Element) -> Tuple[str, str, Optional[str]]:
    """Reporting owner name, comma-joined relationship flags and officer title.

    Multi-owner filings (joint filers) are attributed to the first owner.
    """
    owner = root.find("reportingOwner")
    name = _text(owner, "reportingOwnerId/rptOwnerName") or "UNKNOWN"
    relationship = owner.find("reportingOwnerRelationship") if owner is not None else None
    flags = [label for tag, label in RELATIONSHIP_FLAGS if _bool(relationship, tag)]
    return name, ",".join(flags) or "other", _text(relationship, "officerTitle")


def _transactions(root: ET.Element) -> Iterator[Tuple[ET.Element, bool]]:
    for element in root.iterfind("nonDerivativeTable/nonDerivativeTransaction"):
        yield element, False
    for element in root.iterfind("derivativeTable/derivativeTransaction"):
        yield element, True


def parse_form4(
    xml_text: str, symbol: str, cik: str, accession_number: str, filed_date: datetime.date
) -> List[InsiderTransaction]:
    """Parse one ownershipDocument into transaction rows (holdings-only lines are skipped)."""
    root = ET.fromstring(xml_text)  # noqa: S314 - SEC-hosted XML, parsed without external entities by ElementTree
    owner, relationship, title = _owner(root)
    rows: List[InsiderTransaction] = []
    for line_no, (element, is_derivative) in enumerate(_transactions(root), start=1):
        code = _text(element, "transactionCoding/transactionCode")
        transaction_date = _text(element, "transactionDate")
        shares = _float(element, "transactionAmounts/transactionShares")
        acquired_disposed = _text(element, "transactionAmounts/transactionAcquiredDisposedCode")
        if not code or not transaction_date or shares is None or acquired_disposed not in {"A", "D"}:
            continue
        price = _float(element, "transactionAmounts/transactionPricePerShare")
        rows.append(
            InsiderTransaction(
                symbol=symbol,
                cik=cik,
                accession_number=accession_number,
                line_no=line_no,
                filed_date=filed_date,
                transaction_date=datetime.date.fromisoformat(transaction_date[:10]),
                reporting_owner=owner,
                owner_relationship=relationship,
                officer_title=title,
                security_title=_text(element, "securityTitle") or "",
                transaction_code=code,
                acquired_disposed=acquired_disposed,
                shares=shares,
                price=price,
                value=shares * price if price is not None else None,
                shares_owned_after=_float(element, "postTransactionAmounts/sharesOwnedFollowingTransaction"),
                is_derivative=is_derivative,
            )
        )
    return rows


def insider_filings(payload: Dict[str, Any], since: Optional[datetime.date] = None) -> List[FilingRef]:
    """Form 4 references from a submissions page, newest first."""
    recent = payload.get("filings", {}).get("recent", payload)
    refs: List[FilingRef] = []
    rows = zip(
        recent.get("accessionNumber", []),
        recent.get("form", []),
        recent.get("filingDate", []),
        recent.get("primaryDocument", []),
        strict=True,
    )
    for accession_number, form, filing_date, document in rows:
        filed = datetime.date.fromisoformat(filing_date)
        if form not in INSIDER_FORMS or (since is not None and filed < since):
            continue
        refs.append((accession_number, filed, document))
    return refs


def xml_document_name(primary_document: str) -> Optional[str]:
    """The raw ownershipDocument behind a primary document path.

    EDGAR lists the rendered view (``xslF345X05/form4.xml``); the XML itself is
    the same file name without the stylesheet directory.
    """
    name = primary_document.rsplit("/", 1)[-1]
    return name if name.lower().endswith(".xml") else None


def _get(url: str, timeout: int = 30) -> requests.Response:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


def _find_xml_in_index(cik: str, accession: str) -> Optional[str]:
    index = _get(INDEX_URL.format(cik=int(cik), accession=accession)).json()
    for item in index.get("directory", {}).get("item", []):
        name = item.get("name", "")
        if name.lower().endswith(".xml") and not name.lower().startswith("xsl"):
            return str(name)
    return None


def fetch_form4(cik: str, accession_number: str, primary_document: str, timeout: int = 30) -> str:
    accession = accession_number.replace("-", "")
    document = xml_document_name(primary_document) or _find_xml_in_index(cik, accession)
    if document is None:
        raise ValueError(f"No XML document found for filing {accession_number}")
    return _get(ARCHIVE_URL.format(cik=int(cik), accession=accession, document=document), timeout).text


def _submission_pages(cik: str, since: Optional[datetime.date], pause: float) -> Iterator[Dict[str, Any]]:
    """The recent submissions page, then older pages while they may still cover ``since``."""
    payload = _get(SUBMISSIONS_URL.format(cik=cik)).json()
    yield payload
    if since is None:
        return
    recent_dates = payload.get("filings", {}).get("recent", {}).get("filingDate", [])
    oldest_recent = datetime.date.fromisoformat(min(recent_dates)) if recent_dates else since
    if oldest_recent <= since:
        return
    for page in payload.get("filings", {}).get("files", []):
        if datetime.date.fromisoformat(page["filingTo"]) < since:
            continue
        time.sleep(pause)
        yield _get(SUBMISSIONS_PAGE_URL.format(name=page["name"])).json()


def fetch_insider_transactions(
    symbols: List[str],
    since: Optional[datetime.date] = None,
    pause: float = DELAY,
    max_filings: int = 50,
) -> List[InsiderTransaction]:
    """Form 4 transactions for symbols with a known CIK.

    ``max_filings`` caps the number of filings fetched per symbol (newest
    first) so a first run on a heavily traded name stays bounded; raise it
    or pass ``since`` for a full backfill. Per-filing failures are logged
    and skipped.
    """
    mapper = StockMapper()
    transactions: List[InsiderTransaction] = []
    for symbol in symbols:
        cik = cik_for_symbol(symbol, mapper)
        if cik is None:
            logger.debug(f"No CIK found for {symbol}; skipping insider transactions")
            continue
        try:
            refs: List[FilingRef] = []
            for page in _submission_pages(cik, since, pause):
                refs.extend(insider_filings(page, since))
                if len(refs) >= max_filings:
                    break
        except Exception as e:
            logger.error(f"Error listing Form 4 filings for {symbol}: {e}")
            continue
        for accession_number, filed, document in refs[:max_filings]:
            try:
                xml_text = fetch_form4(cik, accession_number, document)
                transactions.extend(parse_form4(xml_text, symbol, cik, accession_number, filed))
            except Exception as e:
                logger.error(f"Error parsing Form 4 {accession_number} for {symbol}: {e}")
            time.sleep(pause)
    return transactions
