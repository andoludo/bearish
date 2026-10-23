"""SIPRI Military Expenditure Database (annual workbook).

The workbook (``SIPRI-Milex-data-1949-<year>[_vX.Y].xlsx``) has one sheet per
measure with a few note rows, a ``Country`` header row, year columns and
region/sub-region rows interleaved with countries. Used here:

* ``Constant (<base year>) US$`` — US$ m. at constant prices -> ``MILEX_USD``
* ``Share of GDP`` — a fraction, stored as a percentage -> ``MILEX_GDP``
* ``Regional totals`` — the ``World`` row in US$ b. constant -> ``MILEX_USD.WLD``
  (converted to US$ m. so every ``MILEX_USD`` series shares one unit)

``"..."``, ``". ."`` and ``"xxx"`` markers become missing values. Catalog
``source_code`` is ``<measure>|<ISO3>`` with measure ``constant`` or
``share_gdp``. The newest file is discovered from the database page, falling
back to :data:`SIPRI_FALLBACK_URL`.
"""

import datetime
import io
import logging
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

from bearish.macro.countries import iso3_from
from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import observations_from_series

logger = logging.getLogger(__name__)

SIPRI_PAGE_URL = "https://www.sipri.org/databases/milex"
SIPRI_FALLBACK_URL = "https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx"
_WORKBOOK_LINK = re.compile(r'href="([^"]*SIPRI-Milex-data-1949-(\d{4})[^"]*\.xlsx)"')

WORLD = "WLD"
FIRST_YEAR, LAST_YEAR = 1900, 2100  # plausible year-column range in the workbook header
SIPRI_COUNTRIES: Dict[str, str] = {
    "Korea, South": "KOR",
    "Korea, North": "PRK",
    "Iran": "IRN",
    "Syria": "SYR",
    "Belarus": "BLR",
    "Yemen": "YEM",
    "Cuba": "CUB",
    "Congo, DR": "COD",
    "Russia": "RUS",
    "Türkiye": "TUR",
    "Viet Nam": "VNM",
    "Palestine": "PSE",
}


def sipri_iso3(name: object) -> Optional[str]:
    if not isinstance(name, str):
        return None
    name = name.strip()
    return SIPRI_COUNTRIES.get(name) or iso3_from(name)


def newest_workbook_url(page_html: str) -> Optional[str]:
    """Absolute URL of the newest workbook linked from the database page."""
    links: List[Tuple[str, str]] = _WORKBOOK_LINK.findall(page_html)
    if not links:
        return None
    href = max(links, key=lambda link: (link[1], link[0]))[0]
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return f"https:{href}"
    return f"https://www.sipri.org{href}"


def _year_columns(header: pd.Series) -> Dict[int, int]:
    """Column position -> year for header cells that are plain years."""
    years: Dict[int, int] = {}
    for position, value in enumerate(header.tolist()):
        if (
            isinstance(value, (int, float))
            and not pd.isna(value)
            and FIRST_YEAR <= int(value) <= LAST_YEAR
            and value == int(value)
        ):
            years[position] = int(value)
    return years


def _sheet_table(raw: pd.DataFrame, label: str) -> pd.DataFrame:
    """Years (rows, Jan 1) x first-column labels (columns) for one sheet."""
    header_rows = raw.index[raw[0].astype(str).str.strip() == label]
    if header_rows.empty:
        raise ValueError(f"SIPRI sheet has no '{label}' header row")
    header = raw.loc[header_rows[0]]
    years = _year_columns(header)
    body = raw.loc[header_rows[0] + 1 :]
    data: Dict[str, pd.Series] = {}
    for _, row in body.iterrows():
        name = row[0]
        if not isinstance(name, str) or not name.strip():
            continue
        values = pd.to_numeric(pd.Series({year: row[position] for position, year in years.items()}), errors="coerce")
        data.setdefault(name.strip(), values)
    table = pd.DataFrame(data)
    table.index = pd.to_datetime([f"{year}-01-01" for year in table.index])
    return table


def _by_iso3(table: pd.DataFrame) -> pd.DataFrame:
    columns: Dict[str, pd.Series] = {}
    for name in table.columns:
        iso3 = sipri_iso3(name)
        if iso3 is not None and iso3 not in columns:
            columns[iso3] = table[name]
    return pd.DataFrame(columns)


def parse_milex_workbook(content: bytes) -> Dict[str, pd.DataFrame]:
    """``{"constant": ..., "share_gdp": ...}``, each a year x ISO-3 frame in the catalog's units."""
    sheets: Dict[str, pd.DataFrame] = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
    constant_sheet = next(name for name in sheets if str(name).startswith("Constant"))
    constant = _by_iso3(_sheet_table(sheets[constant_sheet], "Country"))
    share = _by_iso3(_sheet_table(sheets["Share of GDP"], "Country")) * 100.0
    regional = _sheet_table(sheets["Regional totals"], "Region")
    if "World" in regional.columns:
        constant[WORLD] = regional["World"] * 1000.0
    return {"constant": constant, "share_gdp": share}


def split_source_code(source_code: str) -> Tuple[str, str]:
    measure, iso3 = source_code.split("|", 1)
    return measure, iso3


class SipriSource(AbstractMacroSource):
    __source__ = "SIPRI"
    timeout: int = 120

    def _workbook_url(self) -> str:
        try:
            return newest_workbook_url(self._get(SIPRI_PAGE_URL).text) or SIPRI_FALLBACK_URL
        except Exception as e:  # the page is only a convenience to find the newest edition
            logger.warning(f"Could not read the SIPRI page ({e}); using {SIPRI_FALLBACK_URL}")
            return SIPRI_FALLBACK_URL

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        tables = parse_milex_workbook(self._get(self._workbook_url()).content)
        as_of = self.today()
        observations: List[Observation] = []
        for macro_series in series:
            measure, iso3 = split_source_code(macro_series.source_code)
            table = tables.get(measure)
            if table is None or iso3 not in table.columns:
                logger.warning(f"SIPRI workbook has no {measure} data for {iso3}")
                continue
            observations.extend(observations_from_series(macro_series, table[iso3], as_of, start))
        return observations
