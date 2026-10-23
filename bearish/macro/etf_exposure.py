"""Derive what an ETF is exposed to from the metadata already stored for it.

Three signals, in decreasing reliability:

* ``sector_weightings`` (provider-reported shares) → sector exposure,
* ``category`` / ``category_group`` (Morningstar-style buckets),
* the fund name.

Country/region and commodity exposure from text are heuristics: a name match
gets a full weight split equally across the entities matched of that type.
"""

import re
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from bearish.interface.interface import BearishDbBase
from bearish.macro.commodities import COMMODITIES
from bearish.macro.countries import COUNTRIES, REGIONS
from bearish.macro.links import EtfExposure
from bearish.macro.models import EntityType
from bearish.macro.sectors import sector_from
from bearish.models.assets.etfs import Etf
from bearish.models.query.query import AssetQuery

Method = str

# Words in a category or fund name that identify a sector.
SECTOR_KEYWORDS: Tuple[Tuple[str, str], ...] = (
    ("information technology", "Information Technology"),
    ("technology", "Information Technology"),
    ("semiconductor", "Information Technology"),
    ("software", "Information Technology"),
    ("health care", "Health Care"),
    ("healthcare", "Health Care"),
    ("biotech", "Health Care"),
    ("pharma", "Health Care"),
    ("financial", "Financials"),
    ("bank", "Financials"),
    ("insurance", "Financials"),
    ("real estate", "Real Estate"),
    ("reit", "Real Estate"),
    ("utilities", "Utilities"),
    ("industrial", "Industrials"),
    ("aerospace", "Industrials"),
    ("defense", "Industrials"),
    ("consumer discretionary", "Consumer Discretionary"),
    ("consumer cyclical", "Consumer Discretionary"),
    ("retail", "Consumer Discretionary"),
    ("consumer staples", "Consumer Staples"),
    ("consumer defensive", "Consumer Staples"),
    ("communication", "Communication Services"),
    ("telecom", "Communication Services"),
    ("media", "Communication Services"),
    ("materials", "Materials"),
    ("mining", "Materials"),
    ("miners", "Materials"),
    ("energy", "Energy"),
    ("oil & gas", "Energy"),
    ("oil and gas", "Energy"),
)

# Region phrases checked before country names (so "north america" is not "america" → USA).
REGION_KEYWORDS: Tuple[Tuple[str, str], ...] = (
    ("asia pacific ex japan", "APXJ"),
    ("asia pacific ex-japan", "APXJ"),
    ("asia ex japan", "APXJ"),
    ("asia ex-japan", "APXJ"),
    ("pacific ex japan", "APXJ"),
    ("asia pacific", "APXJ"),
    ("pacific/asia", "APXJ"),
    ("north america", "NAM"),
    ("latin america", "LATAM"),
    ("emerging markets", "EM"),
    ("emerging market", "EM"),
    ("emerging mkts", "EM"),
    ("emerging", "EM"),
    ("frontier", "EM"),
    ("developed markets", "DM"),
    ("developed market", "DM"),
    ("eafe", "DM"),
    ("foreign", "DM"),
    ("international", "DM"),
    ("world ex us", "DM"),
    ("world ex-us", "DM"),
    ("eurozone", "EA20"),
    ("euro area", "EA20"),
    ("euro stoxx", "EA20"),
    ("europe", "EUR"),
    ("european", "EUR"),
    ("global", "WLD"),
    ("world", "WLD"),
    ("all country", "WLD"),
    ("acwi", "WLD"),
)

US_KEYWORDS: Tuple[str, ...] = (
    "s&p 500",
    "s&p500",
    "s&p 400",
    "s&p 600",
    "nasdaq",
    "russell",
    "dow jones",
    "wilshire",
    "u.s.",
    "united states",
    "usa",
    "america",
)

COMMODITY_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("natural gas", ("NATGAS_HH",)),
    ("crude oil", ("BRENT", "WTI")),
    ("brent", ("BRENT",)),
    ("wti", ("WTI",)),
    ("oil", ("BRENT", "WTI")),
    ("gasoline", ("GASOLINE",)),
    ("heating oil", ("HEATING_OIL",)),
    ("coal", ("COAL",)),
    ("gold", ("GOLD",)),
    ("silver", ("SILVER",)),
    ("platinum", ("PLATINUM",)),
    ("palladium", ("PALLADIUM",)),
    ("precious metals", ("GOLD", "SILVER", "PLATINUM", "PALLADIUM")),
    ("copper", ("COPPER",)),
    ("aluminium", ("ALUMINIUM",)),
    ("aluminum", ("ALUMINIUM",)),
    ("nickel", ("NICKEL",)),
    ("zinc", ("ZINC",)),
    ("iron ore", ("IRON_ORE",)),
    ("steel", ("IRON_ORE",)),
    ("industrial metals", ("COPPER", "ALUMINIUM", "NICKEL", "ZINC")),
    ("base metals", ("COPPER", "ALUMINIUM", "NICKEL", "ZINC")),
    ("wheat", ("WHEAT",)),
    ("corn", ("CORN",)),
    ("soybean", ("SOYBEANS",)),
    ("grains", ("WHEAT", "CORN", "SOYBEANS")),
    ("agriculture", ("WHEAT", "CORN", "SOYBEANS", "SUGAR", "COFFEE", "COCOA", "COTTON")),
    ("agricultural", ("WHEAT", "CORN", "SOYBEANS", "SUGAR", "COFFEE", "COCOA", "COTTON")),
    ("sugar", ("SUGAR",)),
    ("coffee", ("COFFEE",)),
    ("cocoa", ("COCOA",)),
    ("cotton", ("COTTON",)),
    ("livestock", ("LIVE_CATTLE", "LEAN_HOGS")),
    ("cattle", ("LIVE_CATTLE",)),
    ("hogs", ("LEAN_HOGS",)),
    ("commodities", ("BRENT", "GOLD", "COPPER", "WHEAT", "CORN", "NATGAS_HH")),
    ("commodity", ("BRENT", "GOLD", "COPPER", "WHEAT", "CORN", "NATGAS_HH")),
)

# Fund names that contain a commodity word without commodity exposure.
_FALSE_COMMODITY_PHRASES = ("goldman", "gold rush", "silver lake", "oilfield services", "oil services")
# Country names that collide with common English words or other names.
_AMBIGUOUS_COUNTRY_NAMES = {"georgia", "jersey", "guernsey", "jordan", "niger", "chad", "turkey"}

_KNOWN_COMMODITIES = {commodity.code for commodity in COMMODITIES}
# Aliases shorter than this (ISO codes) are too ambiguous to match in free text.
_MIN_ALIAS_LENGTH = 4
# Sector weightings summing above this are reported in percent rather than fractions.
_PERCENT_THRESHOLD = 1.5
_VALID_REGIONS = set(REGIONS) | {"LATAM"}


def _text_of(etf: Etf) -> Tuple[str, str]:
    """(name text, category text), lower-cased."""
    name = " ".join(filter(None, [etf.name, etf.long_name, etf.short_name])).lower()
    category = " ".join(filter(None, [etf.category, etf.category_group])).lower()
    return name, category


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def _geo_entities(text: str) -> List[Tuple[EntityType, str]]:
    found: List[Tuple[EntityType, str]] = []
    remaining = text
    for phrase, region in REGION_KEYWORDS:
        if _contains(remaining, phrase):
            if region in _VALID_REGIONS and ("region", region) not in found:
                found.append(("region", region))
            remaining = remaining.replace(phrase, " ")
    for country in COUNTRIES:
        names = [country.name.lower(), *(alias.lower() for alias in country.aliases if len(alias) >= _MIN_ALIAS_LENGTH)]
        if any(name not in _AMBIGUOUS_COUNTRY_NAMES and _contains(remaining, name) for name in names):
            found.append(("country", country.iso3))
    if ("country", "USA") not in found and any(_contains(remaining, keyword) for keyword in US_KEYWORDS):
        found.append(("country", "USA"))
    return found


def _commodity_entities(text: str) -> List[str]:
    if any(phrase in text for phrase in _FALSE_COMMODITY_PHRASES):
        return []
    found: List[str] = []
    remaining = text
    for phrase, codes in COMMODITY_KEYWORDS:
        if _contains(remaining, phrase):
            found.extend(code for code in codes if code not in found and code in _KNOWN_COMMODITIES)
            remaining = remaining.replace(phrase, " ")
    return found


def _sector_entities(text: str) -> List[str]:
    found: List[str] = []
    remaining = text
    for phrase, sector in SECTOR_KEYWORDS:
        if _contains(remaining, phrase):
            if sector not in found:
                found.append(sector)
            remaining = remaining.replace(phrase, " ")
    return found


def _sector_weightings(etf: Etf) -> Dict[str, float]:
    weights: Dict[str, float] = defaultdict(float)
    for key, value in (etf.sector_weightings or {}).items():
        sector = sector_from(key)
        if sector is None or value is None or value <= 0:
            continue
        weights[sector] += float(value)
    total = sum(weights.values())
    if total > _PERCENT_THRESHOLD:
        weights = {sector: value / 100.0 for sector, value in weights.items()}
    return {sector: min(value, 1.0) for sector, value in weights.items()}


def _split(symbol: str, entity_type: EntityType, entities: Iterable[str], method: Method) -> List[EtfExposure]:
    entities = list(dict.fromkeys(entities))
    if not entities:
        return []
    weight = round(1.0 / len(entities), 6)
    return [
        EtfExposure(symbol=symbol, entity_type=entity_type, entity=entity, weight=weight, method=method)
        for entity in entities
    ]


def exposures_for_etf(etf: Etf) -> List[EtfExposure]:
    """Country/region, commodity and sector exposure of one ETF."""
    name, category = _text_of(etf)
    exposures: List[EtfExposure] = []

    geo = _geo_entities(name)
    method: Method = "name"
    if not geo:
        geo, method = _geo_entities(category), "category"
    for entity_type in ("country", "region"):
        exposures.extend(_split(etf.symbol, entity_type, [e for t, e in geo if t == entity_type], method))

    commodities = _commodity_entities(name)
    method = "name"
    if not commodities:
        commodities, method = _commodity_entities(category), "category"
    exposures.extend(_split(etf.symbol, "commodity", commodities, method))

    reported = _sector_weightings(etf)
    if reported:
        exposures.extend(
            EtfExposure(
                symbol=etf.symbol, entity_type="sector", entity=sector, weight=weight, method="sector_weightings"
            )
            for sector, weight in reported.items()
        )
    else:
        sectors = _sector_entities(category)
        method = "category"
        if not sectors:
            sectors, method = _sector_entities(name), "name"
        exposures.extend(_split(etf.symbol, "sector", sectors, method))
    return exposures


def write_etf_exposures(db: BearishDbBase, etfs: Optional[List[Etf]] = None) -> int:
    """Derive and store exposures for every ETF in the database; returns rows written."""
    etfs = etfs if etfs is not None else db.read_assets(AssetQuery.model_validate({})).etfs
    exposures = [exposure for etf in etfs for exposure in exposures_for_etf(etf)]
    db.write_etf_exposures(exposures)
    return len(exposures)
