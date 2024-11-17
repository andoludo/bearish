from functools import cached_property
from typing import Optional

from pydantic import BaseModel, Field, validate_call, ConfigDict

from bearish.database.crud import BearishDb
from bearish.equities import EquityQuery, Equities, DailySeries, SeriesType
from bearish.financials import ManyFinancials


class Bearish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    equities_query: EquityQuery
    bearish_db: BearishDb = Field(default_factory=BearishDb)

    def initialize(self, url: Optional[str] = None):
        equities = Equities.from_url(url)
        equities.write(self.bearish_db)

    @cached_property
    def _equities(self):
        equities =  self.bearish_db.read_equities(
            self.equities_query
        )
        if not equities:
            raise ValueError("No equities found. init() must be called first")
        return equities

    @validate_call
    def update(self,type: SeriesType ):
        for equity in self._equities:
            financials = ManyFinancials.from_yfinance(equity)
            financials.write(self.bearish_db)
            daily_series = DailySeries.from_yfinance(equity, type)
            daily_series.write(self.bearish_db)

    def read_series(self, months: int):
        return self.bearish_db.read_series(self._equities, months)

    def read_financials(self):
        return self.bearish_db.read_financials(self._equities)