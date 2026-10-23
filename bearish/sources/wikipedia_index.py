"""Index constituents from the Wikipedia constituent tables.

No keyless API publishes index membership; the Wikipedia pages of the major
indices carry a maintained ``constituents`` table with the ticker in local
exchange notation. Each ``IndexPage`` says which page to read, which column
holds the ticker and how to turn it into the Yahoo Finance symbol used in
the ``equity`` / ``price`` tables (suffix for the exchange, ``.`` → ``-``
for US share classes). Membership is stored as a dated snapshot in
``indexmember``.
"""

import datetime
import logging
import re
import time
from io import StringIO
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import requests
from pydantic import BaseModel, ConfigDict, Field

from bearish.models.assets.index_members import IndexMember
from bearish.types import DELAY

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "bearish (https://github.com/andoludo/bearish) python-requests"}
SYMBOL_COLUMNS = ("Symbol", "Ticker", "Ticker symbol", "Code", "Stock symbol")
NAME_COLUMNS = ("Security", "Company", "Name", "Constituent", "Company name")
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,11}$")


class IndexPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    index_symbol: str
    url: str
    suffix: str = Field(default="", description="Exchange suffix appended to each ticker, e.g. .DE")
    strip_prefix: str = Field(default="", description="Exchange prefix some pages put in front, e.g. 'NYSE: '")
    dot_to_dash: bool = Field(default=False, description="US share classes: BRK.B → BRK-B")
    table_id: str = "constituents"


INDEX_PAGES: Tuple[IndexPage, ...] = (
    IndexPage(index_symbol="^GSPC", url="https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", dot_to_dash=True),
    IndexPage(index_symbol="^NDX", url="https://en.wikipedia.org/wiki/Nasdaq-100", dot_to_dash=True),
    IndexPage(index_symbol="^DJI", url="https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average", dot_to_dash=True),
    IndexPage(index_symbol="^GDAXI", url="https://en.wikipedia.org/wiki/DAX"),
    IndexPage(index_symbol="^FCHI", url="https://en.wikipedia.org/wiki/CAC_40"),
    IndexPage(index_symbol="^BFX", url="https://en.wikipedia.org/wiki/BEL_20"),
    IndexPage(index_symbol="^AEX", url="https://en.wikipedia.org/wiki/AEX_index"),
    IndexPage(index_symbol="^FTSE", url="https://en.wikipedia.org/wiki/FTSE_100_Index", suffix=".L"),
    IndexPage(index_symbol="^STOXX50E", url="https://en.wikipedia.org/wiki/EURO_STOXX_50"),
    IndexPage(index_symbol="^SSMI", url="https://en.wikipedia.org/wiki/Swiss_Market_Index"),
    IndexPage(index_symbol="^IBEX", url="https://en.wikipedia.org/wiki/IBEX_35", suffix=".MC"),
    IndexPage(index_symbol="FTSEMIB.MI", url="https://en.wikipedia.org/wiki/FTSE_MIB", suffix=".MI"),
    IndexPage(index_symbol="^N225", url="https://en.wikipedia.org/wiki/Nikkei_225", suffix=".T"),
)


def _first_column(frame: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    columns = {str(column).strip().casefold(): str(column) for column in frame.columns}
    for candidate in candidates:
        if candidate.casefold() in columns:
            return columns[candidate.casefold()]
    return None


def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [str(level[-1]) for level in frame.columns]
    return frame


def _constituent_table(html: str, page: IndexPage) -> Optional[pd.DataFrame]:
    """The table with ``id=constituents``, or the first table with a ticker column."""
    try:
        tables = pd.read_html(StringIO(html), attrs={"id": page.table_id}, flavor="bs4")
    except ValueError:
        tables = []
    if not tables:
        try:
            tables = [t for t in pd.read_html(StringIO(html), flavor="bs4") if _first_column(t, SYMBOL_COLUMNS)]
        except ValueError:
            tables = []
    return _flatten_columns(tables[0]) if tables else None


def normalise_symbol(raw: Any, page: IndexPage) -> Optional[str]:
    """Yahoo symbol from the page's ticker cell, ``None`` when the cell is not a ticker."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if page.strip_prefix and text.startswith(page.strip_prefix):
        text = text[len(page.strip_prefix) :]
    text = text.split(":")[-1].strip().upper()  # "NYSE: MMM" → "MMM"
    text = text.replace(chr(0xA0), "").replace(" ", "")
    if not _SYMBOL_PATTERN.match(text):
        return None
    if page.dot_to_dash:
        text = text.replace(".", "-")
    if page.suffix and not text.endswith(page.suffix):
        text = f"{text.rstrip('.')}{page.suffix}"
    return text


def parse_constituents(html: str, page: IndexPage, as_of: Optional[datetime.date] = None) -> List[IndexMember]:
    """Index members from one Wikipedia page; empty when no constituent table is found."""
    table = _constituent_table(html, page)
    if table is None:
        logger.warning(f"No constituent table found for {page.index_symbol} at {page.url}")
        return []
    symbol_column = _first_column(table, SYMBOL_COLUMNS)
    if symbol_column is None:
        logger.warning(f"No ticker column in the constituent table of {page.index_symbol}")
        return []
    name_column = _first_column(table, NAME_COLUMNS)
    as_of = as_of or datetime.date.today()
    members: Dict[str, IndexMember] = {}
    for _, row in table.iterrows():
        symbol = normalise_symbol(row[symbol_column], page)
        if symbol is None or symbol in members:
            continue
        name = str(row[name_column]).strip() if name_column and not pd.isna(row[name_column]) else None
        members[symbol] = IndexMember(index_symbol=page.index_symbol, symbol=symbol, as_of=as_of, name=name)
    return list(members.values())


def fetch_index_members(
    pages: Sequence[IndexPage] = INDEX_PAGES, pause: float = DELAY, timeout: int = 30
) -> List[IndexMember]:
    """Fetch every page; a page that fails or parses to nothing is logged and skipped."""
    members: List[IndexMember] = []
    for page in pages:
        try:
            response = requests.get(page.url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            parsed = parse_constituents(response.text, page)
        except Exception as e:
            logger.error(f"Error fetching constituents of {page.index_symbol}: {e}")
            continue
        logger.info(f"{page.index_symbol}: {len(parsed)} constituents")
        members.extend(parsed)
        time.sleep(pause)
    return members


def pages_for(indices: Optional[Sequence[str]] = None) -> List[IndexPage]:
    """The configured pages, restricted to ``indices`` when given (unknown symbols raise)."""
    if not indices:
        return list(INDEX_PAGES)
    by_symbol = {page.index_symbol: page for page in INDEX_PAGES}
    unknown = [symbol for symbol in indices if symbol not in by_symbol]
    if unknown:
        raise ValueError(f"No constituent page configured for {unknown}. Known: {sorted(by_symbol)}")
    return [by_symbol[symbol] for symbol in indices]
