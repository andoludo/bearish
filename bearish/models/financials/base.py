import logging
from typing import List, Optional, Dict, Any, TYPE_CHECKING

import pandas as pd
from pydantic import BaseModel, Field


from bearish.models.base import Ticker
from bearish.models.financials.balance_sheet import BalanceSheet
from bearish.models.financials.cash_flow import CashFlow
from bearish.models.financials.earnings_date import EarningsDate
from bearish.models.financials.metrics import FinancialMetrics
from bearish.models.query.query import AssetQuery, Symbols

if TYPE_CHECKING:
    from bearish.interface.interface import BearishDbBase
logger = logging.getLogger(__name__)


class FundamentalAnalysis(BaseModel):
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


class Financials(BaseModel):
    financial_metrics: List[FinancialMetrics] = Field(default_factory=list)
    balance_sheets: List[BalanceSheet] = Field(default_factory=list)
    cash_flows: List[CashFlow] = Field(default_factory=list)
    earnings_date: List[EarningsDate] = Field(default_factory=list)

    def add(self, financials: "Financials") -> None:
        self.financial_metrics.extend(financials.financial_metrics)
        self.balance_sheets.extend(financials.balance_sheets)
        self.cash_flows.extend(financials.cash_flows)
        self.earnings_date.extend(financials.earnings_date)

    def is_empty(self) -> bool:
        return not any(
            [
                self.financial_metrics,
                self.balance_sheets,
                self.cash_flows,
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
        try:
            balance_sheet = pd.DataFrame.from_records(
                [
                    f.model_dump()
                    for f in self.balance_sheets
                    if f.symbol == ticker.symbol
                ]
            )
            balance_sheet = balance_sheet.set_index("date", inplace=False)
            balance_sheet = balance_sheet.sort_index(inplace=False)
            debt_to_equity = (
                balance_sheet.total_liabilities / balance_sheet.total_shareholder_equity
            ).dropna()
            positive_debt_to_equity = all(debt_to_equity > 0)
            financial = pd.DataFrame.from_records(
                [
                    f.model_dump()
                    for f in self.financial_metrics
                    if f.symbol == ticker.symbol
                ]
            )
            financial = financial.set_index("date", inplace=False)
            financial = financial.sort_index(inplace=False)
            financial["total_shareholder_equity"] = balance_sheet[
                "total_shareholder_equity"
            ]
            financial["common_stock_shares_outstanding"] = balance_sheet[
                "common_stock_shares_outstanding"
            ]
            earning_per_share = (
                (financial.net_income / financial.common_stock_shares_outstanding)
                .dropna()
                .iloc[-1]
            )
            positive_net_income = all(financial.net_income.dropna() > 0)
            positive_operating_income = all(financial.operating_income.dropna() > 0)
            growing_net_income = all(
                financial.net_income.pct_change(fill_method=None).dropna() > 0  # type: ignore
            )
            growing_operating_income = all(
                financial.operating_income.pct_change(fill_method=None).dropna() > 0  # type: ignore
            )
            positive_diluted_eps = all(financial.diluted_eps.dropna() > 0)
            positive_basic_eps = all(financial.basic_eps.dropna() > 0)
            growing_basic_eps = all(
                financial.basic_eps.pct_change(fill_method=None).dropna() > 0  # type: ignore
            )
            growing_diluted_eps = all(
                financial.diluted_eps.pct_change(fill_method=None).dropna() > 0  # type: ignore
            )
            return_on_equity = (
                financial.net_income * 100 / financial.total_shareholder_equity
            ).dropna()
            return_on_assets = (
                financial.net_income * 100 / balance_sheet.total_assets
            ).dropna()
            positive_return_on_assets = all(return_on_assets > 0)
            positive_return_on_equity = all(return_on_equity > 0)
            cash_flow = pd.DataFrame.from_records(
                [f.model_dump() for f in self.cash_flows if f.symbol == ticker.symbol]
            )
            cash_flow = cash_flow.set_index("date", inplace=False)
            cash_flow = cash_flow.sort_index(inplace=False)
            cash_flow["net_income"] = financial["net_income"]
            free_cash_flow = (
                cash_flow["operating_cash_flow"] - cash_flow["capital_expenditure"]
            )
            positive_free_cash_flow = all(free_cash_flow.dropna() > 0)
            growing_operating_cash_flow = all(
                cash_flow["operating_cash_flow"].pct_change(fill_method=None).dropna()  # type: ignore
                > 0
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

            try:
                dividend_payout_ratio = (
                    abs(cash_flow["cash_dividends_paid"]) / free_cash_flow
                ).dropna()
                mean_dividend_payout_ratio = dividend_payout_ratio.mean()
                max_dividend_payout_ratio = dividend_payout_ratio.max()
                min_dividend_payout_ratio = dividend_payout_ratio.min()
            except Exception as e:
                logger.warning(
                    f"Cannot compute dividend for {ticker.symbol}: {e}", exc_info=True
                )
                mean_dividend_payout_ratio = None
                max_dividend_payout_ratio = None
                min_dividend_payout_ratio = None
            return FundamentalAnalysis(
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
            logger.warning(f"Error for {ticker.symbol}: {e}", exc_info=True)
            return FundamentalAnalysis()

    @classmethod
    def from_ticker(cls, bearish_db: "BearishDbBase", ticker: Ticker) -> "Financials":
        return bearish_db.read_financials(
            AssetQuery(symbols=Symbols(equities=[ticker]))  # type: ignore
        )
