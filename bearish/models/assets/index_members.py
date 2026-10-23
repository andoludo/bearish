import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IndexMember(BaseModel):
    """One constituent of an equity index on a given date.

    Membership is a snapshot: a new ``as_of`` is written on every fetch, so
    additions and deletions can be reconstructed from the history. Weights
    are only stored when the source publishes them (most open sources do not).
    """

    model_config = ConfigDict(extra="forbid")

    index_symbol: str = Field(description="Index symbol as used in the index / priceindex tables, e.g. ^GSPC")
    symbol: str = Field(description="Constituent symbol in Yahoo Finance notation, e.g. BRK-B or ADS.DE")
    as_of: datetime.date
    name: Optional[str] = None
    weight: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Index weight when published")
    source: str = "Wikipedia"
