import logging
from pathlib import Path
from typing import Optional, List, Any

import typer
from pydantic import BaseModel, Field, ConfigDict, model_validator, PrivateAttr

from bearish.database.crud import BearishDb
from bearish.models.base import CandleStick
from bearish.sources.alphavantage import AlphaVantageSource
from bearish.sources.base import AbstractSource, Assets, Financials
from bearish.sources.financedatabase import FinanceDatabaseSource
from bearish.sources.yfinance import yFinanceSource

logger = logging.getLogger(__name__)
app = typer.Typer()


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
    path: Path
    _bearish_db: BearishDb = PrivateAttr()
    sources: List[AbstractSource] = Field(
        default_factory=lambda: [
            yFinanceSource(),
            FinanceDatabaseSource(),
            AlphaVantageSource(),
        ]
    )

    def model_post_init(self, __context: Any) -> None:  # noqa: ANN401
        self._bearish_db = BearishDb(database_path=self.path)

    def write_assets(self, keywords: Optional[List[str]] = None) -> None:
        assets = Assets()
        for source in self.sources:
            logger.info(f"Fetching assets from source {type(source).__name__}")
            assets_ = source.read_assets(keywords)
            if assets_.is_empty():
                logger.warning(f"No assets found from {type(source).__name__}")
                continue
            assets.add(assets_)
        self._bearish_db.write_assets(assets)

    def read_assets(self, assets_query: AssetQuery) -> Assets:
        return self._bearish_db.read_assets(assets_query)

    def read_financials(self, assets_query: AssetQuery) -> Financials:
        return self._bearish_db.read_financials(assets_query)

    def read_series(self, assets_query: AssetQuery) -> List[CandleStick]:
        return self._bearish_db.read_series(assets_query)

    def read_financials_from_many_sources(self, ticker: str) -> Financials:
        financials = Financials()
        for source in self.sources:
            financials_ = source.read_financials(ticker)
            if financials_.is_empty():
                logger.warning(
                    f"No financials found for {ticker} from {type(source).__name__}"
                )
                continue
            financials.add(financials_)
        return financials

    def write_many_financials(self, tickers: List[str]) -> None:
        financials = Financials()
        for ticker in tickers:
            financials_ = self.read_financials_from_many_sources(ticker)
            financials.add(financials_)
            if financials_.is_empty():
                continue
        self._bearish_db.write_financials(financials)

    def write_many_series(self, tickers: List[str], type: str) -> None:
        for ticker in tickers:
            self.write_series(ticker, type)


    def write_series(self, ticker: str, type: str) -> None:
        series = []
        for source in self.sources:
            try:
                series_ = source.read_series(ticker, type)
            except Exception as e:
                logger.error(f"Error reading series: {e}")
                continue
            series.extend(series_)
        if series:
            self._bearish_db.write_series(series)



@app.command()
def assets(path: Path, keywords: Optional[List[str]] = None) -> None:
    logger.info(
        f"Writing assets to database with keywords: {keywords}",
    )
    bearish = Bearish(path=path)
    bearish.write_assets(keywords)


if __name__ == "__main__":
    app()
