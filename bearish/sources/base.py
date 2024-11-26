import abc
import logging
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, validate_call

from bearish.models.base import Equity, Crypto, Etf, Currency, CandleStick
from bearish.models.financials import FinancialMetrics, BalanceSheet, CashFlow

logger = logging.getLogger(__name__)


class Financials(BaseModel):
    financial_metrics: List[FinancialMetrics] = Field(default_factory=list)
    balance_sheets: List[BalanceSheet] = Field(default_factory=list)
    cash_flows: List[CashFlow] = Field(default_factory=list)

    def add(self, financials: "Financials") -> None:
        self.financial_metrics.extend(financials.financial_metrics)
        self.balance_sheets.extend(financials.balance_sheets)
        self.cash_flows.extend(financials.cash_flows)

    def is_empty(self) -> bool:
        return not any(
            [
                self.financial_metrics,
                self.balance_sheets,
                self.cash_flows,
            ]
        )


class Assets(BaseModel):
    equities: List[Equity] = Field(default_factory=list)
    cryptos: List[Crypto] = Field(default_factory=list)
    etfs: List[Etf] = Field(default_factory=list)
    currencies: List[Currency] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            [
                self.equities,
                self.cryptos,
                self.etfs,
                self.currencies,
            ]
        )

    def add(self, assets: "Assets") -> None:
        self.equities.extend(assets.equities)
        self.cryptos.extend(assets.cryptos)
        self.etfs.extend(assets.etfs)
        self.currencies.extend(assets.currencies)


class AbstractSource(BaseModel, abc.ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @validate_call(validate_return=True)
    def read_assets(self, keywords: Optional[List[str]] = None) -> Assets:
        try:
            return self._read_assets(keywords)
        except Exception as e:
            logger.error(f"Error reading assets from {type(self).__name__}: {e}")
            return Assets()

    @validate_call(validate_return=True)
    def read_financials(self, ticker: str) -> Financials:
        try:
            logger.info(f"Reading Financials from {type(self).__name__}: for {ticker}")
            return self._read_financials(ticker)
        except Exception as e:
            logger.error(f"Error reading Financials from {type(self).__name__}: {e}")
            return Financials()

    @abc.abstractmethod
    def _read_financials(self, ticker: str) -> Financials:
        ...

    @abc.abstractmethod
    def _read_assets(self, keywords: Optional[List[str]] = None) -> Assets:
        ...

    @abc.abstractmethod
    def read_series(self, ticker: str, type: str) -> List[CandleStick]:
        ...
