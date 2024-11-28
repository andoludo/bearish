import datetime
from datetime import date
from typing import Dict, Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
    field_validator,
)


class BaseAssets(BaseModel):
    equities: Any
    cryptos: Any
    etfs: Any
    currencies: Any


class SourceBase(BaseModel):
    __source__: str
    __alias__: ClassVar[Dict[str, str]] = {}
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class DataSourceBase(SourceBase):

    date: datetime.date
    created_at: datetime.date
    symbol: str
    source: str

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
