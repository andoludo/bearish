from typing import List

from pydantic import BaseModel, Field

from bearish.models.financials.balance_sheet import BalanceSheet
from bearish.models.financials.cash_flow import CashFlow
from bearish.models.financials.earnings_date import EarningsDate
from bearish.models.financials.metrics import FinancialMetrics


class Financials(BaseModel):
    financial_metrics: List[FinancialMetrics] = Field(default_factory=list)
    balance_sheets: List[BalanceSheet] = Field(default_factory=list)
    cash_flows: List[CashFlow] = Field(default_factory=list)
    earnings_date: List[EarningsDate] = Field(default_factory=list)

    def add(self, financials: "Financials") -> None:
        self.financial_metrics.extend(financials.financial_metrics)
        self.balance_sheets.extend(financials.balance_sheets)
        self.cash_flows.extend(financials.cash_flows)
        self.earnings_date.extend(financials.earnings_date)

    def is_empty(self) -> bool:
        return not any(
            [
                self.financial_metrics,
                self.balance_sheets,
                self.cash_flows,
                self.earnings_date,
            ]
        )
