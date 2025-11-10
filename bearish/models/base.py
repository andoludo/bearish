import abc
import datetime
from datetime import date
from typing import Dict, Any, ClassVar, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
    field_validator,
    Field,
)

from bearish.types import Sources


class BaseAssets(BaseModel):
    equities: Any
    cryptos: Any
    etfs: Any
    currencies: Any
    index: Any


class Ticker(BaseModel):
    symbol: str
    exchange: Optional[str] = None
    source: Optional[Sources] = None

    def __hash__(self) -> int:
        return hash(self.symbol)


class SourceBase(BaseModel, abc.ABC):
    __source__: Sources
    __alias__: ClassVar[Dict[str, str]] = {}
    __api_key__: ClassVar[str]
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class BaseTrackerQuery(BaseModel):
    exchange: Optional[str] = None


class TrackerQuery(BaseTrackerQuery):
    reference_date: Optional[datetime.date] = None
    delay: int = 5


class BaseTracker(BaseTrackerQuery):
    source: str
    symbol: str
    date: datetime.date = Field(default_factory=lambda: date(1970, 1, 1))


class PriceTracker(BaseTracker): ...


class FinancialsTracker(BaseTracker): ...


class DataSourceBase(SourceBase, Ticker):
    source: Sources
    date: datetime.date
    created_at: datetime.date

    @field_validator("date", mode="before")
    def _date_validator(cls, value: str | datetime.date) -> datetime.date:  # noqa: N805
        if isinstance(value, str):
            return datetime.datetime.strptime(value, "%Y-%m-%d").date()
        return value

    @model_validator(mode="before")
    def _validate(cls, metrics: Dict[str, Any]) -> Dict[str, Any]:  # noqa: N805
        if not hasattr(cls, "__source__") and "source" not in metrics:
            raise ValueError("No source specified for financial metrics")
        source = cls.__source__ if hasattr(cls, "__source__") else metrics["source"]
        default_keys = {field: field for field in cls.model_fields}
        default_keys.pop("date", None)
        alias = cls.__alias__.copy()
        alias = {**alias, **default_keys}

        created_at = date.today()
        current_date = metrics.get("date", created_at)
        if isinstance(current_date, datetime.datetime):
            current_date = current_date.date()
        return (
            {"date": current_date}
            | {
                alias.get(key, key): value
                for key, value in metrics.items()
                if key in alias
            }
            | {
                "created_at": created_at,
                "source": source,
            }
        )
