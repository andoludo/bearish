import logging
import time
from datetime import date

from typing import List, Optional, Dict, Any, Callable, cast

import pandas as pd
import yfinance as yf  # type: ignore
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    wait_exponential,
)

from bearish.exchanges.exchanges import Countries
from bearish.models.assets.etfs import Etf
from bearish.models.base import Ticker
from bearish.models.financials.earnings_date import EarningsDate
from bearish.models.query.query import AssetQuery
from bearish.models.assets.equity import Equity
from bearish.models.financials.balance_sheet import QuarterlyBalanceSheet
from bearish.models.financials.cash_flow import QuarterlyCashFlow
from bearish.models.financials.metrics import (
    QuarterlyFinancialMetrics,
)
from bearish.models.price.price import Price

from bearish.sources.base import (
    AbstractSource,
)
from bearish.models.financials.base import Financials
from bearish.models.assets.assets import Assets, FailedQueryAssets
from bearish.types import Sources, SeriesLength, DELAY

logger = logging.getLogger(__name__)


class YfinanceBase(BaseModel):
    __source__: Sources = "Yfinance"


@retry(
    wait=wait_exponential(multiplier=1, min=60, max=1200),
    stop=stop_after_attempt(5),
    reraise=True,
)
def get_data_frame(
    ticker_: yf.Ticker,
    attribute: str,
    transpose: bool = True,
    prefix: Optional[str] = None,
) -> pd.DataFrame:
    attribute_ = attribute if not prefix else f"{prefix}_{attribute}"
    data = getattr(ticker_, attribute_).T if transpose else getattr(ticker_, attribute_)
    if data is None:
        return pd.DataFrame()
    data.index = [date(index.year, index.month, index.day) for index in data.index]
    data = data.reset_index(names=["date"])
    return cast(pd.DataFrame, data)


class YfinanceFinancialBase(YfinanceBase):
    @classmethod
    def _from_ticker(
        cls,
        ticker_: yf.Ticker,
        attribute: str,
        transpose: bool = True,
        prefix: Optional[str] = None,
    ) -> List["YfinanceFinancialBase"]:
        try:
            data = get_data_frame(
                ticker_, attribute, transpose=transpose, prefix=prefix
            )
            time.sleep(DELAY)
            return [
                cls.model_validate(data_ | {"symbol": ticker_.ticker})
                for data_ in data.to_dict(orient="records")
            ]

        except Exception as e:
            logger.error(f"Error reading {ticker_.ticker} {attribute}: {e}")
            return []


@retry(stop=stop_after_attempt(2), wait=wait_fixed(10))
def get_info(
    ticker: Ticker, function: Callable[[str, yf.Ticker], Dict[str, Any]]
) -> Dict[str, Any]:
    current_ticker = yf.Ticker(ticker.symbol)
    info = function(ticker.symbol, current_ticker)
    return info


class YfinanceAssetOutput(BaseModel):
    equities: List["YfinanceAssetBase"]
    failed_query: List[Ticker] = Field(default_factory=list)


class YfinanceAssetBase(YfinanceBase):
    @classmethod
    def _from_tickers(
        cls, tickers: List[Ticker], function: Callable[[str, yf.Ticker], Dict[str, Any]]
    ) -> YfinanceAssetOutput:
        equities = []
        failed_query = []
        for ticker in tickers:
            try:
                info = get_info(ticker, function)
                if not info:
                    logger.error(f"No info found for {ticker.symbol}", exc_info=True)
                    failed_query.append(ticker)
                    continue
                logger.info(f"Successfully read {ticker.symbol}")
                equities.append(cls.model_validate(info))
            except Exception as e:
                logger.error(f"Error reading ticker: {e}", exc_info=True)
                failed_query.append(ticker)
                continue
            time.sleep(DELAY)  # To avoid hitting API limits
        return YfinanceAssetOutput(equities=equities, failed_query=failed_query)


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
    def from_tickers(cls, tickers: List[Ticker]) -> YfinanceAssetOutput:
        return cls._from_tickers(tickers, lambda ticker, x: x.info)


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
    def from_tickers(cls, tickers: List[Ticker]) -> YfinanceAssetOutput:
        return cls._from_tickers(tickers, _get_etf)


class YfinanceFinancialMetrics(YfinanceFinancialBase, QuarterlyFinancialMetrics):
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
    def from_ticker(
        cls, ticker: yf.Ticker, prefix: Optional[str] = None
    ) -> List["YfinanceFinancialMetrics"]:
        return cls._from_ticker(ticker, "financials", prefix=prefix)  # type: ignore


class yFinanceEarningsDate(YfinanceFinancialBase, EarningsDate):
    __alias__ = {
        "symbol": "symbol",
        "EPS Estimate": "eps_estimate",
        "Reported EPS": "eps_reported",
    }

    @classmethod
    def from_ticker(
        cls, ticker: yf.Ticker, prefix: Optional[str] = None
    ) -> List["yFinanceEarningsDate"]:
        return cls._from_ticker(ticker, "earnings_dates", transpose=False, prefix=prefix)  # type: ignore


class yFinanceBalanceSheet(YfinanceFinancialBase, QuarterlyBalanceSheet):
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
    def from_ticker(
        cls, ticker: yf.Ticker, prefix: Optional[str] = None
    ) -> List["yFinanceBalanceSheet"]:
        return cls._from_ticker(ticker, "balance_sheet", prefix=prefix)  # type: ignore


class yFinanceCashFlow(YfinanceFinancialBase, QuarterlyCashFlow):
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
    def from_ticker(
        cls, ticker: yf.Ticker, prefix: Optional[str] = None
    ) -> List["yFinanceCashFlow"]:
        return cls._from_ticker(ticker, "cashflow", prefix=prefix)  # type: ignore


class yFinancePrice(YfinanceBase, Price):
    __alias__ = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "symbol": "symbol",
        "Date": "date",
    }


class yFinanceSource(YfinanceBase, AbstractSource):
    countries: List[Countries] = [
        "United Kingdom",
        "Germany",
        "France",
        "Netherlands",
        "Belgium",
        "US",
    ]

    def set_api_key(self, api_key: str) -> None: ...
    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        if query is None:
            return Assets()

        if query.symbols.empty():
            return Assets()
        equities = YfinanceEquity.from_tickers(query.symbols.equities)
        etfs = YfinanceEtf.from_tickers(query.symbols.etfs)
        return Assets(
            equities=equities.equities,
            etfs=etfs.equities,
            failed_query=FailedQueryAssets(
                symbols=etfs.failed_query + equities.failed_query
            ),
        )

    def _read_financials(self, tickers: List[str]) -> List[Financials]:
        financials = []
        for ticker in tickers:
            try:
                ticker_ = yf.Ticker(ticker)
            except Exception as e:
                logger.error(f"Error reading financials for {ticker}: {e}")
                continue
            financials.append(
                Financials(
                    financial_metrics=YfinanceFinancialMetrics.from_ticker(ticker_),
                    balance_sheets=yFinanceBalanceSheet.from_ticker(ticker_),
                    cash_flows=yFinanceCashFlow.from_ticker(ticker_),
                    quarterly_financial_metrics=YfinanceFinancialMetrics.from_ticker(
                        ticker_, prefix="quarterly"
                    ),
                    quarterly_balance_sheets=yFinanceBalanceSheet.from_ticker(
                        ticker_, prefix="quarterly"
                    ),
                    quarterly_cash_flows=yFinanceCashFlow.from_ticker(
                        ticker_, prefix="quarterly"
                    ),
                    earnings_date=yFinanceEarningsDate.from_ticker(ticker_),
                )
            )
        return financials

    def _read_series(  # type: ignore
        self, tickers: List[str], type: SeriesLength
    ) -> List[yFinancePrice]:
        data = yf.download(
            tickers, period=type, group_by="ticker", auto_adjust=True, timeout=60
        )
        missing_tickers = [
            ticker for ticker in tickers if data[(ticker, "Close")].dropna().empty
        ]
        if missing_tickers:
            time.sleep(self.pause)
            valid_tickers = list(set(tickers).difference(set(missing_tickers)))
            data = data[valid_tickers]
            logger.warning(f"Missing tickers: {missing_tickers}")
            print(f"Missing tickers: {missing_tickers}")
            data_missing = yf.download(
                missing_tickers,
                period=type,
                group_by="ticker",
                auto_adjust=True,
                timeout=60,
            )
            if not data_missing.empty:
                data = pd.concat([data, data_missing], axis=1)
            else:
                print("None of the missing tickers where found")

        records_final = []
        for ticker in tickers:
            try:
                if ticker in data.columns:
                    records = data[ticker].reset_index().to_dict(orient="records")
                    if not records:
                        logger.error(f"No data found for ticker: {ticker}")
                    records_final.extend(
                        [
                            yFinancePrice(
                                **(
                                    record
                                    | {
                                        "symbol": ticker,
                                        "Date": pd.to_datetime(record["Date"]).date(),
                                    }
                                )
                            )
                            for record in records
                        ]
                    )
            except Exception as e:  # noqa: PERF203
                logger.error(f"Error reading series for {ticker}: {e}")
        time.sleep(self.pause)
        return records_final
