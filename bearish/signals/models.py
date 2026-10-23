import datetime
import math
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

EventType = Literal[
    "election",
    "fomc",
    "conflict",
    "sanctions",
    "policy",
    "market",
    "other",
]

PredictionPlatform = Literal["Polymarket", "Kalshi"]


class MarketEvent(BaseModel):
    """A dated event that market reactions can be measured around."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(description="Stable id, e.g. US_MIDTERM_2022, FOMC_2026-09-17, CONFLICT_RUS_UKR_2022")
    event_type: EventType
    name: str
    date: datetime.date = Field(description="Day the event happened (election day, decision day, onset)")
    end_date: Optional[datetime.date] = None
    country: Optional[str] = Field(default=None, description="ISO-3 of the main country, if any")
    tags: str = Field(default="", description="Comma-separated labels used to group events, e.g. midterm,divided")
    outcome: Optional[str] = Field(default=None, description="Short machine-readable outcome, e.g. R_HOUSE,D_SENATE")
    description: Optional[str] = None
    source: str
    as_of: datetime.date = Field(description="When this record was written; outcomes can be revised")

    def tag_set(self) -> set[str]:
        return {tag.strip() for tag in self.tags.split(",") if tag.strip()}


class EventReturn(BaseModel):
    """Measured return of one asset over one window around one event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    asset: str = Field(description="Symbol or factor id the return is measured on, e.g. ^GSPC, XLK, FF_MKT.USA")
    window: str = Field(description="Window label, e.g. -60d..0d, 0d..+250d")
    start_date: datetime.date
    end_date: datetime.date
    ret: float = Field(description="Simple return over the window, in percent")
    benchmark: Optional[str] = None
    benchmark_ret: Optional[float] = None
    excess_ret: Optional[float] = None
    as_of: datetime.date


class TickerSignal(BaseModel):
    """One point-in-time value of a per-ticker signal.

    ``signal`` names the measure, optionally with a qualifier after a colon:
    ``THEME_MENTIONS:ai_accelerator``, ``SHORT_INTEREST``, ``SHORT_VOLUME_RATIO``,
    ``FED_AWARDS_USD``, ``LOBBYING_USD``, ``CAPEX_USD``. Revisions are stored as a
    new row with a later ``as_of``.
    """

    model_config = ConfigDict(extra="forbid")

    symbol: str
    signal: str
    date: datetime.date
    value: float
    as_of: datetime.date
    source: str

    @field_validator("value")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("TickerSignal value must be finite")
        return value

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()


class CongressTrade(BaseModel):
    """One transaction from a congressional Periodic Transaction Report (STOCK Act)."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(description="Filing document id from the House Clerk or Senate eFD")
    line_no: int
    chamber: Literal["House", "Senate"]
    member: str
    state_district: Optional[str] = None
    party: Optional[str] = None
    owner: Optional[str] = Field(default=None, description="SP spouse, JT joint, DC dependent child, self")
    symbol: Optional[str] = None
    asset_description: str
    transaction_type: str = Field(description="P purchase, S sale, S (partial), E exchange")
    transaction_date: Optional[datetime.date] = None
    notification_date: Optional[datetime.date] = None
    filed_date: datetime.date
    amount_min: Optional[float] = Field(default=None, description="Lower bound of the reported amount range, USD")
    amount_max: Optional[float] = None
    source: str


class PredictionQuote(BaseModel):
    """A snapshot of one prediction-market outcome's implied probability."""

    model_config = ConfigDict(extra="forbid")

    platform: PredictionPlatform
    market_id: str
    outcome: str
    as_of: datetime.date
    question: str
    category: Optional[str] = Field(default=None, description="election, geopolitics, economy, ...")
    probability: float = Field(ge=0.0, le=1.0)
    volume_usd: Optional[float] = None
    end_date: Optional[datetime.date] = None
    url: Optional[str] = None
    tags: str = Field(default="", description="Comma-separated labels, e.g. midterm,house or conflict,ISR,IRN")
