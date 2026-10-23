import datetime
import math
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MacroSources = Literal[
    "FRED",
    "OECD",
    "IMF",
    "WorldBank",
    "BIS",
    "ECB",
    "Eurostat",
    "USTreasury",
    "EPU",
    "GPR",
    "AtlantaFed",
    "DBnomics",
    "WorldBankPinkSheet",
    "CFTC",
    "USDA",
    "EIA",
    "Comtrade",
    "KenFrench",
    "Yfinance",
]

Category = Literal[
    "growth",
    "inflation",
    "labour",
    "rates",
    "credit",
    "fiscal",
    "external",
    "sentiment",
    "positioning",
    "supply_demand",
    "prices",
    "factor",
]

EntityType = Literal["country", "region", "commodity", "sector", "global", "chokepoint", "country_pair"]

Frequency = Literal["D", "W", "M", "Q", "A"]

# Transformations applied at ingest so that stored values share a meaning
# across providers (e.g. an index level from one and a y/y rate from another
# both end up as ``*_YOY`` percentages).
Transform = Literal["none", "yoy", "diff", "pct_change"]

# Periods are stored on their *start* date (FRED convention): the month
# 2026-09 is 2026-09-01, the quarter 2026-Q3 is 2026-07-01, the year 2026 is
# 2026-01-01. Daily series keep their own date.
PERIODS_PER_YEAR = {"D": 252, "W": 52, "M": 12, "Q": 4, "A": 1}


def series_id_for(concept: str, entity: str) -> str:
    return f"{concept}.{entity}"


class MacroSeries(BaseModel):
    """Catalog entry: what a series means and where it comes from."""

    model_config = ConfigDict(extra="forbid")

    series_id: str = Field(default="", description="``<concept>.<entity>``; derived when omitted")
    concept: str = Field(description="Normalised meaning, e.g. CPI_YOY")
    entity: str = Field(description="ISO-3 country, region or commodity code")
    entity_type: EntityType
    category: Category
    source: MacroSources
    source_code: str = Field(description="Provider-native identifier (FRED id, SDMX key, ...)")
    frequency: Frequency
    unit: str
    transform: Transform = "none"
    seasonal_adj: bool = False
    is_proxy: bool = Field(
        default=False,
        description="True when the series stands in for a concept it does not measure directly",
    )
    description: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _derive_series_id(cls, values: dict) -> dict:  # type: ignore[type-arg]
        if isinstance(values, dict) and not values.get("series_id"):
            concept = str(values["concept"]).strip().upper()
            entity = str(values["entity"]).strip().upper()
            values = {**values, "series_id": series_id_for(concept, entity)}
        return values

    @field_validator("concept", "entity")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    def __hash__(self) -> int:
        return hash(self.series_id)


class Observation(BaseModel):
    """One point-in-time value of a series.

    ``as_of`` is the date on which this value was known to the provider; a
    revised value for the same ``date`` is stored as a new row with a later
    ``as_of`` rather than overwriting the old one.
    """

    model_config = ConfigDict(extra="forbid")

    series_id: str
    date: datetime.date
    value: float
    as_of: datetime.date

    @field_validator("value")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Observation value must be finite")
        return value

    @field_validator("date", "as_of", mode="before")
    @classmethod
    def _to_date(cls, value: object) -> object:
        if isinstance(value, datetime.datetime):
            return value.date()
        return value


class MacroTracker(BaseModel):
    """Bookkeeping for incremental updates: last stored date per series."""

    series_id: str
    source: MacroSources
    last_date: datetime.date
    last_as_of: datetime.date


class MacroQuery(BaseModel):
    """Selection criteria for reading series and observations."""

    series_ids: List[str] = Field(default_factory=list)
    concepts: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    categories: List[Category] = Field(default_factory=list)
    sources: List[MacroSources] = Field(default_factory=list)
    start: Optional[datetime.date] = None
    end: Optional[datetime.date] = None
    as_of: Optional[datetime.date] = Field(
        default=None,
        description="Return the vintage known on this date; None means the latest vintage",
    )

    @field_validator("concepts", "entities", mode="before")
    @classmethod
    def _upper_list(cls, values: List[str]) -> List[str]:
        return [v.strip().upper() for v in values]
