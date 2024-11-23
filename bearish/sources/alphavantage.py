import logging
import os
from typing import List, Optional, ClassVar, cast, Any, Dict

import pandas as pd
from alpha_vantage.fundamentaldata import FundamentalData  # type: ignore
from alpha_vantage.timeseries import TimeSeries  # type: ignore
from pydantic import BaseModel

from bearish.models.base import Equity, CandleStick
from bearish.models.financials import FinancialMetrics, BalanceSheet, CashFlow
from bearish.sources.base import (
    AbstractSource,
    Assets,
    Financials,
)

logger = logging.getLogger(__name__)


class AlphaVantageBase(BaseModel):
    __source__: str = "AlphaVantage"
    fundamentals: ClassVar[FundamentalData] = FundamentalData(
        key=os.environ["ALPHAVANTAGE_API_KEY"]
    )
    timeseries: ClassVar[TimeSeries] = TimeSeries(
        key=os.environ["ALPHAVANTAGE_API_KEY"]
    )


class AlphaVantageBaseFinancials(AlphaVantageBase):
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "AlphaVantageBaseFinancials":
        return cls.model_validate(data)

    @classmethod
    def from_dataframe(
        cls, ticker: str, data: pd.DataFrame
    ) -> List["AlphaVantageBaseFinancials"]:
        return [
            cls.model_validate(bs | {"symbol": ticker})
            for bs in data.to_dict(orient="records")
        ]


class AlphaVantageEquity(AlphaVantageBase, Equity):
    __alias__ = {
        "Symbol": "symbol",  # Unique ticker symbol
        "Name": "name",  # Full name of the company
        "Description": "summary",  # Brief summary of the company's operations
        "Currency": "currency",  # Currency code
        "Exchange": "exchange",  # Stock exchange abbreviation
        "AssetType": "market",  # Closest match to market classification
        "Sector": "sector",  # Broad sector classification
        "Industry": "industry_group",  # Closest match to industry grouping
        "Country": "country",  # Headquarters location
        "region": "city",  # Aggregates state, city, and zipcode
        "currency": "currency",  # Aggregates state, city, and zipcode
        "OfficialSite": "website",  # URL of the company's official website
    }

    @classmethod
    def from_tickers(
        cls, tickers: Optional[List[str]] = None
    ) -> List["AlphaVantageEquity"]:
        equities = []
        tickers = tickers or []
        for ticker in tickers:
            data, _ = cls.timeseries.get_symbol_search(ticker)
            data = data.rename(
                columns={c: c.split(".")[-1].strip() for c in data.columns}
            )
            records = data.to_dict(orient="records")
            for record in records:
                try:
                    overview, _ = cls.fundamentals.get_company_overview(
                        record["symbol"]
                    )
                except Exception as e:
                    logger.exception(
                        f"Failed to fetch company overview for {record['symbol']}. Reason: {e}",
                    )
                    continue
                equities.append(overview | record)
        return [AlphaVantageEquity.model_validate(equity) for equity in equities]


class AlphaVantageFinancialMetrics(AlphaVantageBaseFinancials, FinancialMetrics):
    __alias__ = {
        "Symbol": "symbol",
        "EBITDA": "ebitda",
        "Net Income": "net_income",
        "PERatio": "pe_ratio",
        "MarketCapitalization": "market_capitalization",
        "EPS": "basic_eps",
        "DilutedEPSTTM": "diluted_eps",
        "RevenueTTM": "total_revenue",
        "OperatingMarginTTM": "operating_revenue",  # or "operating_income"
        "GrossProfitTTM": "gross_profit",
        "ProfitMargin": "profit_margin",
    }

    @classmethod
    def from_ticker(cls, ticker: str) -> List["AlphaVantageFinancialMetrics"]:
        company_overview, _ = cls.fundamentals.get_company_overview(ticker)
        return AlphaVantageFinancialMetrics.from_json(company_overview)  # type: ignore


class AlphaVantageBalanceSheet(AlphaVantageBaseFinancials, BalanceSheet):
    __alias__ = {
        "symbol": "symbol",
        "fiscalDateEnding": "date",
        "totalAssets": "total_assets",
        "totalCurrentAssets": "total_current_assets",
        "cashAndCashEquivalentsAtCarryingValue": "cash_and_cash_equivalents_at_carrying_value",
        "cashAndShortTermInvestments": "cash_and_short_term_investments",
        "inventory": "inventory",
        "currentNetReceivables": "current_net_receivables",
        "totalNonCurrentAssets": "total_non_current_assets",
        "propertyPlantEquipment": "property_plant_equipment",
        "accumulatedDepreciationAmortizationPPE": "accumulated_depreciation_amortization_ppe",
        "otherCurrentAssets": "other_current_assets",
        "otherNonCurrentAssets": "other_non_current_assets",
        "totalLiabilities": "total_liabilities",
        "totalCurrentLiabilities": "total_current_liabilities",
        "currentAccountsPayable": "current_accounts_payable",
        "currentDebt": "current_debt",
        "totalNonCurrentLiabilities": "total_non_current_liabilities",
        "capitalLeaseObligations": "capital_lease_obligations",
        "longTermDebt": "long_term_debt",
        "shortLongTermDebtTotal": "short_long_term_debt_total",
        "otherCurrentLiabilities": "other_current_liabilities",
        "otherNonCurrentLiabilities": "other_non_current_liabilities",
        "totalShareholderEquity": "total_shareholder_equity",
        "treasuryStock": "treasury_stock",
        "retainedEarnings": "retained_earnings",
        "commonStock": "common_stock",
        "commonStockSharesOutstanding": "common_stock_shares_outstanding",
    }

    @classmethod
    def from_ticker(cls, ticker: str) -> List["AlphaVantageBalanceSheet"]:
        data_annual, _ = cls.fundamentals.get_balance_sheet_annual(ticker)
        data_quarterly, _ = cls.fundamentals.get_balance_sheet_quarterly(ticker)
        data_to_add = data_quarterly[
            ~data_quarterly["fiscalDateEnding"].isin(data_annual["fiscalDateEnding"])
        ]
        data_combined = pd.concat([data_annual, data_to_add], ignore_index=True)
        return AlphaVantageBalanceSheet.from_dataframe(ticker, data_combined)  # type: ignore


class AlphaVantageCashFlow(AlphaVantageBaseFinancials, CashFlow):
    __alias__ = {
        "symbol": "symbol",
        "fiscalDateEnding": "date",
        "operatingCashflow": "operating_cash_flow",
        "changeInOperatingLiabilities": "change_in_operating_liabilities",
        "changeInOperatingAssets": "change_in_other_working_capital",
        "changeInReceivables": "change_in_receivables",
        "changeInInventory": "change_in_inventory",
        "depreciationDepletionAndAmortization": "depreciation_amortization_depletion",
        "capitalExpenditures": "capital_expenditure",
        "cashflowFromInvestment": "cash_flow_from_investing_activities",
        "cashflowFromFinancing": "financing_cash_flow",
        "paymentsForRepurchaseOfCommonStock": "repurchase_of_capital_stock",
        "dividendPayout": "cash_dividends_paid",
        "dividendPayoutCommonStock": "common_stock_dividend_paid",
        "proceedsFromIssuanceOfCommonStock": "proceeds_from_issuance_of_common_stock",
        "changeInCashAndCashEquivalents": "changes_in_cash",
        "netIncome": "net_income_from_continuing_operations",
    }

    @classmethod
    def from_ticker(cls, ticker: str) -> List["AlphaVantageCashFlow"]:
        data, _ = cls.fundamentals.get_cash_flow_annual(ticker)
        return AlphaVantageCashFlow.from_dataframe(ticker, data)  # type: ignore


class AlphaVantageCandleStick(AlphaVantageBase, CandleStick):
    __alias__ = {
        "1. open": "open",
        "2. high": "high",
        "3. low": "low",
        "4. close": "close",
        "5. volume": "volume",
        "2. Symbol": "symbol",
    }

    @classmethod
    def from_ticker(cls, ticker: str, type: str) -> List["CandleStick"]:
        type = "full" if type == "full" else "compact"
        time_series, metadata = cls.timeseries.get_daily(ticker, outputsize=type)

        return [
            cast(CandleStick, AlphaVantageCandleStick(**(v | {"date": k} | metadata)))
            for k, v in time_series.items()
        ]


class AlphaVantageSource(AbstractSource):
    def read_assets(self, filters: Optional[List[str]] = None) -> Assets:
        equities = AlphaVantageEquity.from_tickers(filters)
        return Assets(equities=equities)

    def read_financials(self, ticker: str) -> Financials:
        return Financials(
            financial_metrics=[AlphaVantageFinancialMetrics.from_ticker(ticker)],
            balance_sheets=AlphaVantageBalanceSheet.from_ticker(ticker),
            cash_flows=AlphaVantageCashFlow.from_ticker(ticker),
        )

    def read_series(self, ticker: str, type: str) -> List[CandleStick]:
        return AlphaVantageCandleStick.from_ticker(ticker, type)
