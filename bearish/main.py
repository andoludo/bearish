import logging
import os
from pathlib import Path
from typing import Optional, List, Any

import typer
from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    PrivateAttr,
)

from bearish.database.crud import BearishDb
from bearish.exceptions import InvalidApiKeyError
from bearish.interface.interface import BearishDbBase
from bearish.models.api_keys.api_keys import SourceApiKeys
from bearish.models.assets.assets import Assets
from bearish.models.financials.base import Financials
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery
from bearish.sources.alphavantage import AlphaVantageSource
from bearish.sources.base import AbstractSource
from bearish.sources.financedatabase import FinanceDatabaseSource
from bearish.sources.financial_modelling_prep import FmpAssetsSource, FmpSource
from bearish.sources.investpy import InvestPySource
from bearish.sources.tiingo import TiingoSource
from bearish.sources.yfinance import yFinanceSource

logger = logging.getLogger(__name__)
app = typer.Typer()


class Bearish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: Path
    api_keys: SourceApiKeys = Field(default_factory=SourceApiKeys)
    _bearish_db: BearishDbBase = PrivateAttr()
    asset_sources: List[AbstractSource] = Field(
        default_factory=lambda: [
            FinanceDatabaseSource(),
            InvestPySource(),
            FmpAssetsSource(),
        ]
    )
    sources: List[AbstractSource] = Field(
        default_factory=lambda: [
            yFinanceSource(),
            AlphaVantageSource(),
            FmpSource(),
            TiingoSource(),
        ]
    )

    def model_post_init(self, __context: Any) -> None:  # noqa: ANN401
        self._bearish_db = BearishDb(database_path=self.path)
        for source in self.sources + self.asset_sources:
            try:
                source.set_api_key(
                    self.api_keys.keys.get(
                        source.__source__, os.environ.get(source.__source__.upper())  # type: ignore
                    )
                )
            except Exception as e:  # noqa: PERF203
                logger.error(
                    f"Invalid API key for {source.__source__}: {e}. It will be removed from sources"
                )
                self.sources.remove(source)

    def write_assets(self, query: Optional[AssetQuery] = None) -> None:
        existing_sources = self._bearish_db.read_sources()
        asset_sources = [
            asset_source
            for asset_source in self.asset_sources
            if asset_source.__source__ not in existing_sources
        ]
        for source in asset_sources + self.sources:
            if query:
                cached_assets = self.read_assets(AssetQuery.model_validate(query))
                query.update_symbols(cached_assets)
            logger.info(f"Fetching assets from source {type(source).__name__}")
            assets_ = source.read_assets(query)
            if assets_.is_empty():
                logger.warning(f"No assets found from {type(source).__name__}")
                continue
            self._bearish_db.write_assets(assets_)
            self._bearish_db.write_source(source.__source__)

    def read_assets(self, assets_query: AssetQuery) -> Assets:
        return self._bearish_db.read_assets(assets_query)

    def read_financials(self, assets_query: AssetQuery) -> Financials:
        return self._bearish_db.read_financials(assets_query)

    def read_series(self, assets_query: AssetQuery) -> List[Price]:
        return self._bearish_db.read_series(assets_query)

    def write_many_financials(self, tickers: List[str]) -> None:
        for source in self.sources:
            self.write_financials(source, tickers)

    def write_financials(self, source: AbstractSource, tickers: List[str]) -> None:
        financials = Financials()
        for ticker in tickers:
            try:
                financials_ = source.read_financials(ticker)
            except InvalidApiKeyError as e:
                logger.error(f"Invalid API key for {source.__source__}: {e}")
                break
            if financials_.is_empty():
                continue
            financials.add(financials_)
        self._bearish_db.write_financials(financials)

    def write_many_series(self, tickers: List[str], type: str) -> None:
        for source in self.sources:
            self.write_series(source, tickers, type)

    def write_series(
        self, source: AbstractSource, tickers: List[str], type: str
    ) -> None:
        series = []
        for ticker in tickers:
            try:
                series_ = source.read_series(ticker, type)
            except Exception as e:
                logger.error(f"Error reading series: {e}")
                continue
            series.extend(series_)
        if series:
            self._bearish_db.write_series(series)

    def read_sources(self) -> List[str]:
        return self._bearish_db.read_sources()


@app.command()
def tickers(path: Path, exchanges: List[str], api_keys: Optional[Path] = None) -> None:

    logger.info(
        f"Writing assets to database for countries: {exchanges}",
    )
    source_api_keys = SourceApiKeys.from_file(api_keys)
    bearish = Bearish(path=path, api_keys=source_api_keys)
    bearish.write_assets(AssetQuery(exchanges=exchanges, countries=[]))


@app.command()
def financials(
    path: Path, exchanges: List[str], api_keys: Optional[Path] = None
) -> None:
    source_api_keys = SourceApiKeys.from_file(api_keys)
    bearish = Bearish(path=path, api_keys=source_api_keys)
    asset_query = AssetQuery(exchanges=exchanges, countries=[])
    assets = bearish.read_assets(asset_query)
    bearish.write_many_financials(assets.symbols())


@app.command()
def series(path: Path, exchanges: List[str], api_keys: Optional[Path] = None) -> None:
    source_api_keys = SourceApiKeys.from_file(api_keys)
    bearish = Bearish(path=path, api_keys=source_api_keys)
    asset_query = AssetQuery(exchanges=exchanges, countries=[])
    assets = bearish.read_assets(asset_query)
    bearish.write_many_series(assets.symbols(), "full")


if __name__ == "__main__":
    app()
