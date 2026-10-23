"""OFAC Specially Designated Nationals (SDN) list: new designations per country.

The plain ``SDN.XML`` export carries no designation dates, but the enhanced
export (``SDN_ENHANCED.XML``, ~110 MB) gives every listed entity a
``sanctionsList/@datePublished``. Each entity is attributed to the countries
in its addresses and its nationality / citizenship / registration features,
falling back to the country targeted by its sanctions program (e.g.
``RUSSIA-EO14024`` -> RUS) when neither is present.

``SANCTIONS_NEW.<ISO3>`` is the monthly count of designations attributed to a
country; ``SANCTIONS_NEW.WLD`` counts every designation once. Caveat: the list
only holds entities that are *still* designated, so older months undercount
designations that were later lifted. Catalog ``source_code`` is the ISO-3
code (or ``WLD``).
"""

import datetime
import io
import logging
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from typing import Dict, Iterator, List, Optional, Set, Tuple

import pandas as pd

from bearish.macro.countries import iso3_from
from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import observations_from_series

logger = logging.getLogger(__name__)

SDN_ENHANCED_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN_ENHANCED.XML"
WORLD = "WLD"

# OFAC spellings that bearish.macro.countries does not resolve.
OFAC_COUNTRIES: Dict[str, str] = {
    "Iran": "IRN",
    "Syria": "SYR",
    "Belarus": "BLR",
    "Korea, North": "PRK",
    "Yemen": "YEM",
    "Cuba": "CUB",
    "Nicaragua": "NIC",
    "Somalia": "SOM",
    "Kosovo": "XKX",
    "Russia": "RUS",
    "Burma": "MMR",
    "Congo, Democratic Republic of the": "COD",
    "Virgin Islands, British": "VGB",
    "West Bank": "PSE",
    "Gaza": "PSE",
    "Palestinian": "PSE",
}

# Program prefix -> targeted country, used only when an entity has no country of its own.
PROGRAM_COUNTRIES: Tuple[Tuple[str, str], ...] = (
    ("RUSSIA", "RUS"),
    ("UKRAINE-EO1366", "RUS"),
    ("UKRAINE-EO13685", "RUS"),
    ("CAATSA - RUSSIA", "RUS"),
    ("IRAN", "IRN"),
    ("IFSR", "IRN"),
    ("IRGC", "IRN"),
    ("DPRK", "PRK"),
    ("VENEZUELA", "VEN"),
    ("BELARUS", "BLR"),
    ("BURMA", "MMR"),
    ("SYRIA", "SYR"),
    ("CUBA", "CUB"),
    ("IRAQ", "IRQ"),
    ("NICARAGUA", "NIC"),
    ("LEBANON", "LBN"),
    ("YEMEN", "YEM"),
    ("SOMALIA", "SOM"),
)

COUNTRY_FEATURES = ("Nationality", "Citizenship")


def ofac_iso3(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    name = name.strip()
    return OFAC_COUNTRIES.get(name) or iso3_from(name)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, *path: str) -> Iterator[ET.Element]:
    """Descendants following local tag names, ignoring the XML namespace."""
    if not path:
        yield element
        return
    for child in element:
        if _local(child.tag) == path[0]:
            yield from _children(child, *path[1:])


def entity_countries(entity: ET.Element) -> Set[str]:
    countries: Set[str] = set()
    for country in _children(entity, "addresses", "address", "country"):
        if iso3 := ofac_iso3(country.text):
            countries.add(iso3)
    for feature in _children(entity, "features", "feature"):
        kind = next(_children(feature, "type"), None)
        value = next(_children(feature, "value"), None)
        is_country_feature = kind is not None and any(word in (kind.text or "") for word in COUNTRY_FEATURES)
        if is_country_feature and value is not None and (iso3 := ofac_iso3(value.text)):
            countries.add(iso3)
    if countries:
        return countries
    for program in _children(entity, "sanctionsPrograms", "sanctionsProgram"):
        text = (program.text or "").upper()
        for prefix, iso3 in PROGRAM_COUNTRIES:
            if text.startswith(prefix):
                countries.add(iso3)
    return countries


def parse_designations(content: bytes) -> pd.DataFrame:
    """One row per listed entity: ``entity_id``, ``date`` (designation) and ``countries`` (set of ISO-3)."""
    rows = []
    # Treasury-hosted XML; ElementTree does not resolve external entities.
    for _, element in ET.iterparse(io.BytesIO(content), events=("end",)):  # noqa: S314
        if _local(element.tag) != "entity":
            continue
        listing = next(_children(element, "sanctionsLists", "sanctionsList"), None)
        published = listing.get("datePublished") if listing is not None else None
        if published:
            rows.append(
                {
                    "entity_id": element.get("id"),
                    "date": datetime.date.fromisoformat(published[:10]),
                    "countries": entity_countries(element),
                }
            )
        element.clear()
    return pd.DataFrame(rows, columns=["entity_id", "date", "countries"])


def monthly_counts(designations: pd.DataFrame, end: Optional[datetime.date] = None) -> pd.DataFrame:
    """Designations per month (rows, month start) and country (columns, plus WLD); empty months are 0."""
    if designations.empty:
        return pd.DataFrame()
    counts: Dict[str, Counter[pd.Timestamp]] = defaultdict(Counter)
    days: List[datetime.date] = designations["date"].tolist()
    entity_countries_: List[Set[str]] = designations["countries"].tolist()
    for day, countries in zip(days, entity_countries_, strict=True):
        month = pd.Timestamp(day).to_period("M").to_timestamp()
        counts[WORLD][month] += 1
        for iso3 in countries:
            counts[iso3][month] += 1
    first = min(designations["date"])
    last = end or max(designations["date"])
    months = pd.date_range(pd.Timestamp(first).to_period("M").to_timestamp(), pd.Timestamp(last), freq="MS")
    frame = pd.DataFrame({iso3: pd.Series(counter, dtype=float) for iso3, counter in counts.items()})
    return frame.reindex(months).fillna(0.0)


class OfacSource(AbstractMacroSource):
    __source__ = "OFAC"
    timeout: int = 300

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        designations = parse_designations(self._get(SDN_ENHANCED_URL).content)
        as_of = self.today()
        frame = monthly_counts(designations, end=as_of)
        observations: List[Observation] = []
        for macro_series in series:
            column = macro_series.source_code
            values = frame[column] if column in frame.columns else pd.Series(0.0, index=frame.index)
            observations.extend(observations_from_series(macro_series, values, as_of, start))
        return observations
