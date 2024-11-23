from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, model_validator

from bearish.database.crud import BearishDb
from bearish.models.base import CandleStick
from bearish.sources.base import AbstractSource, Assets, Financials
from bearish.sources.yfinance import yFinanceSource


class AssetQuery(BaseModel):
    exchanges: List[str] = Field(default_factory=list)
    countries: List[str] = Field(default_factory=list)
    symbols: List[str] = Field(default_factory=list)
    markets: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_query(self) -> "AssetQuery":
        if all(not getattr(self, field) for field in self.model_fields):
            raise ValueError("At least one query parameter must be provided")
        return self


class Bearish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bearish_db: BearishDb = Field(default_factory=BearishDb)
    sources: List[AbstractSource] = Field(default_factory=lambda: [yFinanceSource()])  # type: ignore

    def write_assets(self, filters: Optional[List[str]] = None) -> None:
        for source in self.sources:
            assets = source.read_assets(filters)
            self.bearish_db.write_assets(assets)

    def read_assets(self, assets_query: AssetQuery) -> Assets:
        return self.bearish_db.read_assets(assets_query)

    def read_financials(self, assets_query: AssetQuery) -> Financials:
        return self.bearish_db.read_financials(assets_query)

    def read_series(self, assets_query: AssetQuery) -> List[CandleStick]:
        return self.bearish_db.read_series(assets_query)

    def write_financials(self, ticker: str) -> None:
        for source in self.sources:
            financials = source.read_financials(ticker)
            self.bearish_db.write_financials(financials)

    def write_series(self, ticker: str, type: str) -> None:
        for source in self.sources:
            series = source.read_series(ticker, type)
            self.bearish_db.write_series(series)
