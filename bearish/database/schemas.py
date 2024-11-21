from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


from bearish.models.base import Equity, Crypto, Currency, Etf, CandleStick

from bearish.models.financials import FinancialMetrics, BalanceSheet, CashFlow


class BaseBearishTable(SQLModel):
    symbol: str = Field(index=True)
    source: str = Field(index=True)

class BaseTable(BaseBearishTable):
    __table_args__ = {"sqlite_autoincrement": True}  # noqa: RUF012
    id: Optional[int] = Field(default=None, primary_key=True)

class BaseFinancials(BaseBearishTable):
    date: datetime = Field(primary_key=True, index=True)

class EquityORM(BaseTable, Equity, table=True):
    __tablename__ = "equity"
    country: str = Field(index=True)

class CryptoORM(BaseTable, Crypto, table=True):
    __tablename__ = "crypto"
    cryptocurrency: str = Field(index=True)

class CurrencyORM(BaseTable,Currency, table=True):
    __tablename__ = "currency"
    base_currency: str = Field(index=True)

class EtfORM(BaseTable,Etf, table=True):
    __tablename__ = "etf"


class CandleStickORM(SQLModel, CandleStick, table=True):
    __tablename__ = "candlestick"
    date: datetime = Field(primary_key=True, index=True)
    symbol: str = Field(primary_key=True, index=True)
    source: str = Field(primary_key=True, index=True)

class FinancialMetricsORM(BaseFinancials, FinancialMetrics, table=True):
    __tablename__ = "financialmetrics"


class BalanceSheetORM(BaseFinancials, BalanceSheet, table=True):
    __tablename__ = "balancesheet"

class CashFlowORM(BaseFinancials, CashFlow, table=True):
    __tablename__ = "cashflow"