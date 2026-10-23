import datetime as dt
from datetime import date, datetime
from typing import Optional, Dict

from sqlalchemy import JSON, Column
from sqlmodel import SQLModel, Field


from bearish.models.assets.equity import Equity
from bearish.models.assets.crypto import Crypto
from bearish.models.assets.currency import Currency
from bearish.models.assets.etfs import Etf
from bearish.models.assets.index import Index
from bearish.models.base import PriceTracker, FinancialsTracker
from bearish.models.financials.analyst import AnalystRecommendation, PriceTarget
from bearish.models.financials.balance_sheet import BalanceSheet, QuarterlyBalanceSheet
from bearish.models.financials.cash_flow import CashFlow, QuarterlyCashFlow
from bearish.models.financials.earnings_date import EarningsDate
from bearish.models.financials.metrics import (
    FinancialMetrics,
    QuarterlyFinancialMetrics,
)
from bearish.models.price.price import Price
from bearish.macro.commodities import Commodity, CountryCommodityExposure
from bearish.macro.links import CountryAlias, CountryRef, EtfExposure, SectorCommoditySensitivity
from bearish.macro.models import MacroSeries, MacroTracker, Observation
from bearish.models.sec.holdings import Holding13F, Holding13FSummary, Ownership13DG
from bearish.models.sec.insider import InsiderTransaction
from bearish.signals.models import CongressTrade, EventReturn, MarketEvent, PredictionQuote, TickerSignal
from bearish.models.sec.filing import Filing
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


class PriceCommodityORM(SQLModel, Price, table=True):  # type: ignore
    __tablename__ = "pricecommodity"
    symbol: str = Field(primary_key=True, index=True)
    source: str = Field(primary_key=True, index=True)  # type: ignore[assignment]
    date: datetime = Field(primary_key=True, index=True)


class PriceEtfORM(SQLModel, Price, table=True):  # type: ignore
    __tablename__ = "priceetf"
    date: datetime = Field(primary_key=True, index=True)
    symbol: str = Field(primary_key=True, index=True)
    source: str = Field(primary_key=True, index=True)  # type: ignore


class FinancialMetricsORM(BaseFinancials, FinancialMetrics, table=True):  # type: ignore
    __tablename__ = "financialmetrics"
    filed_date: Optional[date] = Field(default=None, index=True)


class BalanceSheetORM(BaseFinancials, BalanceSheet, table=True):  # type: ignore
    __tablename__ = "balancesheet"
    filed_date: Optional[date] = Field(default=None, index=True)


class CashFlowORM(BaseFinancials, CashFlow, table=True):  # type: ignore
    __tablename__ = "cashflow"
    filed_date: Optional[date] = Field(default=None, index=True)


class QuarterlyFinancialMetricsORM(BaseFinancials, QuarterlyFinancialMetrics, table=True):  # type: ignore
    __tablename__ = "quarterlyfinancialmetrics"
    filed_date: Optional[date] = Field(default=None, index=True)


class QuarterlyBalanceSheetORM(BaseFinancials, QuarterlyBalanceSheet, table=True):  # type: ignore
    __tablename__ = "quarterlybalancesheet"
    filed_date: Optional[date] = Field(default=None, index=True)


class QuarterlyCashFlowORM(BaseFinancials, QuarterlyCashFlow, table=True):  # type: ignore
    __tablename__ = "quarterlycashflow"
    filed_date: Optional[date] = Field(default=None, index=True)


class EarningsDateORM(BaseFinancials, EarningsDate, table=True):  # type: ignore
    __tablename__ = "earningsdate"


class PriceTargetORM(BaseFinancials, PriceTarget, table=True):  # type: ignore
    __tablename__ = "pricetarget"


class AnalystRecommendationORM(BaseFinancials, AnalystRecommendation, table=True):  # type: ignore
    __tablename__ = "analystrecommendation"
    period: str = Field(primary_key=True, index=True)


class FilingORM(SQLModel, Filing, table=True):
    __tablename__ = "filing"
    accession_number: str = Field(primary_key=True)
    symbol: str = Field(index=True)
    period_end: date = Field(index=True)
    filed_date: date = Field(index=True)


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


class MacroSeriesORM(SQLModel, MacroSeries, table=True):  # type: ignore
    __tablename__ = "macroseries"
    series_id: str = Field(primary_key=True)
    concept: str = Field(index=True)
    entity: str = Field(index=True)
    source: str = Field(index=True)  # type: ignore[assignment]
    # Literal-typed on the pydantic model; SQLModel needs plain columns.
    entity_type: str  # type: ignore[assignment]
    category: str = Field(index=True)  # type: ignore[assignment]
    frequency: str  # type: ignore[assignment]
    transform: str  # type: ignore[assignment]


class MacroObservationORM(SQLModel, Observation, table=True):  # type: ignore
    """Point-in-time store: one row per (series, date, vintage)."""

    __tablename__ = "macroobservation"
    series_id: str = Field(primary_key=True, index=True)
    date: dt.date = Field(primary_key=True, index=True)
    as_of: dt.date = Field(primary_key=True)
    created_at: dt.date = Field(default_factory=dt.date.today)


class MacroTrackerORM(SQLModel, MacroTracker, table=True):
    __tablename__ = "macrotracker"
    series_id: str = Field(primary_key=True)
    source: str = Field(index=True)  # type: ignore[assignment]


class CommodityORM(SQLModel, Commodity, table=True):  # type: ignore
    __tablename__ = "commodity"
    code: str = Field(primary_key=True)
    group: str = Field(index=True)  # type: ignore[assignment]
    hs_codes: str = Field(default="", description="Comma-separated HS codes")  # type: ignore[assignment]
    sectors: str = Field(default="", description="Comma-separated sector names")  # type: ignore[assignment]


class CountryCommodityExposureORM(SQLModel, CountryCommodityExposure, table=True):  # type: ignore
    __tablename__ = "countrycommodityexposure"
    country: str = Field(primary_key=True, index=True)
    commodity: str = Field(primary_key=True, index=True)
    direction: str = Field(primary_key=True)  # type: ignore[assignment]
    year: int = Field(primary_key=True)


class InsiderTransactionORM(SQLModel, InsiderTransaction, table=True):  # type: ignore
    __tablename__ = "insidertransaction"
    accession_number: str = Field(primary_key=True)
    line_no: int = Field(primary_key=True)
    symbol: str = Field(index=True)
    transaction_date: dt.date = Field(index=True)
    acquired_disposed: str  # type: ignore[assignment]


class CountryRefORM(SQLModel, CountryRef, table=True):  # type: ignore
    __tablename__ = "countryref"
    iso3: str = Field(primary_key=True)
    iso2: str = Field(index=True)


class CountryAliasORM(SQLModel, CountryAlias, table=True):  # type: ignore
    __tablename__ = "countryalias"
    alias: str = Field(primary_key=True)
    iso3: str = Field(index=True)


class SectorCommoditySensitivityORM(SQLModel, SectorCommoditySensitivity, table=True):  # type: ignore
    __tablename__ = "sectorcommoditysensitivity"
    sector: str = Field(primary_key=True)
    commodity: str = Field(primary_key=True, index=True)
    direction: int  # type: ignore[assignment]
    strength: str  # type: ignore[assignment]


class EtfExposureORM(SQLModel, EtfExposure, table=True):  # type: ignore
    __tablename__ = "etfexposure"
    symbol: str = Field(primary_key=True, index=True)
    entity_type: str = Field(primary_key=True)  # type: ignore[assignment]
    entity: str = Field(primary_key=True, index=True)
    method: str  # type: ignore[assignment]


class Holding13FORM(SQLModel, Holding13F, table=True):  # type: ignore
    __tablename__ = "holding13f"
    accession_number: str = Field(primary_key=True)
    cusip: str = Field(primary_key=True, index=True)
    put_call: str = Field(primary_key=True, default="")  # type: ignore[assignment]
    manager_cik: str = Field(index=True)
    symbol: Optional[str] = Field(default=None, index=True)
    period: dt.date = Field(index=True)


class Holding13FSummaryORM(SQLModel, Holding13FSummary, table=True):  # type: ignore
    __tablename__ = "holding13fsummary"
    cusip: str = Field(primary_key=True)
    period: dt.date = Field(primary_key=True, index=True)
    symbol: Optional[str] = Field(default=None, index=True)


class Ownership13DGORM(SQLModel, Ownership13DG, table=True):  # type: ignore
    __tablename__ = "ownership13dg"
    accession_number: str = Field(primary_key=True)
    reporting_person: str = Field(primary_key=True)
    symbol: str = Field(index=True)
    filed_date: dt.date = Field(index=True)


class MarketEventORM(SQLModel, MarketEvent, table=True):  # type: ignore
    __tablename__ = "marketevent"
    event_id: str = Field(primary_key=True)
    event_type: str = Field(index=True)  # type: ignore[assignment]
    date: dt.date = Field(index=True)


class EventReturnORM(SQLModel, EventReturn, table=True):  # type: ignore
    __tablename__ = "eventreturn"
    event_id: str = Field(primary_key=True, index=True)
    asset: str = Field(primary_key=True, index=True)
    window: str = Field(primary_key=True)


class TickerSignalORM(SQLModel, TickerSignal, table=True):  # type: ignore
    """Point-in-time store: one row per (symbol, signal, date, vintage)."""

    __tablename__ = "tickersignal"
    symbol: str = Field(primary_key=True, index=True)
    signal: str = Field(primary_key=True, index=True)
    date: dt.date = Field(primary_key=True, index=True)
    as_of: dt.date = Field(primary_key=True)


class CongressTradeORM(SQLModel, CongressTrade, table=True):  # type: ignore
    __tablename__ = "congresstrade"
    doc_id: str = Field(primary_key=True)
    line_no: int = Field(primary_key=True)
    chamber: str = Field(index=True)  # type: ignore[assignment]
    symbol: Optional[str] = Field(default=None, index=True)
    filed_date: dt.date = Field(index=True)


class PredictionQuoteORM(SQLModel, PredictionQuote, table=True):  # type: ignore
    __tablename__ = "predictionquote"
    platform: str = Field(primary_key=True)  # type: ignore[assignment]
    market_id: str = Field(primary_key=True)
    outcome: str = Field(primary_key=True)
    as_of: dt.date = Field(primary_key=True, index=True)
    category: Optional[str] = Field(default=None, index=True)
