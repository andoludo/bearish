from datetime import datetime
from typing import Optional, Dict

from sqlalchemy import JSON, Column
from sqlmodel import SQLModel, Field


from bearish.models.assets.equity import Equity
from bearish.models.assets.crypto import Crypto
from bearish.models.assets.currency import Currency
from bearish.models.assets.etfs import Etf
from bearish.models.assets.index import Index
from bearish.models.base import PriceTracker, FinancialsTracker
from bearish.models.financials.balance_sheet import BalanceSheet, QuarterlyBalanceSheet
from bearish.models.financials.cash_flow import CashFlow, QuarterlyCashFlow
from bearish.models.financials.earnings_date import EarningsDate
from bearish.models.financials.metrics import (
    FinancialMetrics,
    QuarterlyFinancialMetrics,
)
from bearish.models.price.price import Price
from bearish.models.sec.sec import Sec, SecShareIncrease


class BaseBearishTable(SQLModel):
    symbol: str = Field(index=True)
    source: str = Field(index=True)


class BaseTable(BaseBearishTable):
    __table_args__ = {"sqlite_autoincrement": True}
    id: Optional[int] = Field(default=None, primary_key=True)


class BaseFinancials(SQLModel):
    date: datetime = Field(primary_key=True, index=True)
    symbol: str = Field(primary_key=True, index=True)
    source: str = Field(primary_key=True, index=True)


class EquityORM(BaseTable, Equity, table=True):  # type: ignore
    __tablename__ = "equity"
    country: Optional[str] = Field(default=None, index=True)


class IndexORM(BaseTable, Index, table=True):  # type: ignore
    __tablename__ = "index"
    country: Optional[str] = Field(default=None, index=True)


class CryptoORM(BaseTable, Crypto, table=True):  # type: ignore
    __tablename__ = "crypto"
    cryptocurrency: Optional[str] = Field(default=None, index=True)


class CurrencyORM(BaseTable, Currency, table=True):  # type: ignore
    __tablename__ = "currency"
    base_currency: str = Field(index=True)


class EtfORM(BaseTable, Etf, table=True):  # type: ignore
    __tablename__ = "etf"

    holding_percent: Optional[Dict[str, float]] = Field(None, sa_column=Column(JSON))
    sector_weightings: Optional[Dict[str, float]] = Field(None, sa_column=Column(JSON))


class PriceORM(SQLModel, Price, table=True):  # type: ignore
    __tablename__ = "price"
    date: datetime = Field(primary_key=True, index=True)
    symbol: str = Field(primary_key=True, index=True)
    source: str = Field(primary_key=True, index=True)  # type: ignore


class PriceIndexORM(SQLModel, Price, table=True):  # type: ignore
    __tablename__ = "priceindex"
    date: datetime = Field(primary_key=True, index=True)
    symbol: str = Field(primary_key=True, index=True)
    source: str = Field(primary_key=True, index=True)  # type: ignore


class PriceEtfORM(SQLModel, Price, table=True):  # type: ignore
    __tablename__ = "priceetf"
    date: datetime = Field(primary_key=True, index=True)
    symbol: str = Field(primary_key=True, index=True)
    source: str = Field(primary_key=True, index=True)  # type: ignore


class FinancialMetricsORM(BaseFinancials, FinancialMetrics, table=True):  # type: ignore
    __tablename__ = "financialmetrics"


class BalanceSheetORM(BaseFinancials, BalanceSheet, table=True):  # type: ignore
    __tablename__ = "balancesheet"


class CashFlowORM(BaseFinancials, CashFlow, table=True):  # type: ignore
    __tablename__ = "cashflow"


class QuarterlyFinancialMetricsORM(BaseFinancials, QuarterlyFinancialMetrics, table=True):  # type: ignore
    __tablename__ = "quarterlyfinancialmetrics"


class QuarterlyBalanceSheetORM(BaseFinancials, QuarterlyBalanceSheet, table=True):  # type: ignore
    __tablename__ = "quarterlybalancesheet"


class QuarterlyCashFlowORM(BaseFinancials, QuarterlyCashFlow, table=True):  # type: ignore
    __tablename__ = "quarterlycashflow"


class EarningsDateORM(BaseFinancials, EarningsDate, table=True):  # type: ignore
    __tablename__ = "earningsdate"


class SourcesORM(SQLModel, table=True):
    __tablename__ = "sources"
    source: str = Field(primary_key=True, index=True)


class PriceTrackerORM(SQLModel, PriceTracker, table=True):
    __tablename__ = "pricetracker"
    __table_args__ = {"sqlite_autoincrement": True}
    source: str = Field(index=True, primary_key=True)
    symbol: str = Field(index=True, primary_key=True)


class FinancialsTrackerORM(SQLModel, FinancialsTracker, table=True):
    __tablename__ = "financialstracker"
    __table_args__ = {"sqlite_autoincrement": True}
    source: str = Field(index=True, primary_key=True)
    symbol: str = Field(index=True, primary_key=True)


class SecORM(SQLModel, Sec, table=True):
    __tablename__ = "sec"
    __table_args__ = {"sqlite_autoincrement": True}
    name: str = Field(index=True, primary_key=True)
    source: str = Field(index=True, primary_key=True)
    period: str = Field(index=True, primary_key=True)
    filed_date: str = Field(index=True, primary_key=True)


class SecShareIncreaseORM(SQLModel, SecShareIncrease, table=True):
    __tablename__ = "secshareincrease"
    __table_args__ = {"sqlite_autoincrement": True}
    ticker: str = Field(index=True, primary_key=True)
