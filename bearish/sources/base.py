import abc
from datetime import datetime
from typing import List, Optional, Any, Annotated

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, BeforeValidator

from bearish.models.base import Equity, Crypto, Etf, Currency, CandleStick
from bearish.models.financials import FinancialMetrics, BalanceSheet, CashFlow



class Financials(BaseModel):
    financial_metrics: List[FinancialMetrics] = Field(default_factory=list)
    balance_sheets: List[BalanceSheet] = Field(default_factory=list)
    cash_flows: List[CashFlow] = Field(default_factory=list)


class Assets(BaseModel):
    equities: List[Equity] = Field(default_factory=list)
    cryptos: List[Crypto] = Field(default_factory=list)
    etfs: List[Etf] = Field(default_factory=list)
    currencies: List[Currency] = Field(default_factory=list)





class AbstractSource(abc.ABC, BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @abc.abstractmethod
    def read_financials(self, ticker: str)-> Financials:...


    @abc.abstractmethod
    def read_assets(self, filters: Optional[List[str]] = None) -> Assets:...

    @abc.abstractmethod
    def read_series(self, ticker: str, type: str) -> List[CandleStick]:...


