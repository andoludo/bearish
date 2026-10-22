"""Linking layer: tables that connect macro and commodity entities to the
equities, sectors and ETFs already in the database."""

from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from bearish.macro.countries import COUNTRIES, Country
from bearish.macro.models import EntityType


class CountryRef(BaseModel):
    """Database mirror of ``bearish.macro.countries.Country`` for SQL joins."""

    model_config = ConfigDict(extra="forbid")

    iso3: str
    iso2: str
    name: str
    region: str
    eu: bool = False
    euro_area: bool = False
    oecd: bool = False
    priority: bool = False

    @classmethod
    def from_country(cls, country: Country) -> "CountryRef":
        return cls(
            iso3=country.iso3,
            iso2=country.iso2,
            name=country.name,
            region=country.region,
            eu=country.eu,
            euro_area=country.euro_area,
            oecd=country.oecd,
            priority=country.priority,
        )


class CountryAlias(BaseModel):
    """A spelling of a country as it appears in asset tables, mapped to ISO-3."""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(description="Case-folded spelling")
    iso3: str


def country_references(countries: Tuple[Country, ...] = COUNTRIES) -> Tuple[List[CountryRef], List[CountryAlias]]:
    refs = [CountryRef.from_country(country) for country in countries]
    aliases = [
        CountryAlias(alias=spelling.casefold(), iso3=country.iso3)
        for country in countries
        for spelling in (country.iso3, country.iso2, country.name, *country.aliases)
    ]
    return refs, aliases


class SectorCommoditySensitivity(BaseModel):
    """Curated sign of a sector's sensitivity to a commodity price."""

    model_config = ConfigDict(extra="forbid")

    sector: str
    commodity: str
    direction: Literal[-1, 1] = Field(description="+1 benefits from a higher price, -1 is hurt by it")
    strength: Literal["high", "medium", "low"] = "medium"
    rationale: Optional[str] = None


class EtfExposure(BaseModel):
    """What an ETF is exposed to, derived from its metadata."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    entity_type: EntityType
    entity: str
    weight: float = Field(ge=0.0, le=1.0, description="Share of the fund attributed to the entity")
    method: Literal["category", "name", "sector_weightings", "holdings"]
