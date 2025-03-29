import logging
from typing import List, Annotated, Optional, Dict, Any, TYPE_CHECKING

import pandas as pd
from pydantic import BaseModel, Field, BeforeValidator


from bearish.models.base import Ticker
from bearish.models.financials.balance_sheet import BalanceSheet
from bearish.models.financials.cash_flow import CashFlow
from bearish.models.financials.earnings_date import EarningsDate
from bearish.models.financials.metrics import FinancialMetrics
from bearish.models.query.query import AssetQuery, Symbols
from bearish.utils.utils import to_float

if TYPE_CHECKING:
    from bearish.interface.interface import BearishDbBase
logger = logging.getLogger(__name__)


class FundamentalAnalysis(BaseModel):
    net_income_growth_0: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
        ),
    ]
    net_income_growth_1: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
        ),
    ]
    net_income_growth_2: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
        ),
    ]
    net_income_growth_3: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
        ),
    ]


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
            financial = pd.DataFrame.from_records(
                [
                    f.model_dump()
                    for f in self.financial_metrics
                    if f.symbol == ticker.symbol
                ]
            )
            financial = financial.set_index("date", inplace=False)
            financial = financial.sort_index(inplace=False)
            fundamental_analysis = {}
            for field in ["net_income"]:
                fundamental_analysis.update(self._compute_growth(financial, field))

            return FundamentalAnalysis(**fundamental_analysis)
        except Exception as e:
            logger.error(e)
            return FundamentalAnalysis()  # type: ignore

    @classmethod
    def from_ticker(cls, bearish_db: "BearishDbBase", ticker: Ticker) -> "Financials":
        return bearish_db.read_financials(
            AssetQuery(symbols=Symbols(equities=[ticker]))  # type: ignore
        )
