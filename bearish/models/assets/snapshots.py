"""Dated copies of the fast-moving fields of ``equity`` and ``etf``.

The asset tables are overwritten on every detailed fetch, so market
capitalisation, short interest, valuation ratios, ETF assets under
management and NAV only exist as "latest" values. Snapshots keep one row per
``(symbol, source, as_of)`` so that downstream analysis can compute fund
flows, premium / discount to NAV, short-interest trends and valuation
history. Raw data only: nothing is derived here.
"""

import datetime
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from bearish.models.assets.assets import Assets
from bearish.models.assets.equity import Equity
from bearish.models.assets.etfs import Etf


class _Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    source: str
    as_of: datetime.date = Field(description="Date the values were fetched")

    _VALUE_FIELDS: ClassVar[tuple[str, ...]] = ()

    def is_empty(self) -> bool:
        return all(getattr(self, field) is None for field in self._VALUE_FIELDS)


class EquitySnapshot(_Snapshot):
    """Point-in-time copy of the provider-reported equity fields that change daily."""

    market_capitalization: Optional[float] = None
    shares_outstanding: Optional[float] = None
    float_shares: Optional[float] = None
    short_shares: Optional[float] = Field(default=None, description="Shares sold short (short interest)")
    short_ratio: Optional[float] = Field(default=None, description="Days to cover: short shares / average volume")
    price_to_book: Optional[float] = None
    trailing_price_to_earnings: Optional[float] = None
    forward_price_to_earnings: Optional[float] = None
    trailing_price_to_sales: Optional[float] = None
    trailing_peg_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    trailing_earnings_per_share: Optional[float] = None
    forward_earnings_per_share: Optional[float] = None
    return_on_equity: Optional[float] = None
    return_on_assets: Optional[float] = None
    gross_margins: Optional[float] = None
    operating_margins: Optional[float] = None
    revenue_growth: Optional[float] = None
    earning_growth: Optional[float] = None

    _VALUE_FIELDS: ClassVar[tuple[str, ...]] = (
        "market_capitalization",
        "shares_outstanding",
        "float_shares",
        "short_shares",
        "short_ratio",
        "price_to_book",
        "trailing_price_to_earnings",
        "forward_price_to_earnings",
        "trailing_price_to_sales",
        "trailing_peg_ratio",
        "dividend_yield",
        "trailing_earnings_per_share",
        "forward_earnings_per_share",
        "return_on_equity",
        "return_on_assets",
        "gross_margins",
        "operating_margins",
        "revenue_growth",
        "earning_growth",
    )

    @classmethod
    def from_equity(cls, equity: Equity, as_of: Optional[datetime.date] = None) -> "EquitySnapshot":
        values = {field: getattr(equity, field) for field in cls._VALUE_FIELDS}
        return cls(symbol=equity.symbol, source=equity.source, as_of=as_of or datetime.date.today(), **values)


class EtfSnapshot(_Snapshot):
    """Point-in-time copy of the provider-reported fund fields that change daily."""

    total_net_assets: Optional[float] = Field(default=None, description="Assets under management")
    nav_price: Optional[float] = None
    annual_report_expense_ratio: Optional[float] = None
    annual_holdings_turnover: Optional[float] = None
    price_to_earnings: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    price_to_cashflow: Optional[float] = None
    yield_: Optional[float] = None
    ytd_return: Optional[float] = None
    three_year_average_return: Optional[float] = None
    holding_percent: Optional[Dict[str, float]] = Field(default=None, description="Top holdings and their weight")
    sector_weightings: Optional[Dict[str, float]] = None

    _VALUE_FIELDS: ClassVar[tuple[str, ...]] = (
        "total_net_assets",
        "nav_price",
        "annual_report_expense_ratio",
        "annual_holdings_turnover",
        "price_to_earnings",
        "price_to_book",
        "price_to_sales",
        "price_to_cashflow",
        "yield_",
        "ytd_return",
        "three_year_average_return",
        "holding_percent",
        "sector_weightings",
    )

    @classmethod
    def from_etf(cls, etf: Etf, as_of: Optional[datetime.date] = None) -> "EtfSnapshot":
        values: Dict[str, Any] = {field: getattr(etf, field) for field in cls._VALUE_FIELDS}
        return cls(symbol=etf.symbol, source=etf.source, as_of=as_of or datetime.date.today(), **values)


class Snapshots(BaseModel):
    equities: List[EquitySnapshot] = Field(default_factory=list)
    etfs: List[EtfSnapshot] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.equities and not self.etfs

    @classmethod
    def from_assets(cls, assets: Assets, as_of: Optional[datetime.date] = None) -> "Snapshots":
        """Snapshots of every asset that carries at least one snapshot value.

        Base ticker sources (FinanceDatabase, InvestPy) have none of these
        fields, so only detailed fetches produce rows.
        """
        equities = [EquitySnapshot.from_equity(equity, as_of) for equity in assets.equities]
        etfs = [EtfSnapshot.from_etf(etf, as_of) for etf in assets.etfs]
        return cls(
            equities=[snapshot for snapshot in equities if not snapshot.is_empty()],
            etfs=[snapshot for snapshot in etfs if not snapshot.is_empty()],
        )
