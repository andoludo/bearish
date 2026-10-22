"""Country reference data shared by macro sources and the linking layer.

One row per country with the codes each provider expects, plus the name
spellings seen in asset tables (``equity.country``) so they can be mapped to
ISO-3.
"""

from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


class Country(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    iso3: str
    iso2: str
    name: str
    aliases: Tuple[str, ...] = Field(default=(), description="Other spellings seen in source data")
    eurostat_code: Optional[str] = Field(default=None, description="Eurostat geo code when it differs from ISO-2")
    euro_area: bool = False
    eu: bool = False
    oecd: bool = False
    region: str = Field(description="Coarse region used for roll-ups")
    priority: bool = Field(default=False, description="Fetched by default by ``bearish macro``")


# Priority = G7 + China + India + every country already supported by the
# equities pipeline (bearish.exchanges.exchanges.Countries).
COUNTRIES: Tuple[Country, ...] = (
    Country(
        iso3="USA",
        iso2="US",
        name="United States",
        aliases=("US", "USA", "United States of America"),
        oecd=True,
        region="North America",
        priority=True,
    ),
    Country(iso3="CAN", iso2="CA", name="Canada", oecd=True, region="North America", priority=True),
    Country(iso3="MEX", iso2="MX", name="Mexico", oecd=True, region="Latin America", priority=True),
    Country(iso3="BRA", iso2="BR", name="Brazil", aliases=("Brasil",), region="Latin America", priority=True),
    Country(iso3="ARG", iso2="AR", name="Argentina", region="Latin America", priority=True),
    Country(
        iso3="GBR",
        iso2="GB",
        name="United Kingdom",
        aliases=("UK", "Great Britain", "Britain"),
        eurostat_code="UK",
        oecd=True,
        region="Europe",
        priority=True,
    ),
    Country(iso3="DEU", iso2="DE", name="Germany", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="FRA", iso2="FR", name="France", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="ITA", iso2="IT", name="Italy", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="ESP", iso2="ES", name="Spain", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(
        iso3="NLD",
        iso2="NL",
        name="Netherlands",
        aliases=("The Netherlands", "Holland"),
        euro_area=True,
        eu=True,
        oecd=True,
        region="Europe",
        priority=True,
    ),
    Country(iso3="BEL", iso2="BE", name="Belgium", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="AUT", iso2="AT", name="Austria", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="PRT", iso2="PT", name="Portugal", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="FIN", iso2="FI", name="Finland", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="IRL", iso2="IE", name="Ireland", euro_area=True, eu=True, oecd=True, region="Europe"),
    Country(
        iso3="GRC", iso2="GR", name="Greece", eurostat_code="EL", euro_area=True, eu=True, oecd=True, region="Europe"
    ),
    Country(iso3="SWE", iso2="SE", name="Sweden", eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="DNK", iso2="DK", name="Denmark", eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="NOR", iso2="NO", name="Norway", oecd=True, region="Europe", priority=True),
    Country(iso3="CHE", iso2="CH", name="Switzerland", oecd=True, region="Europe", priority=True),
    Country(iso3="POL", iso2="PL", name="Poland", eu=True, oecd=True, region="Europe"),
    Country(iso3="RUS", iso2="RU", name="Russia", aliases=("Russian Federation",), region="Europe", priority=True),
    Country(iso3="TUR", iso2="TR", name="Turkey", aliases=("Türkiye", "Turkiye"), oecd=True, region="Middle East"),
    Country(iso3="ZAF", iso2="ZA", name="South Africa", region="Africa", priority=True),
    Country(iso3="SAU", iso2="SA", name="Saudi Arabia", region="Middle East"),
    Country(iso3="JPN", iso2="JP", name="Japan", oecd=True, region="Asia Pacific", priority=True),
    Country(
        iso3="CHN",
        iso2="CN",
        name="China",
        aliases=("People's Republic of China", "China (mainland)"),
        region="Asia Pacific",
        priority=True,
    ),
    Country(
        iso3="HKG",
        iso2="HK",
        name="Hong Kong",
        aliases=("Hong Kong SAR", "Hong Kong SAR, China"),
        region="Asia Pacific",
        priority=True,
    ),
    Country(
        iso3="TWN",
        iso2="TW",
        name="Taiwan",
        aliases=("Taiwan, China", "Chinese Taipei"),
        region="Asia Pacific",
        priority=True,
    ),
    Country(
        iso3="KOR",
        iso2="KR",
        name="South Korea",
        aliases=("Korea", "Korea, Republic of", "Republic of Korea", "Korea, Rep."),
        oecd=True,
        region="Asia Pacific",
        priority=True,
    ),
    Country(iso3="IND", iso2="IN", name="India", region="Asia Pacific", priority=True),
    Country(iso3="IDN", iso2="ID", name="Indonesia", region="Asia Pacific"),
    Country(iso3="SGP", iso2="SG", name="Singapore", region="Asia Pacific", priority=True),
    Country(iso3="AUS", iso2="AU", name="Australia", oecd=True, region="Asia Pacific", priority=True),
    Country(iso3="NZL", iso2="NZ", name="New Zealand", oecd=True, region="Asia Pacific", priority=True),
)

# Aggregates that providers publish as if they were countries.
REGIONS: Dict[str, str] = {
    "WLD": "World",
    "EA20": "Euro area",
    "EU27": "European Union",
    "OECD": "OECD total",
    "G7": "G7",
    "G20": "G20",
    # Fama-French regional portfolios
    "DM": "Developed markets",
    "EM": "Emerging markets",
    "EUR": "Europe",
    "APXJ": "Asia Pacific ex Japan",
    "NAM": "North America",
}


@lru_cache(maxsize=1)
def _name_index() -> Dict[str, Country]:
    index: Dict[str, Country] = {}
    for country in COUNTRIES:
        for key in (country.iso3, country.iso2, country.name, *country.aliases):
            index[key.casefold()] = country
    return index


def country_from(value: Optional[str]) -> Optional[Country]:
    """Resolve an ISO-2/ISO-3 code or a name spelling to a Country (None if unknown)."""
    if not value:
        return None
    return _name_index().get(value.strip().casefold())


def iso3_from(value: Optional[str]) -> Optional[str]:
    country = country_from(value)
    return country.iso3 if country else None


def priority_countries() -> List[Country]:
    return [country for country in COUNTRIES if country.priority]


def countries_by_iso3(iso3_codes: Optional[List[str]] = None) -> List[Country]:
    if not iso3_codes:
        return priority_countries()
    wanted = {code.upper() for code in iso3_codes}
    return [country for country in COUNTRIES if country.iso3 in wanted]
