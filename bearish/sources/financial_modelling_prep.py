import logging
from typing import Optional, List, Any, ClassVar, Dict

import requests  # type: ignore
from pydantic import Field

from bearish.exceptions import InvalidApiKeyError
from bearish.exchanges.exchanges import Countries
from bearish.models.assets.assets import Assets
from bearish.models.assets.equity import Equity
from bearish.models.assets.etfs import Etf
from bearish.models.base import SourceBase
from bearish.models.financials.balance_sheet import BalanceSheet
from bearish.models.financials.base import Financials
from bearish.models.financials.cash_flow import CashFlow
from bearish.models.financials.metrics import FinancialMetrics
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery
from bearish.sources.base import AbstractSource, ApiUsage
from bearish.types import Sources, SeriesLength
from bearish.utils.utils import get_start_date

logger = logging.getLogger(__name__)

API_URL = "https://financialmodelingprep.com/api/v3/"


def compose_url(  # noqa: PLR0913
    api_url: str,
    endpoint: str,
    api_key: str,
    ticker: str,
    period: Optional[str] = None,
    from_: Optional[str] = None,
) -> str:
    period_ = f"?period={period}" if period else ""
    from__ = f"?from={from_}" if from_ else ""
    if from_ and period:
        raise NotImplementedError("Cannot use both period and from_")
    separator = "&" if (period or from_) else "?"
    return f"{api_url}{endpoint}/{ticker}{period_}{from__}{separator}apikey={api_key}"


def read_api(  # noqa: PLR0913
    api_url: str,
    endpoint: str,
    api_key: str,
    ticker: str,
    period: Optional[str] = None,
    from_: Optional[str] = None,
) -> Any:
    request_response = requests.get(
        compose_url(api_url, endpoint, api_key, ticker, period=period, from_=from_),
        timeout=10,
    )
    response_json = request_response.json()
    if isinstance(response_json, dict) and response_json.get("Error Message"):
        logger.error(f"Error reading {ticker}: {response_json['Error Message']}")
        raise InvalidApiKeyError(response_json["Error Message"])
    if isinstance(response_json, list):
        for response_json_ in response_json:
            if response_json_.get("Error Message"):
                logger.error(
                    f"Error reading {ticker}: {response_json_['Error Message']}"
                )
                raise InvalidApiKeyError(response_json_["Error Message"])
    return response_json


class FmpSourceBase(SourceBase):
    __source__: Sources = "FMP"


class FmpAssetsSourceBase(SourceBase):
    __source__: Sources = "FMPAssets"


class FmpAssetsEquity(FmpAssetsSourceBase, Equity):
    __alias__: ClassVar[Dict[str, str]] = {
        "symbol": "symbol",
        "name": "name",
        "exchange": "exchange",
        "exchangeShortName": "market",
    }


class FmpAssetsEtf(FmpAssetsSourceBase, Etf):
    __alias__: ClassVar[Dict[str, str]] = {
        "symbol": "symbol",
        "name": "name",
        "exchange": "exchange",
        "exchangeShortName": "market",
    }


class FmpEquity(FmpSourceBase, Equity):
    __alias__: ClassVar[Dict[str, str]] = {
        "symbol": "symbol",  # Ticker symbol
        "lastDiv": "dividend_rate",  # Last dividend rate
        "companyName": "name",  # Company name
        "currency": "currency",  # Currency
        "isin": "isin",  # ISIN
        "cusip": "cusip",  # CUSIP
        "exchange": "exchange",  # Exchange name
        "exchangeShortName": "market",  # Abbreviated market name
        "industry": "industry",  # Industry
        "website": "website",  # Company website
        "description": "summary",  # Company summary
        "sector": "sector",  # Sector
        "country": "country",  # Country
        "city": "city",  # City
        "state": "state",  # State
        "zip": "zipcode",  # ZIP code
        "name": "name",  # Company name
        "marketCap": "market_capitalization",  # Market capitalization
        "eps": "trailing_earnings_per_share",  # Trailing EPS
        "pe": "trailing_price_to_earnings",  # Trailing P/E ratio
        "sharesOutstanding": "shares_outstanding",  # Outstanding shares
        "dividendYielTTM": "dividend_yield",  # TTM dividend yield
        "peRatioTTM": "trailing_price_to_earnings",  # Trailing P/E ratio
        "pegRatioTTM": "trailing_peg_ratio",  # Trailing PEG ratio
        "currentRatioTTM": "current_ratio",  # Current ratio
        "quickRatioTTM": "quick_ratio",  # Quick ratio
        "grossProfitMarginTTM": "gross_margins",  # Gross margins
        "operatingProfitMarginTTM": "operating_margins",  # Operating margins
        "returnOnAssetsTTM": "return_on_assets",  # ROA
        "returnOnEquityTTM": "return_on_equity",  # ROE
    }

    @classmethod
    def from_tickers(cls, tickers: List[str]) -> List["FmpEquity"]:
        tickers_ = []
        for ticker in tickers:
            try:
                profile = read_api(API_URL, "profile", cls.__api_key__, ticker)
                quote = read_api(API_URL, "quote", cls.__api_key__, ticker)
                ratio_ttm = read_api(API_URL, "ratios-ttm", cls.__api_key__, ticker)
                key_metrics = read_api(
                    API_URL, "key-metrics-ttm", cls.__api_key__, ticker
                )
                datas = [*profile, *quote, *ratio_ttm, *key_metrics]
                data = {k: v for data in datas for k, v in data.items()}
                tickers_.append(cls.model_validate(data))
            except InvalidApiKeyError as e:  # noqa: PERF203
                logger.warning(f"Error reading {ticker}: {e}")
                break
            except Exception as e:
                logger.error(f"Error reading {ticker}: {e}")
                continue
        return tickers_


class FmpFinancialMetrics(FmpSourceBase, FinancialMetrics):
    __alias__: ClassVar[Dict[str, str]] = {
        "peRatioTTM": "pe_ratio",
        "marketCapTTM": "market_capitalization",
        "netProfitMarginTTM": "profit_margin",
        "netIncomePerShareTTM": "basic_eps",
        "revenuePerShareTTM": "total_revenue",
        "grossProfitMarginTTM": "gross_profit",
    }


class FmpBalanceSheet(FmpSourceBase, BalanceSheet):
    __alias__: ClassVar[Dict[str, str]] = {
        "date": "date",
        "symbol": "symbol",
        "cashAndCashEquivalents": "cash_and_cash_equivalents_at_carrying_value",
        "cashAndShortTermInvestments": "cash_and_short_term_investments",
        "netReceivables": "current_net_receivables",
        "inventory": "inventory",
        "otherCurrentAssets": "other_current_assets",
        "totalCurrentAssets": "total_current_assets",
        "propertyPlantEquipmentNet": "property_plant_equipment",
        "totalAssets": "total_assets",
        "totalCurrentLiabilities": "total_current_liabilities",
        "otherCurrentLiabilities": "other_current_liabilities",
        "shortTermDebt": "current_debt",
        "accountPayables": "current_accounts_payable",
        "totalNonCurrentLiabilities": "total_non_current_liabilities",
        "otherNonCurrentLiabilities": "other_non_current_liabilities",
        "longTermDebt": "long_term_debt",
        "totalLiabilities": "total_liabilities",
        "retainedEarnings": "retained_earnings",
        "commonStock": "common_stock",
        "totalStockholdersEquity": "total_shareholder_equity",
        "capitalLeaseObligations": "capital_lease_obligations",
    }


class FmpCashFlow(FmpSourceBase, CashFlow):
    __alias__: ClassVar[Dict[str, str]] = {
        "date": "date",
        "symbol": "symbol",
        "netIncome": "net_income_from_continuing_operations",
        "depreciationAndAmortization": "depreciation_amortization_depletion",
        "changeInWorkingCapital": "change_in_working_capital",
        "accountsReceivables": "change_in_receivables",
        "inventory": "change_in_inventory",
        "accountsPayables": "change_in_operating_liabilities",
        "otherWorkingCapital": "change_in_other_working_capital",
        "netCashProvidedByOperatingActivities": "operating_cash_flow",
        "investmentsInPropertyPlantAndEquipment": "capital_expenditure",
        "netCashUsedForInvestingActivites": "cash_flow_from_investing_activities",
        "commonStockIssued": "proceeds_from_issuance_of_common_stock",
        "commonStockRepurchased": "repurchase_of_capital_stock",
        "dividendsPaid": "cash_dividends_paid",
        "netCashUsedProvidedByFinancingActivities": "financing_cash_flow",
        "netChangeInCash": "changes_in_cash",
    }


class FmpPrice(FmpSourceBase, Price):
    __alias__: ClassVar[Dict[str, str]] = {
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    }


class FmpSource(FmpSourceBase, AbstractSource):
    countries: List[Countries] = ["US"]  # noqa: RUF012
    api_usage: ApiUsage = ApiUsage(calls_limit=220)

    def set_api_key(self, api_key: str) -> None:
        FmpSourceBase.__api_key__ = api_key

    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        if query is None:
            return Assets()

        if query.symbols.empty():
            return Assets()
        equities = FmpEquity.from_tickers(query.symbols.equities_symbols())
        return Assets(equities=equities)

    def _read_financials(self, tickers: List[str]) -> List[Financials]:
        financials = []
        for ticker in tickers:
            balance_sheet_statement = read_api(
                API_URL,
                "balance-sheet-statement",
                self.__api_key__,
                ticker,
                period="annual",
            )
            cash_flow_statement = read_api(
                API_URL,
                "cash-flow-statement",
                self.__api_key__,
                ticker,
                period="annual",
            )
            ratio_ttm = read_api(API_URL, "ratios-ttm", self.__api_key__, ticker)
            key_metrics = read_api(API_URL, "key-metrics-ttm", self.__api_key__, ticker)
            self.api_usage.add_api_calls(4)
            datas = [*ratio_ttm, *key_metrics]
            financial_metrics = {k: v for data in datas for k, v in data.items()}
            financial_metrics.update({"symbol": ticker})
            financials.append(
                Financials(
                    financial_metrics=[
                        FmpFinancialMetrics.model_validate(financial_metrics)
                    ],
                    balance_sheets=[
                        FmpBalanceSheet.model_validate(balance_sheet_statement_)
                        for balance_sheet_statement_ in balance_sheet_statement
                    ],
                    cash_flows=[
                        FmpCashFlow.model_validate(cash_flow_statement_)
                        for cash_flow_statement_ in cash_flow_statement
                    ],
                )
            )
        return financials

    def _read_series(self, tickers: List[str], type: SeriesLength) -> List[FmpPrice]:  # type: ignore
        from_ = get_start_date(type)
        prices = []
        for ticker in tickers:
            historical_price = read_api(
                API_URL,
                "historical-price-full",
                self.__api_key__,
                ticker,
                period=None,
                from_=from_,
            )
            self.api_usage.add_api_calls(1)
            symbol = historical_price["symbol"]
            datas = historical_price["historical"]
            prices.extend(
                [FmpPrice.model_validate({**data, "symbol": symbol}) for data in datas]
            )
        return prices


class FmpAssetsSource(FmpAssetsSourceBase, AbstractSource):
    countries: List[Countries] = Field(default_factory=list)

    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        stocks = read_api(API_URL, "stock", self.__api_key__, "list")
        stocks = [s for s in stocks if s["type"] == "stock"]
        etfs = read_api(API_URL, "etf", self.__api_key__, "list")
        etfs = [s for s in etfs if s["type"] == "etf"]
        return Assets(
            equities=[FmpAssetsEquity.model_validate(stock) for stock in stocks],
            etfs=[FmpAssetsEtf.model_validate(etf) for etf in etfs],
        )

    def _read_financials(self, tickers: List[str]) -> List[Financials]:
        return [Financials()]

    def _read_series(self, tickers: List[str], type: SeriesLength) -> List[Price]:
        return []

    def set_api_key(self, api_key: str) -> None:
        FmpAssetsSourceBase.__api_key__ = api_key
