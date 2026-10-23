"""Financial statements from SEC XBRL "company facts" (primary source).

``https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`` holds every
us-gaap fact a filer ever tagged. This source maps a curated list of tags onto
the existing ``FinancialMetrics`` / ``BalanceSheet`` / ``CashFlow`` models,
annual (10-K) and quarterly (10-Q), and records ``filed_date`` from the filing
that first reported each period, which yfinance cannot provide.

US filers only; non-US tickers have no CIK and are skipped.
"""

import datetime
import logging
import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple, Type, TypeVar

import requests
from sec_cik_mapper import StockMapper  # type: ignore

from bearish.exchanges.exchanges import Countries
from bearish.models.assets.assets import Assets
from bearish.models.base import SourceBase
from bearish.models.financials.balance_sheet import BalanceSheet, QuarterlyBalanceSheet
from bearish.models.financials.base import Financials
from bearish.models.financials.cash_flow import CashFlow, QuarterlyCashFlow
from bearish.models.financials.metrics import FinancialMetrics, QuarterlyFinancialMetrics
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery
from bearish.sources.base import AbstractSource
from bearish.sources.edgar_filings import HEADERS, cik_for_symbol
from bearish.types import DELAY, SeriesLength, Sources

logger = logging.getLogger(__name__)

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
STATEMENT_FORMS = ("10-K", "10-K/A", "10-Q", "10-Q/A")
ANNUAL_DURATION = (350, 380)
QUARTER_DURATION = (80, 100)

# Ordered candidate tags per model field; the first tag with usable facts wins.
# Flow fields (income statement, cash flow) need a start/end duration,
# instant fields (balance sheet) a single end date.
METRICS_TAGS: Dict[str, Tuple[str, ...]] = {
    "total_revenue": (
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ),
    "operating_revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"),
    "cost_of_revenue": ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices"),
    "gross_profit": ("GrossProfit",),
    "total_expenses": ("CostsAndExpenses",),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"),
    "basic_eps": ("EarningsPerShareBasic", "EarningsPerShareBasicAndDiluted"),
    "diluted_eps": ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"),
    "tax_provision": ("IncomeTaxExpenseBenefit",),
    "ebitda": ("EarningsBeforeInterestTaxesDepreciationAndAmortization",),
    "interest_expense": ("InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"),
    "research_and_development": (
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    ),
    "selling_general_and_administrative": ("SellingGeneralAndAdministrativeExpense",),
    "diluted_average_shares": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
}
BALANCE_TAGS: Dict[str, Tuple[str, ...]] = {
    "total_assets": ("Assets",),
    "total_current_assets": ("AssetsCurrent",),
    "total_non_current_assets": ("AssetsNoncurrent",),
    "other_non_current_assets": ("OtherAssetsNoncurrent",),
    "other_current_assets": ("OtherAssetsCurrent",),
    "cash_and_cash_equivalents_at_carrying_value": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "cash_and_short_term_investments": ("CashCashEquivalentsAndShortTermInvestments",),
    "current_net_receivables": ("AccountsReceivableNetCurrent", "ReceivablesNetCurrent"),
    "inventory": ("InventoryNet",),
    "property_plant_equipment": ("PropertyPlantAndEquipmentNet",),
    "accumulated_depreciation_amortization_ppe": (
        "AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
    ),
    "total_liabilities": ("Liabilities",),
    "total_current_liabilities": ("LiabilitiesCurrent",),
    "total_non_current_liabilities": ("LiabilitiesNoncurrent",),
    "other_non_current_liabilities": ("OtherLiabilitiesNoncurrent",),
    "other_current_liabilities": ("OtherLiabilitiesCurrent",),
    "current_accounts_payable": ("AccountsPayableCurrent",),
    "current_debt": ("DebtCurrent", "LongTermDebtCurrent", "ShortTermBorrowings"),
    "long_term_debt": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "short_long_term_debt_total": ("LongTermDebt", "DebtLongtermAndShorttermCombinedAmount"),
    "capital_lease_obligations": ("FinanceLeaseLiabilityNoncurrent", "CapitalLeaseObligationsNoncurrent"),
    "total_shareholder_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "retained_earnings": ("RetainedEarningsAccumulatedDeficit",),
    "common_stock": ("CommonStockValue", "CommonStocksIncludingAdditionalPaidInCapital"),
    "treasury_stock": ("TreasuryStockValue", "TreasuryStockCommonValue"),
    "common_stock_shares_outstanding": ("CommonStockSharesOutstanding",),
}
CASH_FLOW_TAGS: Dict[str, Tuple[str, ...]] = {
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "cash_flow_from_investing_activities": (
        "NetCashProvidedByUsedInInvestingActivities",
        "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
    ),
    "financing_cash_flow": (
        "NetCashProvidedByUsedInFinancingActivities",
        "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
    ),
    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),
    "depreciation_amortization_depletion": (
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
    ),
    "repurchase_of_capital_stock": ("PaymentsForRepurchaseOfCommonStock",),
    "cash_dividends_paid": ("PaymentsOfDividends", "PaymentsOfDividendsCommonStock"),
    "common_stock_dividend_paid": ("PaymentsOfDividendsCommonStock", "PaymentsOfDividends"),
    "proceeds_from_issuance_of_common_stock": ("ProceedsFromIssuanceOfCommonStock",),
    "change_in_receivables": ("IncreaseDecreaseInAccountsReceivable", "IncreaseDecreaseInReceivables"),
    "change_in_inventory": ("IncreaseDecreaseInInventories",),
    "change_in_operating_liabilities": ("IncreaseDecreaseInOtherOperatingLiabilities",),
    "changes_in_cash": (
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
        "CashAndCashEquivalentsPeriodIncreaseDecrease",
    ),
    "net_income_from_continuing_operations": (
        "IncomeLossFromContinuingOperations",
        "IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest",
        "NetIncomeLoss",
    ),
    "stock_based_compensation": ("ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"),
}
# Fields whose magnitude is not USD.
SHARE_FIELDS = {"common_stock_shares_outstanding", "diluted_average_shares"}
PER_SHARE_FIELDS = {"basic_eps", "diluted_eps"}
# Cash-flow tags reported as positive outflows; the models follow yfinance's
# sign convention (outflows negative).
OUTFLOW_FIELDS = {
    "capital_expenditure",
    "repurchase_of_capital_stock",
    "cash_dividends_paid",
    "common_stock_dividend_paid",
}

PeriodKind = Literal["annual", "quarterly"]
StatementT = TypeVar("StatementT", bound=SourceBase)


class SecSourceBase(SourceBase):
    __source__: Sources = "SEC"


class SecFinancialMetrics(SecSourceBase, FinancialMetrics): ...


class SecQuarterlyFinancialMetrics(SecSourceBase, QuarterlyFinancialMetrics): ...


class SecBalanceSheet(SecSourceBase, BalanceSheet): ...


class SecQuarterlyBalanceSheet(SecSourceBase, QuarterlyBalanceSheet): ...


class SecCashFlow(SecSourceBase, CashFlow): ...


class SecQuarterlyCashFlow(SecSourceBase, QuarterlyCashFlow): ...


def _unit_for(field: str) -> str:
    if field in SHARE_FIELDS:
        return "shares"
    if field in PER_SHARE_FIELDS:
        return "USD/shares"
    return "USD"


def _duration_days(fact: Dict[str, Any]) -> Optional[int]:
    start = fact.get("start")
    if not start:
        return None
    return (datetime.date.fromisoformat(fact["end"]) - datetime.date.fromisoformat(start)).days


def _period_kind(fact: Dict[str, Any], instant: bool) -> Optional[PeriodKind]:
    """Classify a fact as an annual or quarterly data point, or neither.

    Instant facts (balance sheet) from a 10-K are both the fiscal-year value
    and the fourth-quarter value; 10-Q instants are quarterly only. Flow facts
    must span a full year (10-K) or a single quarter (10-Q): year-to-date
    columns in 10-Qs are dropped rather than differenced.
    """
    form = fact.get("form", "")
    if form not in STATEMENT_FORMS:
        return None
    is_annual_form = form.startswith("10-K")
    if instant:
        return "annual" if is_annual_form and fact.get("fp") == "FY" else "quarterly"
    duration = _duration_days(fact)
    if duration is None:
        return None
    if is_annual_form and fact.get("fp") == "FY" and ANNUAL_DURATION[0] <= duration <= ANNUAL_DURATION[1]:
        return "annual"
    if not is_annual_form and QUARTER_DURATION[0] <= duration <= QUARTER_DURATION[1]:
        return "quarterly"
    return None


def _select_facts(
    gaap: Dict[str, Any], candidates: Iterable[str], unit: str, instant: bool, kind: PeriodKind
) -> Dict[str, Tuple[float, str]]:
    """``{end: (value, filed)}`` for the first candidate tag that has facts of ``kind``.

    When a period appears in several filings (comparatives, amendments) the
    earliest filing wins: that is when the number became public, and it keeps
    ``filed_date`` honest for point-in-time use.
    """
    for tag in candidates:
        facts = gaap.get(tag, {}).get("units", {}).get(unit, [])
        selected: Dict[str, Tuple[float, str]] = {}
        for fact in facts:
            if _period_kind(fact, instant) != kind or fact.get("val") is None:
                continue
            end, filed = fact["end"], fact["filed"]
            if end not in selected or filed < selected[end][1]:
                selected[end] = (float(fact["val"]), filed)
        if selected:
            return selected
    return {}


def _build_rows(
    gaap: Dict[str, Any], tag_map: Dict[str, Tuple[str, ...]], instant: bool, kind: PeriodKind, symbol: str
) -> List[Dict[str, Any]]:
    by_end: Dict[str, Dict[str, Any]] = defaultdict(dict)
    filed_by_end: Dict[str, str] = {}
    for field, candidates in tag_map.items():
        for end, (value, filed) in _select_facts(gaap, candidates, _unit_for(field), instant, kind).items():
            by_end[end][field] = -value if field in OUTFLOW_FIELDS else value
            filed_by_end[end] = min(filed, filed_by_end.get(end, filed))
    return [
        {"symbol": symbol, "date": end, "filed_date": filed_by_end[end], **values}
        for end, values in sorted(by_end.items())
    ]


def _validate_rows(model: Type[StatementT], rows: List[Dict[str, Any]]) -> List[StatementT]:
    return [model.model_validate(row) for row in rows]


def parse_companyfacts(payload: Dict[str, Any], symbol: str) -> Financials:
    """Turn one companyfacts payload into annual and quarterly statements."""
    gaap = payload.get("facts", {}).get("us-gaap", {})
    if not gaap:
        return Financials()
    return Financials(
        financial_metrics=_validate_rows(SecFinancialMetrics, _build_rows(gaap, METRICS_TAGS, False, "annual", symbol)),
        quarterly_financial_metrics=_validate_rows(
            SecQuarterlyFinancialMetrics, _build_rows(gaap, METRICS_TAGS, False, "quarterly", symbol)
        ),
        balance_sheets=_validate_rows(SecBalanceSheet, _build_rows(gaap, BALANCE_TAGS, True, "annual", symbol)),
        quarterly_balance_sheets=_validate_rows(
            SecQuarterlyBalanceSheet, _build_rows(gaap, BALANCE_TAGS, True, "quarterly", symbol)
        ),
        cash_flows=_validate_rows(SecCashFlow, _build_rows(gaap, CASH_FLOW_TAGS, False, "annual", symbol)),
        quarterly_cash_flows=_validate_rows(
            SecQuarterlyCashFlow, _build_rows(gaap, CASH_FLOW_TAGS, False, "quarterly", symbol)
        ),
    )


def fetch_companyfacts(cik: str, timeout: int = 60) -> Dict[str, Any]:
    response = requests.get(COMPANYFACTS_URL.format(cik=cik), headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


class SecXbrlSource(SecSourceBase, AbstractSource):
    countries: List[Countries] = ["US"]  # noqa: RUF012
    delay: float = DELAY

    def set_api_key(self, api_key: Optional[str]) -> None: ...

    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        return Assets()

    def _read_series(self, tickers: List[str], type: SeriesLength) -> List[Price]:
        return []

    def _read_financials(self, tickers: List[str]) -> List[Financials]:
        mapper = StockMapper()
        financials: List[Financials] = []
        for symbol in tickers:
            cik = cik_for_symbol(symbol, mapper)
            if cik is None:
                logger.debug(f"No CIK for {symbol}; skipping SEC XBRL financials")
                continue
            try:
                parsed = parse_companyfacts(fetch_companyfacts(cik), symbol)
            except Exception as e:
                logger.error(f"Error reading SEC XBRL financials for {symbol}: {e}")
                continue
            if not parsed.is_empty():
                financials.append(parsed)
            time.sleep(self.delay)
        return financials
