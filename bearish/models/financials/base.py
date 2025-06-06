import logging
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Type, Sequence

import pandas as pd
from pydantic import BaseModel, Field, create_model

from bearish.models.base import Ticker, DataSourceBase
from bearish.models.financials.balance_sheet import BalanceSheet, QuarterlyBalanceSheet
from bearish.models.financials.cash_flow import CashFlow, QuarterlyCashFlow
from bearish.models.financials.earnings_date import EarningsDate
from bearish.models.financials.metrics import (
    FinancialMetrics,
    QuarterlyFinancialMetrics,
)
from bearish.models.query.query import AssetQuery, Symbols

if TYPE_CHECKING:
    from bearish.interface.interface import BearishDbBase
logger = logging.getLogger(__name__)

QUARTERLY = "quarterly"


def _load_data(
    data: Sequence[DataSourceBase], symbol: str, class_: Type[DataSourceBase]
) -> pd.DataFrame:
    try:
        records = pd.DataFrame.from_records(
            [f.model_dump() for f in data if f.symbol == symbol]
        )
        return records.set_index("date").sort_index()
    except Exception as e:
        logger.warning(f"Failed to load data from {symbol}: {e}")
        columns = list(class_.model_fields)
        return pd.DataFrame(columns=columns).sort_index()


def _compute_growth(series: pd.Series) -> bool:  # type: ignore
    if series.empty:
        return False
    return all(series.pct_change(fill_method=None).dropna() > 0)


def _all_positive(series: pd.Series) -> bool:  # type: ignore
    if series.empty:
        return False
    return all(series.dropna() > 0)


def _get_last(data: pd.Series) -> Optional[float]:  # type: ignore
    return data.iloc[-1] if not data.empty else None


def _abs(data: pd.Series) -> pd.Series:  # type: ignore
    try:
        return abs(data)
    except Exception as e:
        logger.warning(f"Failed to compute absolute value: {e}")
        return data


class BaseFundamentalAnalysis(BaseModel):
    positive_free_cash_flow: Optional[float] = None
    growing_operating_cash_flow: Optional[float] = None
    operating_cash_flow_is_higher_than_net_income: Optional[float] = None
    mean_capex_ratio: Optional[float] = None
    max_capex_ratio: Optional[float] = None
    min_capex_ratio: Optional[float] = None
    mean_dividend_payout_ratio: Optional[float] = None
    max_dividend_payout_ratio: Optional[float] = None
    min_dividend_payout_ratio: Optional[float] = None
    positive_net_income: Optional[float] = None
    positive_operating_income: Optional[float] = None
    growing_net_income: Optional[float] = None
    growing_operating_income: Optional[float] = None
    positive_diluted_eps: Optional[float] = None
    positive_basic_eps: Optional[float] = None
    growing_basic_eps: Optional[float] = None
    growing_diluted_eps: Optional[float] = None
    positive_debt_to_equity: Optional[float] = None
    positive_return_on_assets: Optional[float] = None
    positive_return_on_equity: Optional[float] = None
    earning_per_share: Optional[float] = None

    def is_empty(self) -> bool:
        return all(getattr(self, field) is None for field in self.model_fields)

    @classmethod
    def from_financials(
        cls, financials: "Financials", ticker: Ticker
    ) -> "BaseFundamentalAnalysis":
        return cls._from_financials(
            balance_sheets=financials.balance_sheets,
            financial_metrics=financials.financial_metrics,
            cash_flows=financials.cash_flows,
            ticker=ticker,
        )

    @classmethod
    def _from_financials(
        cls,
        balance_sheets: List[BalanceSheet] | List[QuarterlyBalanceSheet],
        financial_metrics: List[FinancialMetrics] | List[QuarterlyFinancialMetrics],
        cash_flows: List[CashFlow] | List[QuarterlyCashFlow],
        ticker: Ticker,
    ) -> "BaseFundamentalAnalysis":
        try:
            symbol = ticker.symbol

            balance_sheet = _load_data(balance_sheets, symbol, BalanceSheet)
            financial = _load_data(financial_metrics, symbol, FinancialMetrics)
            cash_flow = _load_data(cash_flows, symbol, CashFlow)

            # Debt-to-equity
            debt_to_equity = (
                balance_sheet.total_liabilities / balance_sheet.total_shareholder_equity
            ).dropna()
            positive_debt_to_equity = _all_positive(debt_to_equity)

            # Add relevant balance sheet data to financials
            financial["total_shareholder_equity"] = balance_sheet[
                "total_shareholder_equity"
            ]
            financial["common_stock_shares_outstanding"] = balance_sheet[
                "common_stock_shares_outstanding"
            ]

            # EPS and income checks
            earning_per_share = _get_last(
                (
                    financial.net_income / financial.common_stock_shares_outstanding
                ).dropna()
            )
            positive_net_income = _all_positive(financial.net_income)
            positive_operating_income = _all_positive(financial.operating_income)
            growing_net_income = _compute_growth(financial.net_income)
            growing_operating_income = _compute_growth(financial.operating_income)
            positive_diluted_eps = _all_positive(financial.diluted_eps)
            positive_basic_eps = _all_positive(financial.basic_eps)
            growing_basic_eps = _compute_growth(financial.basic_eps)
            growing_diluted_eps = _compute_growth(financial.diluted_eps)

            # Profitability ratios
            return_on_equity = (
                financial.net_income * 100 / financial.total_shareholder_equity
            ).dropna()
            return_on_assets = (
                financial.net_income * 100 / balance_sheet.total_assets
            ).dropna()
            positive_return_on_assets = _all_positive(return_on_assets)
            positive_return_on_equity = _all_positive(return_on_equity)
            # Cash flow analysis
            cash_flow["net_income"] = financial["net_income"]
            free_cash_flow = (
                cash_flow["operating_cash_flow"] - cash_flow["capital_expenditure"]
            )
            positive_free_cash_flow = _all_positive(free_cash_flow)
            growing_operating_cash_flow = _compute_growth(
                cash_flow["operating_cash_flow"]
            )
            operating_income_net_income = cash_flow[
                ["operating_cash_flow", "net_income"]
            ].dropna()
            operating_cash_flow_is_higher_than_net_income = all(
                operating_income_net_income["operating_cash_flow"]
                >= operating_income_net_income["net_income"]
            )
            cash_flow["capex_ratio"] = (
                cash_flow["capital_expenditure"] / cash_flow["operating_cash_flow"]
            ).dropna()
            mean_capex_ratio = cash_flow["capex_ratio"].mean()
            max_capex_ratio = cash_flow["capex_ratio"].max()
            min_capex_ratio = cash_flow["capex_ratio"].min()
            dividend_payout_ratio = (
                _abs(cash_flow["cash_dividends_paid"]) / free_cash_flow
            ).dropna()
            mean_dividend_payout_ratio = dividend_payout_ratio.mean()
            max_dividend_payout_ratio = dividend_payout_ratio.max()
            min_dividend_payout_ratio = dividend_payout_ratio.min()

            return cls(
                earning_per_share=earning_per_share,
                positive_debt_to_equity=positive_debt_to_equity,
                positive_return_on_assets=positive_return_on_assets,
                positive_return_on_equity=positive_return_on_equity,
                growing_net_income=growing_net_income,
                growing_operating_income=growing_operating_income,
                positive_diluted_eps=positive_diluted_eps,
                positive_basic_eps=positive_basic_eps,
                growing_basic_eps=growing_basic_eps,
                growing_diluted_eps=growing_diluted_eps,
                positive_net_income=positive_net_income,
                positive_operating_income=positive_operating_income,
                positive_free_cash_flow=positive_free_cash_flow,
                growing_operating_cash_flow=growing_operating_cash_flow,
                operating_cash_flow_is_higher_than_net_income=operating_cash_flow_is_higher_than_net_income,
                mean_capex_ratio=mean_capex_ratio,
                max_capex_ratio=max_capex_ratio,
                min_capex_ratio=min_capex_ratio,
                mean_dividend_payout_ratio=mean_dividend_payout_ratio,
                max_dividend_payout_ratio=max_dividend_payout_ratio,
                min_dividend_payout_ratio=min_dividend_payout_ratio,
            )
        except Exception as e:
            logger.error(
                f"Failed to compute fundamental analysis for {ticker}: {e}",
                exc_info=True,
            )
            return cls()


class YearlyFundamentalAnalysis(BaseFundamentalAnalysis): ...


fields_with_prefix = {
    f"{QUARTERLY}_{name}": (Optional[float], Field(default=None))
    for name in BaseFundamentalAnalysis.model_fields
}

# Create the new model
BaseQuarterlyFundamentalAnalysis = create_model(  # type: ignore
    "BaseQuarterlyFundamentalAnalysis", **fields_with_prefix
)


class QuarterlyFundamentalAnalysis(BaseQuarterlyFundamentalAnalysis):  # type: ignore

    @classmethod
    def from_quarterly_financials(
        cls, financials: "Financials", ticker: Ticker
    ) -> "QuarterlyFundamentalAnalysis":
        base_financial_analisys = BaseFundamentalAnalysis._from_financials(
            balance_sheets=financials.quarterly_balance_sheets,
            financial_metrics=financials.quarterly_financial_metrics,
            cash_flows=financials.quarterly_cash_flows,
            ticker=ticker,
        )
        return cls.model_validate({f"{QUARTERLY}_{k}": v for k, v in base_financial_analisys.model_dump().items()})  # type: ignore


class FundamentalAnalysis(YearlyFundamentalAnalysis, QuarterlyFundamentalAnalysis): ...


class Financials(BaseModel):
    financial_metrics: List[FinancialMetrics] = Field(default_factory=list)
    balance_sheets: List[BalanceSheet] = Field(default_factory=list)
    cash_flows: List[CashFlow] = Field(default_factory=list)
    quarterly_financial_metrics: List[QuarterlyFinancialMetrics] = Field(
        default_factory=list
    )
    quarterly_balance_sheets: List[QuarterlyBalanceSheet] = Field(default_factory=list)
    quarterly_cash_flows: List[QuarterlyCashFlow] = Field(default_factory=list)
    earnings_date: List[EarningsDate] = Field(default_factory=list)

    def add(self, financials: "Financials") -> None:
        self.financial_metrics.extend(financials.financial_metrics)
        self.balance_sheets.extend(financials.balance_sheets)
        self.cash_flows.extend(financials.cash_flows)
        self.quarterly_financial_metrics.extend(financials.quarterly_financial_metrics)
        self.quarterly_balance_sheets.extend(financials.quarterly_balance_sheets)
        self.quarterly_cash_flows.extend(financials.quarterly_cash_flows)
        self.earnings_date.extend(financials.earnings_date)

    def is_empty(self) -> bool:
        return not any(
            [
                self.financial_metrics,
                self.balance_sheets,
                self.cash_flows,
                self.quarterly_financial_metrics,
                self.quarterly_balance_sheets,
                self.quarterly_cash_flows,
                self.earnings_date,
            ]
        )

    def _compute_growth(self, data: pd.DataFrame, field: str) -> Dict[str, Any]:
        data[f"{field}_growth"] = data[field].pct_change() * 100
        return {
            f"{field}_growth_{i}": value
            for i, value in enumerate(
                data[f"{field}_growth"].sort_index(ascending=False).tolist()
            )
        }

    def fundamental_analysis(self, ticker: Ticker) -> FundamentalAnalysis:
        yearly_analysis = YearlyFundamentalAnalysis.from_financials(
            financials=self, ticker=ticker
        )
        quarterly_analysis = QuarterlyFundamentalAnalysis.from_quarterly_financials(
            financials=self, ticker=ticker
        )
        return FundamentalAnalysis.model_validate(
            yearly_analysis.model_dump() | quarterly_analysis.model_dump()
        )

    @classmethod
    def from_ticker(cls, bearish_db: "BearishDbBase", ticker: Ticker) -> "Financials":
        return bearish_db.read_financials(
            AssetQuery(symbols=Symbols(equities=[ticker]))  # type: ignore
        )


class ManyFinancials(BaseModel):
    financials: List[Financials] = Field(default_factory=list)

    def get(self, attribute: str) -> List[DataSourceBase]:
        return [
            a
            for financial in self.financials
            if hasattr(financial, attribute)
            for a in getattr(financial, attribute)
        ]
