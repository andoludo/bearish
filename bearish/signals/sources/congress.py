"""Congressional stock trades from House Periodic Transaction Reports (STOCK Act).

The House Clerk publishes one zip per year
(``https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip``)
holding an XML index of every financial-disclosure filing (member, state and
district, filing type, date, DocID). Periodic Transaction Reports have
FilingType ``P`` and are PDFs at
``https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{DocID}.pdf``.

Electronically filed PTRs carry a text layer: each transaction is an asset
line (``Apple Inc. - Common Stock (AAPL) [ST]``, optionally prefixed by an
owner code SP/JT/DC) followed by ``<type> <transaction date> <notification
date> <amount range>``. Scanned paper filings have no text layer and are
skipped and counted. The Senate's eFD system requires an interactive
terms-of-use acceptance per session, so Senate trades are not fetched.
"""

import datetime
import io
import logging
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from typing import List, Optional, Tuple

import requests
from pydantic import BaseModel, Field

from bearish.signals.models import CongressTrade

logger = logging.getLogger(__name__)

INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
PTR_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
HEADERS = {"User-Agent": "bearish (https://github.com/andoludo/bearish)"}
SOURCE = "HouseClerk"

_TRANSACTION = re.compile(
    r"(?P<prefix>.*?)\b(?P<type>P|S \(partial\)|S|E)\s+(?P<tdate>\d{2}/\d{2}/\d{4})\s+(?P<ndate>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<amount>\$[\d,]+\s*-\s*(?:\$[\d,]+)?|Over \$[\d,]+|\$[\d,]+\s*\+?)\s*(?P<rest>.*)$"
)
_LABEL = re.compile(r"^(?:[A-Z]\s){0,4}[A-Z]\s?:")
_TITLE = re.compile(r"^(?:[A-Z]\s)*[A-Z]$")
_HEADER_LINES = ("Type", "Date", "$200?")
_HEADER_PREFIXES = ("ID Owner Asset", "Date Notification", "Amount Cap.", "Gains >")
_NOISE_PREFIXES = (
    "Clerk of the House",
    "Name:",
    "Status:",
    "State/District:",
    "Filing ID",
    "* For the complete",
    "Digitally Signed",
)
_TICKER_PAREN = re.compile(r"\(([A-Z][A-Z0-9.\-/]{0,9})\)")
_TICKER_EXCHANGE = re.compile(r"(?:NYSE(?:ARCA|MKT)?|NASDAQ|BATS|CBOE)\s*:\s*([A-Z][A-Z0-9.\-]{0,9})")
_OWNER = re.compile(r"^(SP|JT|DC)\s+")
_MAX_ASSET_LINES = 4


class PtrFiling(BaseModel):
    doc_id: str
    member: str
    state_district: Optional[str] = None
    filed_date: datetime.date
    year: int


class HouseTradesResult(BaseModel):
    trades: List[CongressTrade] = Field(default_factory=list)
    filings: int = 0
    parsed: int = Field(default=0, description="Filings with a text layer and at least one transaction")
    scanned: int = Field(default=0, description="Filings without a text layer (paper / scanned)")
    failed: int = 0


def _date(value: str) -> Optional[datetime.date]:
    try:
        return datetime.datetime.strptime(value.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


def parse_index(xml_text: str) -> List[PtrFiling]:
    """Periodic Transaction Reports listed in a ``{year}FD.xml`` index."""
    root = ET.fromstring(xml_text.lstrip("﻿"))  # noqa: S314
    filings: List[PtrFiling] = []
    for member in root.iter("Member"):
        if (member.findtext("FilingType") or "").strip() != "P":
            continue
        filed = _date(member.findtext("FilingDate") or "")
        doc_id = (member.findtext("DocID") or "").strip()
        if filed is None or not doc_id:
            continue
        name = " ".join(
            part.strip()
            for part in (member.findtext("First") or "", member.findtext("Last") or "", member.findtext("Suffix") or "")
            if part and part.strip()
        )
        filings.append(
            PtrFiling(
                doc_id=doc_id,
                member=name,
                state_district=(member.findtext("StateDst") or "").strip() or None,
                filed_date=filed,
                year=int(member.findtext("Year") or filed.year),
            )
        )
    return filings


def _amount_range(text: str) -> Tuple[Optional[float], Optional[float]]:
    numbers = [float(n.replace(",", "")) for n in re.findall(r"\$([\d,]+)", text)]
    if not numbers:
        return None, None
    if text.strip().lower().startswith("over"):
        return numbers[0], None
    if len(numbers) == 1:
        return numbers[0], None if "-" in text else numbers[0]
    return numbers[0], numbers[1]


def _symbol(asset: str) -> Optional[str]:
    found: List[str] = _TICKER_EXCHANGE.findall(asset) or _TICKER_PAREN.findall(asset)
    return found[-1].replace("/", ".") if found else None


def _clean_lines(text: str) -> List[str]:
    text = text.replace("\x00", "").replace("•", "-")
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if line:
            lines.append(line)
    return lines


def _is_boundary(line: str) -> bool:
    return (
        bool(_LABEL.match(line))
        or bool(_TITLE.match(line))
        or line in _HEADER_LINES
        or line.startswith(_HEADER_PREFIXES)
        or line.startswith(_NOISE_PREFIXES)
        or " @ $" in line
        or "shares sold" in line
        or "shares purchased" in line
    )


def parse_ptr_text(text: str, filing: PtrFiling) -> List[CongressTrade]:
    """Transactions in the text layer of one PTR."""
    lines = _clean_lines(text)
    trades: List[CongressTrade] = []
    asset_lines: List[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = _TRANSACTION.match(line)
        if match is None or not (match.group("prefix").strip() or asset_lines):
            asset_lines = [] if _is_boundary(line) else [*asset_lines, line][-_MAX_ASSET_LINES:]
            index += 1
            continue
        amount = match.group("amount").strip()
        if amount.endswith("-") and index + 1 < len(lines) and lines[index + 1].startswith("$"):
            amount = f"{amount} {lines[index + 1].split()[0]}"
            index += 1
        asset = " ".join([*asset_lines, match.group("prefix").strip()]).strip()
        owner_match = _OWNER.match(asset)
        owner = owner_match.group(1) if owner_match else None
        asset = _OWNER.sub("", asset)
        low, high = _amount_range(amount)
        trades.append(
            CongressTrade(
                doc_id=filing.doc_id,
                line_no=len(trades) + 1,
                chamber="House",
                member=filing.member,
                state_district=filing.state_district,
                owner=owner,
                symbol=_symbol(asset),
                asset_description=asset,
                transaction_type=match.group("type"),
                transaction_date=_date(match.group("tdate")),
                notification_date=_date(match.group("ndate")),
                filed_date=filing.filed_date,
                amount_min=low,
                amount_max=high,
                source=SOURCE,
            )
        )
        asset_lines = []
        index += 1
    return trades


def pdf_text(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _get(url: str, timeout: int = 60) -> requests.Response:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


def fetch_ptr_index(year: int) -> List[PtrFiling]:
    with zipfile.ZipFile(io.BytesIO(_get(INDEX_URL.format(year=year)).content)) as archive:
        name = next(n for n in archive.namelist() if n.lower().endswith(".xml"))
        return parse_index(archive.read(name).decode("utf-8", errors="replace"))


def fetch_house_trades(
    year: int,
    since: Optional[datetime.date] = None,
    max_filings: int = 200,
    pause: float = 0.5,
) -> HouseTradesResult:
    """Trades from the ``max_filings`` newest House PTRs of ``year`` filed on/after ``since``."""
    filings = sorted(
        (f for f in fetch_ptr_index(year) if since is None or f.filed_date >= since),
        key=lambda f: f.filed_date,
        reverse=True,
    )[:max_filings]
    result = HouseTradesResult(filings=len(filings))
    for filing in filings:
        time.sleep(pause)
        try:
            text = pdf_text(_get(PTR_URL.format(year=filing.year, doc_id=filing.doc_id)).content)
        except Exception as e:  # one unreadable PDF must not stop the run
            logger.warning(f"PTR {filing.doc_id} could not be read: {e}")
            result.failed += 1
            continue
        if not text.replace("\x00", "").strip():
            result.scanned += 1
            continue
        trades = parse_ptr_text(text, filing)
        if trades:
            result.parsed += 1
            result.trades.extend(trades)
    return result
