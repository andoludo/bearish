from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field

from bearish.equities import DailyOhlcv
from bearish.models.base import Equity
from bearish.financials import Financials


class BaseTable(SQLModel):
    __table_args__ = {"sqlite_autoincrement": True}  # noqa: RUF012
    id: Optional[int] = Field(default=None, primary_key=True)

class EquityORM(Equity, BaseTable, table=True):
    __tablename__ = "equity"
    symbol: str = Field(index=True)
    country: str = Field(index=True)

class DailyOhlcvORM(SQLModel, DailyOhlcv, table=True):
    __tablename__ = "daily_ohlcv"
    date: datetime = Field(primary_key=True, index=True)
    symbol: str = Field(primary_key=True, index=True)

class FinancialsORM(SQLModel, Financials, table=True):
    __tablename__ = "financials"
    date: datetime = Field(primary_key=True, index=True)
    symbol: str = Field(primary_key=True, index=True)