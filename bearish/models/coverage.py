import datetime

from pydantic import BaseModel, ConfigDict, Field


class Coverage(BaseModel):
    """Row count and date span of one table for one symbol and source."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    table_name: str
    source: str = Field(default="", description="Provider; empty when the table has no source column")
    first_date: datetime.date
    last_date: datetime.date
    rows: int = Field(ge=1)
    as_of: datetime.date = Field(description="When the census was taken")
