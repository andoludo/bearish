from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, model_validator

from bearish.database.crud import BearishDb
from bearish.sources.base import AbstractSource
from bearish.sources.yfinance import yFinanceSource

class AssetQuery(BaseModel):
    exchanges: List[str] = Field(default_factory=list)
    countries: List[str] = Field(default_factory=list)
    symbols: List[str] = Field(default_factory=list)
    markets: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_query(self) -> "EquityQuery":
        if all([not getattr(self, field) for field in self.model_fields]):
            raise ValueError("At least one query parameter must be provided")
        return self
class Bearish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # equities_query: EquityQuery
    bearish_db: BearishDb = Field(default_factory=BearishDb)
    sources: List[AbstractSource] = Field(default_factory=lambda: [yFinanceSource()])

    # def initialize(self, url: Optional[str] = None):
    #     equities = Equities.from_url(url)
    #     equities.write(self.bearish_db)
    #
    # @cached_property
    # def _equities(self):
    #     equities =  self.bearish_db.read_equities(
    #         self.equities_query
    #     )
    #     if not equities:
    #         raise ValueError("No equities found. init() must be called first")
    #     return equities

    def write_assets(self, filters: Optional[List[str]] = None):
        for source in self.sources:
            assets = source.read_assets(filters)
            self.bearish_db.write_assets(assets)

    def read_assets(self, assets_query: AssetQuery):
        return self.bearish_db.read_assets(assets_query)

    def read_financials(self, assets_query: AssetQuery):
        return self.bearish_db.read_financials(assets_query)
    def read_series(self, assets_query: AssetQuery):
        return self.bearish_db.read_series(assets_query)

    def write_financials(self, ticker: str):
        for source in self.sources:
            financials = source.read_financials(ticker)
            self.bearish_db.write_financials(financials)

    def write_series(self, ticker: str, type: str):
        for source in self.sources:
            series = source.read_series(ticker, type)
            self.bearish_db.write_series(series)

    # @validate_call
    # def update(self,type: SeriesType ):
    #     for equity in self._equities:
    #         financials = ManyFinancials.from_yfinance(equity)
    #         financials.write(self.bearish_db)
    #         daily_series = DailySeries.from_yfinance(equity, type)
    #         daily_series.write(self.bearish_db)
    #
    # def read_series(self, months: int):
    #     return self.bearish_db.read_series(self._equities, months)
    #
    # def read_financials(self):
    #     return self.bearish_db.read_financials(self._equities)
