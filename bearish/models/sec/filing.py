import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Filing(BaseModel):
    """Raw metadata of one SEC filing (10-K, 10-Q or 8-K) from the EDGAR
    submissions API. Joining onto statements is downstream work; bearish
    only stores the raw rows and copies the 10-K / 10-Q filed_date onto
    statements whose (symbol, period_end) matches exactly."""

    symbol: str
    cik: str
    form_type: str = Field(description="SEC form type, e.g. 10-K, 10-Q or 8-K")
    period_end: datetime.date = Field(
        description="Period of report (10-K / 10-Q) or event date (8-K; filing date when EDGAR gives none)"
    )
    filed_date: datetime.date = Field(description="Date the filing was submitted")
    accession_number: str = Field(description="Unique EDGAR accession number")
    items: Optional[str] = Field(
        default=None,
        description="Comma-separated 8-K item codes as EDGAR lists them, e.g. '2.02,9.01'; None for other forms",
    )

    def item_codes(self) -> list[str]:
        """8-K item codes as a list (``['2.02', '9.01']``)."""
        return [code.strip() for code in (self.items or "").split(",") if code.strip()]
