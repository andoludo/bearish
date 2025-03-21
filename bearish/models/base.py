import abc
import datetime
from datetime import date
from typing import Dict, Any, ClassVar, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
    field_validator,
)

from bearish.types import Sources


class BaseAssets(BaseModel):
    equities: Any
    cryptos: Any
    etfs: Any
    currencies: Any


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


class TrackerQuery(BaseModel):
    financials: bool = False
    price: bool = False
    price_date: Optional[datetime.date] = None


class Tracker(TrackerQuery):
    source: str
    symbol: str


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
        if not cls.__source__:
            raise ValueError("No source specified for financial metrics")
        default_keys = {field: field for field in cls.model_fields}
        default_keys.pop("date", None)
        alias = cls.__alias__.copy()
        alias = {**alias, **default_keys}

        created_at = date.today()
        return (
            {"date": metrics.get("date", created_at)}
            | {
                alias.get(key, key): value
                for key, value in metrics.items()
                if key in alias
            }
            | {
                "created_at": created_at,
                "source": cls.__source__,
            }
        )
