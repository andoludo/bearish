import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class InsiderTransaction(BaseModel):
    """One transaction line from an SEC Form 4 (ownership report).

    Raw data only: no aggregation into buy/sell scores happens here.
    """

    model_config = ConfigDict(extra="forbid")

    symbol: str
    cik: str
    accession_number: str
    line_no: int = Field(description="Position of the line within the filing (non-derivative then derivative)")
    filed_date: datetime.date
    transaction_date: datetime.date
    reporting_owner: str
    owner_relationship: str = Field(description="Comma-separated: director, officer, ten_percent_owner, other")
    officer_title: Optional[str] = None
    security_title: str
    transaction_code: str = Field(description="SEC code: P purchase, S sale, A grant, M option exercise, ...")
    acquired_disposed: Literal["A", "D"]
    shares: float
    price: Optional[float] = None
    value: Optional[float] = Field(default=None, description="shares * price when a price is reported")
    shares_owned_after: Optional[float] = None
    is_derivative: bool = False
    source: str = "SEC"
