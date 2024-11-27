from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field

from bearish.models.assets.equity import Equity
from bearish.models.assets.crypto import Crypto
from bearish.models.assets.currency import Currency
from bearish.models.assets.etfs import Etf
from bearish.models.financials.balance_sheet import BalanceSheet
from bearish.models.financials.cash_flow import CashFlow
from bearish.models.financials.metrics import FinancialMetrics
from bearish.models.price.price import Price


class BaseBearishTable(SQLModel):
    symbol: str = Field(index=True)
    source: str = Field(index=True)


class BaseTable(BaseBearishTable):
    __table_args__ = {"sqlite_autoincrement": True}  # noqa: RUF012
    id: Optional[int] = Field(default=None, primary_key=True)


class BaseBearishTableTest(BaseTable, table=True):
    ...


class BaseFinancials(SQLModel):
    date: datetime = Field(primary_key=True, index=True)
    symbol: str = Field(primary_key=True, index=True)
    source: str = Field(primary_key=True, index=True)


class EquityORM(BaseTable, Equity, table=True):  # type: ignore
    __tablename__ = "equity"
    country: Optional[str] = Field(default=None, index=True)


class CryptoORM(BaseTable, Crypto, table=True):  # type: ignore
    __tablename__ = "crypto"
    cryptocurrency: Optional[str] = Field(default=None,index=True)


class CurrencyORM(BaseTable, Currency, table=True):  # type: ignore
    __tablename__ = "currency"
    base_currency: str = Field(index=True)


class EtfORM(BaseTable, Etf, table=True):  # type: ignore
    __tablename__ = "etf"


class PriceORM(SQLModel, Price, table=True):  # type: ignore
    __tablename__ = "price"
    date: datetime = Field(primary_key=True, index=True)
    symbol: str = Field(primary_key=True, index=True)
    source: str = Field(primary_key=True, index=True)


class FinancialMetricsORM(BaseFinancials, FinancialMetrics, table=True):  # type: ignore
    __tablename__ = "financialmetrics"


class BalanceSheetORM(BaseFinancials, BalanceSheet, table=True):  # type: ignore
    __tablename__ = "balancesheet"


class CashFlowORM(BaseFinancials, CashFlow, table=True):  # type: ignore
    __tablename__ = "cashflow"
