import datetime
import logging
from typing import List, Dict, Any, TYPE_CHECKING

import pandas as pd
from pydantic import BaseModel, Field

from bearish.models.base import Ticker, DataSourceBase
from bearish.models.financials.balance_sheet import BalanceSheet, QuarterlyBalanceSheet
from bearish.models.financials.cash_flow import CashFlow, QuarterlyCashFlow
from bearish.models.financials.earnings_date import EarningsDate
from bearish.models.financials.metrics import (
    FinancialMetrics,
    QuarterlyFinancialMetrics,
)
from bearish.models.query.query import AssetQuery, Symbols

if TYPE_CHECKING:
    from bearish.interface.interface import BearishDbBase
logger = logging.getLogger(__name__)


class Financials(BaseModel):
    financial_metrics: List[FinancialMetrics] = Field(default_factory=list)
    balance_sheets: List[BalanceSheet] = Field(default_factory=list)
    cash_flows: List[CashFlow] = Field(default_factory=list)
    quarterly_financial_metrics: List[QuarterlyFinancialMetrics] = Field(
        default_factory=list
    )
    quarterly_balance_sheets: List[QuarterlyBalanceSheet] = Field(default_factory=list)
    quarterly_cash_flows: List[QuarterlyCashFlow] = Field(default_factory=list)
    earnings_date: List[EarningsDate] = Field(default_factory=list)

    def _get_dates(self) -> List[datetime.date]:
        dates = sorted(
            {
                field_.date
                for field in self.model_fields
                for field_ in getattr(self, field)
            }
        )
        return dates

    def add(self, financials: "Financials") -> None:
        self.financial_metrics.extend(financials.financial_metrics)
        self.balance_sheets.extend(financials.balance_sheets)
        self.cash_flows.extend(financials.cash_flows)
        self.quarterly_financial_metrics.extend(financials.quarterly_financial_metrics)
        self.quarterly_balance_sheets.extend(financials.quarterly_balance_sheets)
        self.quarterly_cash_flows.extend(financials.quarterly_cash_flows)
        self.earnings_date.extend(financials.earnings_date)

    def is_empty(self) -> bool:
        return not any(
            [
                self.financial_metrics,
                self.balance_sheets,
                self.cash_flows,
                self.quarterly_financial_metrics,
                self.quarterly_balance_sheets,
                self.quarterly_cash_flows,
                self.earnings_date,
            ]
        )

    def _compute_growth(self, data: pd.DataFrame, field: str) -> Dict[str, Any]:
        data[f"{field}_growth"] = data[field].pct_change() * 100
        return {
            f"{field}_growth_{i}": value
            for i, value in enumerate(
                data[f"{field}_growth"].sort_index(ascending=False).tolist()
            )
        }

    @classmethod
    def from_ticker(cls, bearish_db: "BearishDbBase", ticker: Ticker) -> "Financials":
        return bearish_db.read_financials(
            AssetQuery(symbols=Symbols(equities=[ticker]))  # type: ignore
        )


class ManyFinancials(BaseModel):
    financials: List[Financials] = Field(default_factory=list)

    def get(self, attribute: str) -> List[DataSourceBase]:
        return [
            a
            for financial in self.financials
            if hasattr(financial, attribute)
            for a in getattr(financial, attribute)
        ]


class FinancialsWithDate(Financials):
    date: datetime.date

    @classmethod
    def from_financials(cls, financials_: Financials) -> List["FinancialsWithDate"]:
        financials_with_dates = []
        for date in financials_._get_dates():
            financials = cls(date=date)
            for field in financials_.model_fields:
                setattr(
                    financials,
                    field,
                    [
                        field_
                        for field_ in getattr(financials_, field)
                        if field_.date <= date
                    ],
                )
            financials_with_dates.append(financials)
        return financials_with_dates
