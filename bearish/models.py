"""Common, source-agnostic data model.

The whole point of bearish is that every data source — yfinance, FMP,
AlphaVantage, a CSV on disk — flows into the same three shapes:

* :class:`Asset`             — what the instrument is
* :class:`Price`             — one OHLCV row
* :class:`FinancialStatement` — a snapshot of fundamentals at a period end
"""
from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Period = Literal["annual", "quarterly"]


class AssetKind(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"
    CRYPTO = "crypto"
    CURRENCY = "currency"


def _normalise_symbol(value: str) -> str:
    cleaned = value.strip().upper()
    if not cleaned:
        raise ValueError("symbol must not be blank")
    return cleaned


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


class Asset(_Base):
    """A tradeable instrument."""

    symbol: str
    name: str | None = None
    exchange: str | None = None
    country: str | None = None
    currency: str | None = None
    kind: AssetKind = AssetKind.EQUITY
    sector: str | None = None
    industry: str | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return _normalise_symbol(v)

    def __hash__(self) -> int:
        return hash(self.symbol)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Asset) and self.symbol == other.symbol


class Price(_Base):
    """One day of OHLCV data for a symbol."""

    symbol: str
    date: dt.date
    open: float = Field(ge=0)
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    close: float = Field(ge=0)
    volume: float = Field(ge=0)
    source: str

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return _normalise_symbol(v)

    @model_validator(mode="after")
    def _check_high_low(self) -> Price:
        if self.high < self.low:
            raise ValueError("high must be >= low")
        return self


class FinancialStatement(_Base):
    """Periodic fundamentals snapshot.

    Only a handful of canonical fields are kept; richer per-source data can
    live next to bearish, but the common model stays small on purpose.
    """

    symbol: str
    period_end: dt.date
    period: Period
    source: str

    revenue: float | None = None
    net_income: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    operating_cash_flow: float | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return _normalise_symbol(v)
