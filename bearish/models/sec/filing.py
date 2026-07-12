import datetime

from pydantic import BaseModel, Field


class Filing(BaseModel):
    """Raw metadata of one SEC filing (10-K / 10-Q) from the EDGAR
    submissions API. Joining onto statements is downstream work; bearish
    only stores the raw rows and copies filed_date onto statements whose
    (symbol, period_end) matches exactly."""

    symbol: str
    cik: str
    form_type: str = Field(description="SEC form type, e.g. 10-K or 10-Q")
    period_end: datetime.date = Field(description="Period of report")
    filed_date: datetime.date = Field(description="Date the filing was submitted")
    accession_number: str = Field(description="Unique EDGAR accession number")
