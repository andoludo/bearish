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
from bearish.models.api_keys.api_keys import SourceApiKeys
from bearish.models.assets.assets import Assets
from bearish.models.financials.base import Financials
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery
from bearish.sources.base import AbstractSource
from bearish.sources.financedatabase import FinanceDatabaseSource
from bearish.sources.investpy import InvestPySource
from bearish.sources.yfinance import yFinanceSource

logger = logging.getLogger(__name__)
app = typer.Typer()


class Bearish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: Path
    api_keys: SourceApiKeys = Field(default_factory=SourceApiKeys)
    _bearish_db: BearishDb = PrivateAttr()
    sources: List[AbstractSource] = Field(
        default_factory=lambda: [
            FinanceDatabaseSource(),
            InvestPySource(),
            yFinanceSource(),
        ]
    )

    def model_post_init(self, __context: Any) -> None:  # noqa: ANN401
        self._bearish_db = BearishDb(database_path=self.path)
        for source in self.sources:
            try:
                source.set_api_key(
                    self.api_keys.keys.get(
                        source.__source__, os.environ.get(source.__source__.upper())  # type: ignore
                    )
                )
            except InvalidApiKeyError as e:  # noqa: PERF203
                logger.error(
                    f"Invalid API key for {source.__source__}: {e}. It will be removed from sources"
                )
                self.sources.remove(source)

    def write_assets(self, query: Optional[AssetQuery] = None) -> None:
        for source in self.sources:
            if query:
                cached_assets = self.read_assets(AssetQuery(countries=query.countries))
                query.update_symbols(cached_assets)
            logger.info(f"Fetching assets from source {type(source).__name__}")
            assets_ = source.read_assets(query)
            if assets_.is_empty():
                logger.warning(f"No assets found from {type(source).__name__}")
                continue
            self._bearish_db.write_assets(assets_)

    def read_assets(self, assets_query: AssetQuery) -> Assets:
        return self._bearish_db.read_assets(assets_query)

    def read_financials(self, assets_query: AssetQuery) -> Financials:
        return self._bearish_db.read_financials(assets_query)

    def read_series(self, assets_query: AssetQuery) -> List[Price]:
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
def assets(path: Path, countries: List[str]) -> None:
    logger.info(
        f"Writing assets to database for countries: {countries}",
    )
    bearish = Bearish(path=path)
    bearish.write_assets(AssetQuery(countries=countries))


if __name__ == "__main__":
    app()
