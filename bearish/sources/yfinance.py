import logging
from datetime import date
from typing import List, Optional, Dict, Any, Callable

import pandas as pd
import yfinance as yf  # type: ignore
from pydantic import BaseModel

from bearish.models.assets.etfs import Etf
from bearish.models.query.query import AssetQuery
from bearish.models.assets.equity import Equity
from bearish.models.financials.balance_sheet import BalanceSheet
from bearish.models.financials.cash_flow import CashFlow
from bearish.models.financials.metrics import FinancialMetrics
from bearish.models.price.price import Price

from bearish.sources.base import (
    AbstractSource,
)
from bearish.models.financials.base import Financials
from bearish.models.assets.assets import Assets

logger = logging.getLogger(__name__)


class YfinanceBase(BaseModel):
    __source__ = "Yfinance"


class YfinanceFinancialBase(YfinanceBase):
    @classmethod
    def _from_ticker(cls, ticker: str, attribute: str) -> List["YfinanceFinancialBase"]:
        ticker_ = yf.Ticker(ticker)
        data = getattr(ticker_, attribute).T
        data.index = [date(index.year, index.month, index.day) for index in data.index]
        data = data.reset_index(names=["date"])
        return [
            cls.model_validate(data_ | {"symbol": ticker})
            for data_ in data.to_dict(orient="records")
        ]


class YfinanceAssetBase(YfinanceBase):
    @classmethod
    def _from_tickers(
        cls, tickers: List[str], function: Callable[[str, yf.Ticker], Dict[str, Any]]
    ) -> List["YfinanceAssetBase"]:
        equities = []
        tickers_ = yf.Tickers(" ".join(tickers))
        found_tickers = tickers_.tickers
        for ticker in tickers:
            if found_tickers.get(ticker):
                try:
                    equities.append(
                        cls.model_validate(function(ticker, found_tickers[ticker]))
                    )
                except Exception as e:
                    logger.error(f"Error reading {ticker}: {e}")
                    print(f"Error reading {ticker}: {e}")
        return equities


class YfinanceEquity(YfinanceAssetBase, Equity):
    __alias__ = {
        "symbol": "symbol",
        "longName": "name",
        "longBusinessSummary": "summary",
        "currency": "currency",
        "exchange": "exchange",
        "sectorDisp": "sector",  # 'sectorDisp' seems like the descriptive sector field
        "industryDisp": "industry",  # 'industryDisp' matches the detailed industry description
        "sector": "sector",
        "industry": "industry",
        "industryKey": "industry_group",
        "country": "country",
        "state": "state",
        "city": "city",
        "zip": "zipcode",
        "website": "website",
        "marketCap": "market_capitalization",
        "sharesOutstanding": "shares_outstanding",
        "floatShares": "float_shares",
        "sharesShort": "short_shares",
        "bookValue": "book_value",
        "priceToBook": "price_to_book",
        "trailingPE": "trailing_price_to_earnings",
        "forwardPE": "forward_price_to_earnings",
        "dividendYield": "dividend_yield",
        "dividendRate": "dividend_rate",
        "trailingEps": "trailing_earnings_per_share",
        "forwardEps": "forward_earnings_per_share",
        "returnOnEquity": "return_on_equity",
        "operatingMargins": "operating_margins",
        "grossMargins": "gross_margins",
        "revenueGrowth": "revenue_growth",
        "revenuePerShare": "revenue_per_share",
        "quickRatio": "quick_ratio",
        "currentRatio": "current_ratio",
        "earningsGrowth": "earning_growth",
        "trailingPegRatio": "trailing_peg_ratio",
        "priceToSalesTrailing12Months": "trailing_price_to_sales",
        "returnOnAssets": "return_on_assets",
        "shortRatio": "short_ratio",
        "timeZone": "timezone",
        "isin": "isin",
        "cusip": "cusip",
        "figi": "figi",
        "compositeFigi": "composite_figi",
        "shareclassFigi": "shareclass_figi",
    }

    @classmethod
    def from_tickers(cls, tickers: List[str]) -> List["YfinanceEquity"]:
        return cls._from_tickers(tickers, lambda ticker, x: x.info)  # type: ignore


def to_funds_data_dict(data: pd.DataFrame, ticker: str) -> Dict[str, Any]:
    data_dict = {}
    data_dict.update(data.to_dict().get(ticker, {}))
    return data_dict


def _get_etf(ticker: str, results: yf.Ticker) -> Dict[str, Any]:
    etf = {}
    etf.update(to_funds_data_dict(results.funds_data.fund_operations, ticker))
    etf.update(to_funds_data_dict(results.funds_data.equity_holdings, ticker))
    etf.update(results.funds_data.fund_overview)
    etf.update({"Sector Weightings": results.funds_data.sector_weightings})
    etf.update(
        {
            "Holding Percent": results.funds_data.top_holdings.to_dict().get(
                "Holding Percent", {}
            )
        }
    )
    etf.update({"summary": results.funds_data.description})
    etf.update({"isin": results.isin})
    etf.update(results.info)
    return etf


class YfinanceEtf(YfinanceAssetBase, Etf):
    __alias__ = {
        "symbol": "symbol",
        "Annual Report Expense Ratio": "annual_report_expense_ratio",
        "Annual Holdings Turnover": "annual_holdings_turnover",
        "Total Net Assets": "total_net_assets",
        "Price/Earnings": "price_to_earnings",
        "Price/Book": "price_to_book",
        "Price/Sales": "price_to_sales",
        "Price/Cashflow": "price_to_cashflow",
        "Median Market Cap": "median_market_cap",
        "3 Year Earnings Growth": "three_year_earnings_growth",
        "categoryName": "category",
        "family": "fund_family",
        "legalType": "legal_type",
        "Sector Weightings": "sector_weightings",
        "Holding Percent": "holding_percent",
        "summary": "long_business_summary",
        "isin": "isin",
        "longBusinessSummary": "long_business_summary",
        "trailingPE": "trailing_pe",
        "yield": "yield_",
        "navPrice": "nav_price",
        "currency": "currency",
        "category": "category",
        "ytdReturn": "ytd_return",
        "beta3Year": "beta_3_year",
        "fundFamily": "fund_family",
        "fundInceptionDate": "fund_inception_date",
        "threeYearAverageReturn": "three_year_average_return",
        "exchange": "exchange",
        "quoteType": "quote_type",
        "shortName": "short_name",
        "longName": "long_name",
    }

    @classmethod
    def from_tickers(cls, tickers: List[str]) -> List["YfinanceEtf"]:
        return cls._from_tickers(tickers, _get_etf)  # type: ignore


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
    def from_ticker(cls, ticker: str) -> List["YfinanceFinancialMetrics"]:
        return cls._from_ticker(ticker, "financials")  # type: ignore


class yFinanceBalanceSheet(YfinanceFinancialBase, BalanceSheet):  # noqa: N801
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
    def from_ticker(cls, ticker: str) -> List["yFinanceBalanceSheet"]:
        return cls._from_ticker(ticker, "balance_sheet")  # type: ignore


class yFinanceCashFlow(YfinanceFinancialBase, CashFlow):  # noqa: N801
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
    def from_ticker(cls, ticker: str) -> List["yFinanceCashFlow"]:
        return cls._from_ticker(ticker, "cashflow")  # type: ignore


class yFinancePrice(YfinanceBase, Price):  # noqa: N801
    __alias__ = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "symbol": "symbol",
        "Date": "date",
    }


class yFinanceSource(YfinanceBase, AbstractSource):  # noqa: N801
    def set_api_key(self, api_key: str) -> None: ...
    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        if query is None:
            return Assets()

        if query.symbols.empty():
            return Assets()
        equities = YfinanceEquity.from_tickers(query.symbols.equities)
        etfs = YfinanceEtf.from_tickers(query.symbols.etfs)
        return Assets(equities=equities, etfs=etfs)

    def _read_financials(self, ticker: str) -> Financials:
        return Financials(
            financial_metrics=YfinanceFinancialMetrics.from_ticker(ticker),
            balance_sheets=yFinanceBalanceSheet.from_ticker(ticker),
            cash_flows=yFinanceCashFlow.from_ticker(ticker),
        )

    def read_series(self, ticker: str, type: str) -> List[Price]:
        type = "max" if type == "full" else "5d"
        ticker_ = yf.Ticker(ticker)
        data = ticker_.history(period=type)
        records = data.reset_index().to_dict(orient="records")
        return [yFinancePrice(**(record | {"symbol": ticker})) for record in records]
