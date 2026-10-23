"""Institutional ownership models: Form 13F holdings and Schedule 13D/13G.

Raw, point-in-time records. Form 13F positions are quarter-end snapshots
published up to 45 days later; the per-security summary derives quarter-on-
quarter flows (holders entering, leaving, net share change). Schedule 13D/13G
rows record beneficial owners crossing 5 % of a class, with the event and
filing dates, as reported in EDGAR's structured XML (filings since
December 2024).
"""

import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PutCall = Literal["", "PUT", "CALL"]


class Holding13F(BaseModel):
    """One manager's position in one security at one quarter end (Form 13F-HR)."""

    model_config = ConfigDict(extra="forbid")

    accession_number: str
    manager_cik: str
    manager_name: str
    period: datetime.date = Field(description="Quarter end the report describes")
    filed_date: datetime.date
    cusip: str
    figi: Optional[str] = None
    symbol: Optional[str] = Field(default=None, description="Resolved from CUSIP/ISIN/FIGI in the equity table")
    issuer_name: str
    title_of_class: Optional[str] = None
    shares: float
    value: float = Field(description="Market value in USD (pre-2023 reports rescaled from thousands)")
    put_call: PutCall = ""
    is_amendment: bool = False
    source: str = "SEC"


class Holding13FSummary(BaseModel):
    """Aggregate of all 13F filers for one security at one quarter end, with flows vs the prior quarter."""

    model_config = ConfigDict(extra="forbid")

    cusip: str
    period: datetime.date
    symbol: Optional[str] = None
    issuer_name: str
    holders: int = Field(description="Managers reporting a long position")
    total_shares: float
    total_value: float
    prev_holders: Optional[int] = None
    new_holders: Optional[int] = Field(default=None, description="Managers with a position now but not last quarter")
    closed_holders: Optional[int] = Field(default=None, description="Managers with a position last quarter but not now")
    shares_change: Optional[float] = None
    value_change: Optional[float] = None
    latest_filed_date: datetime.date = Field(description="Last filing date among the reports aggregated")
    source: str = "SEC"


class Ownership13DG(BaseModel):
    """One reporting person on a Schedule 13D/13G (or amendment)."""

    model_config = ConfigDict(extra="forbid")

    accession_number: str
    symbol: str
    issuer_cik: str
    issuer_name: Optional[str] = None
    issuer_cusip: Optional[str] = None
    form_type: str = Field(description="SCHEDULE 13D, SCHEDULE 13D/A, SCHEDULE 13G, SCHEDULE 13G/A")
    filed_date: datetime.date
    event_date: Optional[datetime.date] = Field(default=None, description="Date of the event requiring the filing")
    reporting_person: str
    person_type: Optional[str] = Field(default=None, description="SEC code: IA, IC, BK, HC, IN, ...")
    percent_of_class: Optional[float] = None
    shares_owned: Optional[float] = None
    sole_voting: Optional[float] = None
    shared_voting: Optional[float] = None
    sole_dispositive: Optional[float] = None
    shared_dispositive: Optional[float] = None
    rule: Optional[str] = Field(default=None, description="Rule 13d-1(b)/(c)/(d) for 13G filers")
    is_amendment: bool = False
    source: str = "SEC"
