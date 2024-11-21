from datetime import date
from typing import List, Optional

import yfinance as yf
from pydantic import BaseModel

from bearish.models.base import Equity, CandleStick
from bearish.models.financials import FinancialMetrics, BalanceSheet, CashFlow
from bearish.sources.base import (
    AbstractSource,
    Assets,
    Financials,
)
class YfinanceBase(BaseModel):
    __source__ = "Yfinance"

class YfinanceFinancialBase(YfinanceBase):
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


class YfinanceEquityBase(YfinanceBase):
    @classmethod
    def from_tickers(cls, tickers: List[str]):
        tickers_ = yf.Tickers(" ".join(tickers))
        return [cls.model_validate(tickers_.tickers[ticker].info) for ticker in tickers]


class YfinanceEquity(YfinanceEquityBase, Equity):
    __alias__ = {
        "symbol": "symbol",
        "longName": "name",
        "longBusinessSummary": "summary",
        "currency": "currency",
        "exchange": "exchange",
        "quoteType": "market",  # Closest matching field to market classification
        "sectorDisp": "sector",  # 'sectorDisp' seems like the descriptive sector field
        "sector": "industry_group",  # Assuming industry group maps broadly to sector
        "industryDisp": "industry",  # 'industryDisp' matches the detailed industry description
        "country": "country",
        "state": "state",
        "city": "city",
        "zip": "zipcode",
        "website": "website",
    }


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

class yFinanceCandleStick(YfinanceBase, CandleStick):
    __alias__ = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "symbol": "symbol",
        "Date": "date",
    }

class yFinanceSource(AbstractSource):
    def read_assets(self, filters: Optional[List[str]] = None) -> Assets:
        equities = YfinanceEquity.from_tickers(filters)
        return Assets(equities=equities)

    def read_financials(self, ticker: str) -> Financials:
        return Financials(
            financial_metrics=YfinanceFinancialMetrics.from_ticker(ticker),
            balance_sheets=yFinanceBalanceSheet.from_ticker(ticker),
            cash_flows=yFinanceCashFlow.from_ticker(ticker),
        )

    def read_series(self, ticker: str, type: str) -> List[CandleStick]:
        type = "max" if type == "full" else "5d"
        ticker_ = yf.Ticker(ticker)
        data = ticker_.history(period=type)
        records = data.reset_index().to_dict(orient="records")
        return [
            yFinanceCandleStick(**(record | {"symbol": ticker})) for record in records
        ]
