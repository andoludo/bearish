import logging
import time

from typing import List, Optional, Dict, Any, Callable

import pandas as pd
import yfinance as yf  # type: ignore
from pydantic import BaseModel, Field

from bearish.exchanges.exchanges import Countries
from bearish.models.base import Ticker
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
from yahooquery import Ticker as YahooQueryTicker  # type: ignore

from bearish.utils.utils import batch, safe_get

logger = logging.getLogger(__name__)


class YahooQueryBase(BaseModel):
    __source__: Sources = "YahooQuery"


class YahooQueryFinancialBase(YahooQueryBase):
    @classmethod
    def from_data_frame(
        cls,
        ticker_: str,
        data: pd.DataFrame,
    ) -> List["YahooQueryFinancialBase"]:
        return [
            cls.model_validate(data_ | {"symbol": ticker_})
            for data_ in data.to_dict(orient="records")
        ]


class YahooQueryAssetOutput(BaseModel):
    equities: List["YahooQueryAssetBase"]
    failed_query: List[Ticker] = Field(default_factory=list)


class YahooQueryAssetBase(YahooQueryBase):
    @classmethod
    def _from_tickers(
        cls, tickers: List[Ticker], function: Callable[[str, yf.Ticker], Dict[str, Any]]
    ) -> YahooQueryAssetOutput:
        equities = []
        failed_query: List[Ticker] = []
        chunks = batch(tickers, size=100)
        logger.debug(f"Retrieving {len(tickers)} assets.")
        for chunk in chunks:
            yahoo_tickers = YahooQueryTicker(
                " ".join([ticker.symbol for ticker in chunk])
            )
            asset_profile = yahoo_tickers.asset_profile
            summary_detail = yahoo_tickers.summary_detail
            summary_profile = yahoo_tickers.summary_profile
            key_stats = yahoo_tickers.key_stats
            financial_data = yahoo_tickers.financial_data
            quotes = yahoo_tickers.quotes
            for ticker in chunk:
                data = (
                    safe_get(asset_profile, ticker.symbol)
                    | safe_get(summary_detail, ticker.symbol)
                    | safe_get(summary_profile, ticker.symbol)
                    | safe_get(key_stats, ticker.symbol)
                    | safe_get(financial_data, ticker.symbol)
                    | safe_get(quotes, ticker.symbol)
                    | {"symbol": ticker.symbol}
                )
                equities.append(cls.model_validate(data))
            time.sleep(DELAY)  # Avoid hitting API rate limits
        logger.debug(f"Retrieved {len(equities)} assets.")
        return YahooQueryAssetOutput(equities=equities, failed_query=failed_query)


class YahooQueryEquity(YahooQueryAssetBase, Equity):
    __alias__ = {
        "city": "city",
        "zip": "zipcode",
        "country": "country",
        "website": "website",
        "industry": "industry",
        "industryKey": "industry_group",
        "sector": "sector",
        "dividendRate": "dividend_rate",
        "dividendYield": "dividend_yield",
        "marketCap": "market_capitalization",
        "currency": "currency",
        "market": "market",
        "profitMargins": "gross_margins",
        "floatShares": "float_shares",
        "sharesOutstanding": "shares_outstanding",
        "bookValue": "book_value",
        "priceToBook": "price_to_book",
        "earningsQuarterlyGrowth": "earning_growth",
        "trailingEps": "trailing_peg_ratio",
        "exchange": "exchange",
        "currentPrice": "current_ratio",
        "quickRatio": "quick_ratio",
        "revenuePerShare": "revenue_per_share",
        "returnOnAssets": "return_on_assets",
        "returnOnEquity": "return_on_equity",
        "operatingCashflow": "operating_margins",
        "revenueGrowth": "revenue_growth",
        "shortName": "short_shares",
        "longName": "name",
        "sourceInterval": "source",
        "symbol": "symbol",
    }

    @classmethod
    def from_tickers(cls, tickers: List[Ticker]) -> YahooQueryAssetOutput:
        return cls._from_tickers(tickers, lambda ticker, x: x.info)


class YahooQueryFinancialMetrics(YahooQueryFinancialBase, QuarterlyFinancialMetrics):
    __alias__ = {
        "symbol": "symbol",
        "asOfDate": "date",
        "EBITDA": "ebitda",
        "NetIncome": "net_income",
        "BasicEPS": "basic_eps",
        "DilutedEPS": "diluted_eps",
        "TotalRevenue": "total_revenue",
        "OperatingRevenue": "operating_revenue",
        "GrossProfit": "gross_profit",
        "TotalExpenses": "total_expenses",
        "OperatingIncome": "operating_income",
        "CostOfRevenue": "cost_of_revenue",
        "TaxProvision": "tax_provision",
        "TaxRateForCalcs": "tax_rate",
    }


class YahooQueryBalanceSheet(YahooQueryFinancialBase, QuarterlyBalanceSheet):
    __alias__ = {
        "symbol": "symbol",
        "asOfDate": "date",
        "TreasuryStock": "treasury_stock",
        "OrdinarySharesNumber": "common_stock_shares_outstanding",
        "CommonStock": "common_stock",
        "TotalDebt": "short_long_term_debt_total",
        "CapitalLeaseObligations": "capital_lease_obligations",
        "StockholdersEquity": "total_shareholder_equity",
        "RetainedEarnings": "retained_earnings",
        "TotalLiabilitiesNetMinorityInterest": "total_liabilities",
        "TotalNonCurrentLiabilitiesNetMinorityInterest": "total_non_current_liabilities",
        "OtherNonCurrentLiabilities": "other_non_current_liabilities",
        "LongTermDebt": "long_term_debt",
        "CurrentLiabilities": "total_current_liabilities",
        "OtherCurrentLiabilities": "other_current_liabilities",
        "CurrentDebt": "current_debt",
        "AccountsPayable": "current_accounts_payable",
        "TotalAssets": "total_assets",
        "TotalNonCurrentAssets": "total_non_current_assets",
        "OtherNonCurrentAssets": "other_non_current_assets",
        "AccumulatedDepreciation": "accumulated_depreciation_amortization_ppe",
        "GrossPPE": "property_plant_equipment",
        "CurrentAssets": "total_current_assets",
        "OtherCurrentAssets": "other_current_assets",
        "Inventory": "inventory",
        "AccountsReceivable": "current_net_receivables",
        "CashCashEquivalentsAndShortTermInvestments": "cash_and_short_term_investments",
        "CashAndCashEquivalents": "cash_and_cash_equivalents_at_carrying_value",
    }


class YahooQueryCashFlow(YahooQueryFinancialBase, QuarterlyCashFlow):
    __alias__ = {
        "symbol": "symbol",
        "asOfDate": "date",
        "OperatingCashFlow": "operating_cash_flow",
        "ChangeInOtherCurrentLiabilities": "change_in_operating_liabilities",
        "ChangeInWorkingCapital": "change_in_working_capital",
        "ChangeInOtherWorkingCapital": "change_in_other_working_capital",
        "ChangeInReceivables": "change_in_receivables",
        "ChangeInInventory": "change_in_inventory",
        "DepreciationAmortizationDepletion": "depreciation_amortization_depletion",
        "CapitalExpenditure": "capital_expenditure",
        "InvestingCashFlow": "cash_flow_from_investing_activities",
        "FinancingCashFlow": "financing_cash_flow",
        "RepurchaseOfCapitalStock": "repurchase_of_capital_stock",
        "CashDividendsPaid": "cash_dividends_paid",
        "CommonStockDividendPaid": "common_stock_dividend_paid",
        "CommonStockIssuance": "proceeds_from_issuance_of_common_stock",
        "ChangesInCash": "changes_in_cash",
        "NetIncomeFromContinuingOperations": "net_income_from_continuing_operations",
    }


class YahooQueryPrice(YahooQueryBase, Price):
    __alias__ = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "symbol": "symbol",
        "Date": "date",
    }


class YahooQuerySource(YahooQueryBase, AbstractSource):
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
        equities = YahooQueryEquity.from_tickers(query.symbols.equities)
        return Assets(
            equities=equities.equities,
            failed_query=FailedQueryAssets(symbols=equities.failed_query),
        )

    def _read_financials(self, tickers: List[str]) -> List[Financials]:
        financials = []
        yahoo_tickers = YahooQueryTicker(" ".join(tickers))
        cash_flow = yahoo_tickers.cash_flow()
        balance_sheet = yahoo_tickers.balance_sheet()
        income_statement = yahoo_tickers.income_statement()
        for ticker in tickers:
            current_cash_flow = cash_flow[cash_flow.index == ticker]
            current_balance_sheet = balance_sheet[balance_sheet.index == ticker]
            current_income_statement = income_statement[
                income_statement.index == ticker
            ]
            financials.append(
                Financials(
                    financial_metrics=YahooQueryFinancialMetrics.from_data_frame(
                        ticker, current_income_statement
                    ),
                    balance_sheets=YahooQueryBalanceSheet.from_data_frame(
                        ticker, current_balance_sheet
                    ),
                    cash_flows=YahooQueryCashFlow.from_data_frame(
                        ticker, current_cash_flow
                    ),
                )
            )
        return financials

    def _read_series(self, tickers: List[str], type: SeriesLength) -> List[Price]:
        yahoo_tickers = YahooQueryTicker(" ".join(tickers))
        data = yahoo_tickers.history(period=type)
        records = data.reset_index().to_dict(orient="records")
        return [YahooQueryPrice(**(record)) for record in records]
