from typing import List

from bearish.models.financials import FinancialMetrics, BalanceSheet, CashFlow
from bearish.sources.base import BaseFinancialsComponentSource


class AlphaVantageBase(BaseFinancialsComponentSource):
    __source__ = "AlphaVantage"

    @classmethod
    def from_ticker(cls, ticker: str) -> List["AlphaVantageBase"]:
        ...

    @classmethod
    def from_json(cls, data) -> "AlphaVantageBase":
        return cls.model_validate(data)

    @classmethod
    def from_dataframe(cls, ticker, data) -> List["AlphaVantageBase"]:
        return [
            cls.model_validate((bs | {"symbol": ticker}))
            for bs in data.to_dict(orient="records")
        ]


class AlphaVantageFinancialMetrics(AlphaVantageBase, FinancialMetrics):
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


class AlphaVantageBalanceSheet(AlphaVantageBase, BalanceSheet):
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


class AlphaVantageCashFlow(AlphaVantageBase, CashFlow):
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
