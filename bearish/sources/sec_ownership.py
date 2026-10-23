"""Beneficial ownership from SEC Schedule 13D / 13G filings.

Raw-data fetcher: every reporting person on every structured ``SCHEDULE 13D``,
``SCHEDULE 13D/A``, ``SCHEDULE 13G`` and ``SCHEDULE 13G/A`` filed about a
company is stored as an ``Ownership13DG`` row (shares, percent of class,
voting/dispositive powers, event and filing dates).

Only the XML era is covered: since December 2024 these schedules are filed
as structured ``primary_doc.xml``. The older free-text ``SC 13D`` / ``SC 13G``
HTML and TXT filings are skipped, so ``since`` defaults to 2024-12-01.

Element mapping (local names, namespaces ignored):

================  ===================================================  ===========================================
field             Schedule 13G                                         Schedule 13D
================  ===================================================  ===========================================
event_date        eventDateRequiresFilingThisStatement                 dateOfEvent
issuer_cik        issuerInfo/issuerCik                                 issuerInfo/issuerCIK
issuer_name       issuerInfo/issuerName                                issuerInfo/issuerName
issuer_cusip      issuerCusips/issuerCusipNumber                       issuerCusips/issuerCusipNumber
rule              designateRulePursuantThisScheduleFiled               (none)
person block      coverPageHeaderReportingPersonDetails                reportingPersons/reportingPersonInfo
reporting_person  reportingPersonName                                  reportingPersonName
shares_owned      reportingPersonBeneficiallyOwnedAggregateNumberOfShares aggregateAmountOwned
percent_of_class  classPercent                                         percentOfClass
powers            reportingPersonBeneficiallyOwnedNumberOfShares/*     soleVotingPower, ... (direct children)
person_type       typeOfReportingPerson (repeatable, comma-joined)     typeOfReportingPerson
================  ===================================================  ===========================================
"""

import datetime
import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterator, List, Optional

from sec_cik_mapper import StockMapper  # type: ignore

from bearish.models.sec.holdings import Ownership13DG
from bearish.sources.edgar_filings import cik_for_symbol
from bearish.sources.sec_insiders import ARCHIVE_URL, FilingRef, _get, _submission_pages
from bearish.types import DELAY

logger = logging.getLogger(__name__)

OWNERSHIP_FORMS = ("SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A")
XML_ERA_START = datetime.date(2024, 12, 1)
PRIMARY_DOCUMENT = "primary_doc.xml"

_PERSON_BLOCKS = ("coverPageHeaderReportingPersonDetails", "reportingPersonInfo")
_EVENT_DATE = ("eventDateRequiresFilingThisStatement", "dateOfEvent")
_SHARES_OWNED = ("reportingPersonBeneficiallyOwnedAggregateNumberOfShares", "aggregateAmountOwned")
_PERCENT = ("classPercent", "percentOfClass")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, *names: str) -> Iterator[ET.Element]:
    """Descendants of ``element`` whose local name is one of ``names``, document order."""
    wanted = set(names)
    for node in element.iter():
        if node is not element and _local(node.tag) in wanted:
            yield node


def _text(element: ET.Element, *names: str) -> Optional[str]:
    for node in _children(element, *names):
        text = (node.text or "").strip()
        if text:
            return text
    return None


def _texts(element: ET.Element, *names: str) -> List[str]:
    return [text for node in _children(element, *names) if (text := (node.text or "").strip())]


def _number(element: ET.Element, *names: str) -> Optional[float]:
    text = _text(element, *names)
    if text is None:
        return None
    try:
        return float(text.replace(",", "").rstrip("%"))
    except ValueError:
        return None


def _date(text: Optional[str]) -> Optional[datetime.date]:
    if not text:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _person_blocks(root: ET.Element) -> Iterator[ET.Element]:
    """Reporting-person blocks; the 13G cover block comes first so the 13D variant is a fallback."""
    for name in _PERSON_BLOCKS:
        blocks = list(_children(root, name))
        if blocks:
            yield from blocks
            return


def parse_schedule_13dg(
    xml_text: str, symbol: str, accession_number: str, form_type: str, filed_date: datetime.date
) -> List[Ownership13DG]:
    """One row per reporting person of a Schedule 13D/13G XML document."""
    root = ET.fromstring(xml_text)  # noqa: S314 - SEC-hosted XML, parsed without external entities by ElementTree
    issuer = next(iter(_children(root, "issuerInfo")), root)
    issuer_cik = _text(issuer, "issuerCik", "issuerCIK") or ""
    issuer_name = _text(issuer, "issuerName")
    issuer_cusip = _text(issuer, "issuerCusipNumber")
    event_date = _date(_text(root, *_EVENT_DATE))
    rule = _text(root, "designateRulePursuantThisScheduleFiled")
    rows: List[Ownership13DG] = []
    for block in _person_blocks(root):
        name = _text(block, "reportingPersonName")
        if not name:
            continue
        types = _texts(block, "typeOfReportingPerson")
        rows.append(
            Ownership13DG(
                accession_number=accession_number,
                symbol=symbol,
                issuer_cik=issuer_cik,
                issuer_name=issuer_name,
                issuer_cusip=issuer_cusip,
                form_type=form_type,
                filed_date=filed_date,
                event_date=event_date,
                reporting_person=name,
                person_type=",".join(types) or None,
                percent_of_class=_number(block, *_PERCENT),
                shares_owned=_number(block, *_SHARES_OWNED),
                sole_voting=_number(block, "soleVotingPower"),
                shared_voting=_number(block, "sharedVotingPower"),
                sole_dispositive=_number(block, "soleDispositivePower"),
                shared_dispositive=_number(block, "sharedDispositivePower"),
                rule=rule,
                is_amendment=form_type.endswith("/A"),
            )
        )
    return rows


OwnershipRef = tuple[str, datetime.date, str, str]  # accession, filed date, primary document, form type


def ownership_filings(payload: Dict[str, Any], since: Optional[datetime.date] = None) -> List[OwnershipRef]:
    """Structured Schedule 13D/13G references from a submissions page, newest first.

    Legacy ``SC 13D`` / ``SC 13G`` rows are not returned: they have no XML.
    """
    recent = payload.get("filings", {}).get("recent", payload)
    refs: List[OwnershipRef] = []
    rows = zip(
        recent.get("accessionNumber", []),
        recent.get("form", []),
        recent.get("filingDate", []),
        recent.get("primaryDocument", []),
        strict=True,
    )
    for accession_number, form, filing_date, document in rows:
        filed = datetime.date.fromisoformat(filing_date)
        if form not in OWNERSHIP_FORMS or (since is not None and filed < since):
            continue
        refs.append((accession_number, filed, document, form))
    return refs


def fetch_schedule_13dg(cik: str, accession_number: str, primary_document: str, timeout: int = 30) -> str:
    """The raw XML behind a rendered ``xslSCHEDULE_13G_X02/primary_doc.xml`` path."""
    document = primary_document.rsplit("/", 1)[-1] or PRIMARY_DOCUMENT
    accession = accession_number.replace("-", "")
    return _get(ARCHIVE_URL.format(cik=int(cik), accession=accession, document=document), timeout).text


def fetch_ownership(
    symbols: List[str],
    since: Optional[datetime.date] = None,
    pause: float = DELAY,
    max_filings: int = 100,
) -> List[Ownership13DG]:
    """Schedule 13D/13G rows for symbols with a known CIK.

    ``max_filings`` caps the filings fetched per symbol (newest first);
    per-filing failures are logged and skipped. The old ``FilingRef`` tuple
    shape is extended with the form type because 13D and 13G rows are stored
    together.
    """
    since = since or XML_ERA_START
    mapper = StockMapper()
    rows: List[Ownership13DG] = []
    for symbol in symbols:
        cik = cik_for_symbol(symbol, mapper)
        if cik is None:
            logger.debug(f"No CIK found for {symbol}; skipping Schedule 13D/13G")
            continue
        try:
            refs: List[OwnershipRef] = []
            for page in _submission_pages(cik, since, pause):
                refs.extend(ownership_filings(page, since))
                if len(refs) >= max_filings:
                    break
        except Exception as e:
            logger.error(f"Error listing Schedule 13D/13G filings for {symbol}: {e}")
            continue
        for accession_number, filed, document, form in refs[:max_filings]:
            try:
                xml_text = fetch_schedule_13dg(cik, accession_number, document)
                rows.extend(parse_schedule_13dg(xml_text, symbol, accession_number, form, filed))
            except Exception as e:
                logger.error(f"Error parsing {form} {accession_number} for {symbol}: {e}")
            time.sleep(pause)
    return rows


__all__ = [
    "OWNERSHIP_FORMS",
    "FilingRef",
    "OwnershipRef",
    "fetch_ownership",
    "fetch_schedule_13dg",
    "ownership_filings",
    "parse_schedule_13dg",
]
