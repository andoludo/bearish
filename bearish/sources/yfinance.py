from datetime import date
from typing import List, Optional

import yfinance as yf
from pydantic import Field

from bearish.models.base import Equity, Crypto, Etf, Currency
from bearish.models.financials import FinancialMetrics, BalanceSheet, CashFlow
from bearish.sources.base import (
    BaseFinancialsComponentSource,
    AbstractSource,
    BaseFinancialsSource, AbstractAssetsSource,
)


class YfinanceFinancialBase(BaseFinancialsComponentSource):
    __source__ = "Yfinance"

    @classmethod
    def _from_ticker(cls, ticker: str, attribute: str):
        ticker_ = yf.Ticker(ticker)
        data = getattr(ticker_, attribute).T
        data.index = [date(index.year, index.month, index.day) for index in data.index]
        data.reset_index(names=["date"], inplace=True)
        return [
            cls.model_validate((data_ | {"symbol": ticker}))
            for data_ in data.to_dict(orient="records")
        ]


class YfinanceFinancialMetrics(YfinanceFinancialBase, FinancialMetrics):
    __alias__ = {
        "symbol": "symbol",
        "EBITDA": "ebitda",
        "Net Income": "net_income",
        "Basic EPS": "basic_eps",
        "Diluted EPS": "diluted_eps",
        "Total Revenue": "total_revenue",
        "Operating Revenue": "operating_revenue",
        "Gross Profit": "gross_profit",
        "Total Expenses": "total_expenses",
        "Operating Income": "operating_income",
        "Cost Of Revenue": "cost_of_revenue",
        "Tax Provision": "tax_provision",
        "Tax Rate For Calcs": "tax_rate",
    }

    @classmethod
    def from_ticker(cls, ticker: str):
        return cls._from_ticker(ticker, "financials")


class yFinanceBalanceSheet(YfinanceFinancialBase, BalanceSheet):
    __alias__ = {
        "symbol": "symbol",
        "Treasury Shares Number": "treasury_stock",
        "Ordinary Shares Number": "common_stock_shares_outstanding",
        "Share Issued": "common_stock",
        "Total Debt": "short_long_term_debt_total",
        "Capital Lease Obligations": "capital_lease_obligations",
        "Common Stock Equity": "common_stock",  # Closest match
        "Total Equity Gross Minority Interest": "total_shareholder_equity",
        "Stockholders Equity": "total_shareholder_equity",
        "Retained Earnings": "retained_earnings",
        "Capital Stock": "common_stock",  # Closest match
        "Common Stock": "common_stock",
        "Total Liabilities Net Minority Interest": "total_liabilities",
        "Total Non Current Liabilities Net Minority Interest": "total_non_current_liabilities",
        "Other Non Current Liabilities": "other_non_current_liabilities",
        "Long Term Capital Lease Obligation": "capital_lease_obligations",  # Closest match
        "Long Term Debt": "long_term_debt",
        "Current Liabilities": "total_current_liabilities",
        "Other Current Liabilities": "other_current_liabilities",
        "Current Debt And Capital Lease Obligation": "current_debt",  # Closest match
        "Current Capital Lease Obligation": "capital_lease_obligations",  # Closest match
        "Current Debt": "current_debt",
        "Payables": "current_accounts_payable",  # Closest match
        "Accounts Payable": "current_accounts_payable",
        "Total Assets": "total_assets",
        "Total Non Current Assets": "total_non_current_assets",
        "Other Non Current Assets": "other_non_current_assets",
        "Net PPE": "property_plant_equipment",  # Closest match
        "Accumulated Depreciation": "accumulated_depreciation_amortization_ppe",
        "Gross PPE": "property_plant_equipment",
        "Current Assets": "total_current_assets",
        "Other Current Assets": "other_current_assets",
        "Inventory": "inventory",
        "Receivables": "current_net_receivables",
        "Accounts Receivable": "current_net_receivables",
        "Cash Cash Equivalents And Short Term Investments": "cash_and_short_term_investments",
        "Cash And Cash Equivalents": "cash_and_cash_equivalents_at_carrying_value",
        "Cash Equivalents": "cash_and_short_term_investments",  # Closest match
    }

    @classmethod
    def from_ticker(cls, ticker: str):
        return cls._from_ticker(ticker, "balance_sheet")


class yFinanceCashFlow(YfinanceFinancialBase, CashFlow):
    __alias__ = {
        "symbol": "symbol",
        "Operating Cash Flow": "operating_cash_flow",
        "Change In Payables And Accrued Expense": "change_in_operating_liabilities",  # Closest Match
        "Change In Working Capital": "change_in_working_capital",
        "Change In Other Working Capital": "change_in_other_working_capital",
        "Change In Receivables": "change_in_receivables",
        "Change In Inventory": "change_in_inventory",
        "Depreciation Amortization Depletion": "depreciation_amortization_depletion",
        "Capital Expenditure": "capital_expenditure",
        "Investing Cash Flow": "cash_flow_from_investing_activities",
        "Financing Cash Flow": "financing_cash_flow",
        "Repurchase Of Capital Stock": "repurchase_of_capital_stock",
        "Cash Dividends Paid": "cash_dividends_paid",
        "Common Stock Dividend Paid": "common_stock_dividend_paid",
        "Common Stock Issuance": "proceeds_from_issuance_of_common_stock",
        "Changes In Cash": "changes_in_cash",
        "Net Income From Continuing Operations": "net_income_from_continuing_operations",
    }

    @classmethod
    def from_ticker(cls, ticker: str) -> "yFinanceCashFlow":
        return cls._from_ticker(ticker, "cashflow")


class yFinanceFinancialsSource(BaseFinancialsSource):
    def financial_metrics(self, ticker: str) -> List[FinancialMetrics]:
        return YfinanceFinancialMetrics.from_ticker(ticker)

    def balance_sheets(self, ticker: str) -> List[BalanceSheet]:
        return yFinanceBalanceSheet.from_ticker(ticker)

    def cash_flows(self, ticker: str) -> List[CashFlow]:
        return yFinanceCashFlow.from_ticker(ticker)

class yFinanceAssetSource(AbstractAssetsSource):
    def equities(self, filters: Optional[List[str]] = None) -> List[Equity]:
        return []

    def cryptos(self, filters: Optional[List[str]] = None) -> List[Crypto]:
        return []


    def etfs(self, filters: Optional[List[str]] = None) -> List[Etf]:
        return []


    def currencies(self, filters: Optional[List[str]] = None) -> List[Currency]:
        return []

class yFinanceSource(AbstractSource):
    assets:yFinanceAssetSource = Field(default_factory=yFinanceAssetSource)
    financials: yFinanceFinancialsSource = Field(default_factory=yFinanceFinancialsSource)
