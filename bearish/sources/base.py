import abc
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from bearish.models.base import Equity, Crypto, Etf, Currency
from bearish.models.financials import FinancialMetrics, BalanceSheet, CashFlow


class BaseFinancialsComponentSource(abc.ABC, BaseModel):
    @classmethod
    @abc.abstractmethod
    def from_ticker(cls, ticker: str) -> List["BaseFinancialsComponentSource"]:
        ...


class BaseFinancialsSource(abc.ABC, BaseModel):
    @abc.abstractmethod
    def financial_metrics(self, ticker: str) -> List[FinancialMetrics]:
        ...

    @abc.abstractmethod
    def balance_sheets(self, ticker: str) -> List[BalanceSheet]:
        ...

    @abc.abstractmethod
    def cash_flows(self, ticker: str) -> List[CashFlow]:
        ...


class AbstractAssetsSource(abc.ABC):
    @abc.abstractmethod
    def equities(self, filters: Optional[List[str]] = None) -> List[Equity]:
        ...

    @abc.abstractmethod
    def cryptos(self, filters: Optional[List[str]] = None) -> List[Crypto]:
        ...

    @abc.abstractmethod
    def etfs(self, filters: Optional[List[str]] = None) -> List[Etf]:
        ...

    @abc.abstractmethod
    def currencies(self, filters: Optional[List[str]] = None) -> List[Currency]:
        ...


class AbstractSource(abc.ABC, BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    assets: AbstractAssetsSource
    financials: BaseFinancialsSource

    def update_financials(self, ticker: str):
        financial_metrics = self.financials.financial_metrics(ticker)
        balance_sheets = self.financials.balance_sheets(ticker)
        cash_flows = self.financials.cash_flows(ticker)
        a = 12
