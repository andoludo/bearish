import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional, List, Any, get_args, Annotated, cast, Union, Type

import typer
from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    PrivateAttr,
    validate_call,
    model_validator,
)
from rich.console import Console

from bearish.analysis.analysis import Analysis
from bearish.analysis.view import ViewsFactory
from bearish.database.crud import BearishDb
from bearish.exceptions import InvalidApiKeyError, LimitApiKeyReachedError
from bearish.exchanges.exchanges import (
    Countries,
    exchanges_factory,
    ExchangeQuery,
    Exchanges,
)
from bearish.interface.interface import BearishDbBase
from bearish.models.api_keys.api_keys import SourceApiKeys
from bearish.models.assets.assets import Assets
from bearish.models.base import Ticker, TrackerQuery, FinancialsTracker, PriceTracker
from bearish.models.financials.base import Financials
from bearish.models.price.price import Price
from bearish.models.price.prices import Prices
from bearish.models.query.query import AssetQuery, Symbols
from bearish.sources.base import AbstractSource
from bearish.sources.financedatabase import FinanceDatabaseSource
from bearish.sources.financial_modelling_prep import FmpAssetsSource, FmpSource
from bearish.sources.investpy import InvestPySource
from bearish.sources.tiingo import TiingoSource
from bearish.sources.yahooquery import YahooQuerySource
from bearish.sources.yfinance import yFinanceSource
from bearish.types import SeriesLength, Sources
from bearish.utils.utils import batch

logger = logging.getLogger(__name__)
app = typer.Typer()
console = Console()


class CountryEnum(str, Enum): ...


CountriesEnum = Enum(  # type: ignore
    "CountriesEnum",
    {country: country for country in get_args(Countries)},
    type=CountryEnum,
)


class Filter(BaseModel):
    countries: List[CountriesEnum]
    filters: Optional[List[str] | str] = None

    @model_validator(mode="after")
    def _model_validator(self) -> "Filter":
        if self.filters is not None and isinstance(self.filters, str):
            self.filters = [t.strip() for t in self.filters.split(",")]
        return self

    def filter(self, tickers: List[Ticker]) -> List[Ticker]:
        if not self.filters:
            return tickers
        return list({t for t in tickers if t.symbol in self.filters})


class Bearish(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: Path
    batch_size: int = Field(default=500)
    api_keys: SourceApiKeys = Field(default_factory=SourceApiKeys)
    _bearish_db: BearishDbBase = PrivateAttr()
    exchanges: Exchanges = Field(default_factory=exchanges_factory)
    asset_sources: List[AbstractSource] = Field(
        default_factory=lambda: [
            FinanceDatabaseSource(),
            InvestPySource(),
            FmpAssetsSource(),
        ]
    )
    detailed_asset_sources: List[AbstractSource] = Field(
        default_factory=lambda: [yFinanceSource(), YahooQuerySource(), FmpSource()]
    )
    financials_sources: List[AbstractSource] = Field(
        default_factory=lambda: [
            yFinanceSource(),
            YahooQuerySource(),
            FmpSource(),
        ]
    )
    price_sources: List[AbstractSource] = Field(
        default_factory=lambda: [
            yFinanceSource(),
            YahooQuerySource(),
            TiingoSource(),
        ]
    )

    def model_post_init(self, __context: Any) -> None:
        self._bearish_db = BearishDb(database_path=self.path)
        for source in set(
            self.financials_sources
            + self.price_sources
            + self.asset_sources
            + self.detailed_asset_sources
        ):
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
                for sources in [
                    self.financials_sources,
                    self.price_sources,
                    self.asset_sources,
                    self.detailed_asset_sources,
                ]:
                    if source in sources:
                        sources.remove(source)

    def get_asset_sources(self) -> List[Sources]:
        return [source.__source__ for source in self.asset_sources]

    def get_detailed_asset_sources(self) -> List[Sources]:
        return [source.__source__ for source in self.detailed_asset_sources]

    def write_assets(self, query: Optional[AssetQuery] = None) -> None:
        existing_sources = self._bearish_db.read_sources()
        asset_sources = [
            asset_source
            for asset_source in self.asset_sources
            if asset_source.__source__ not in existing_sources
        ]
        logger.debug(f"Found asset sources: {[s.__source__ for s in asset_sources]}")
        return self._write_base_assets(asset_sources, query)

    def write_detailed_assets(self, query: Optional[AssetQuery] = None) -> None:
        return self._write_base_assets(
            self.detailed_asset_sources, query, use_all_sources=False
        )

    def _write_base_assets(
        self,
        asset_sources: List[AbstractSource],
        query: Optional[AssetQuery] = None,
        use_all_sources: bool = True,
    ) -> None:

        if query:
            cached_assets = self.read_assets(AssetQuery.model_validate(query))
            query.update_symbols(cached_assets)
        for source in asset_sources:

            logger.info(f"Fetching assets from source {type(source).__name__}")
            assets_ = source.read_assets(query)
            if assets_.is_empty():
                logger.warning(f"No assets found from {type(source).__name__}")
                continue
            logger.debug(
                f"writing assets from {type(source).__name__}. Number of symbols: {len(assets_.symbols())}"
            )
            self._bearish_db.write_assets(assets_)
            self._bearish_db.write_source(source.__source__)
            if use_all_sources:
                continue
            if not assets_.failed_query.symbols:
                break
            else:
                query = AssetQuery(
                    symbols=Symbols(equities=assets_.failed_query.symbols)  # type: ignore
                )

    def read_assets(self, assets_query: AssetQuery) -> Assets:
        return self._bearish_db.read_assets(assets_query)

    def read_financials(self, assets_query: AssetQuery) -> Financials:
        return self._bearish_db.read_financials(assets_query)

    def read_series(self, assets_query: AssetQuery, months: int = 1) -> List[Price]:
        return self._bearish_db.read_series(assets_query, months=months)

    def _get_tracked_tickers(
        self,
        tracker_query: TrackerQuery,
        tracker_type: Union[Type[PriceTracker], Type[FinancialsTracker]],
    ) -> List[Ticker]:
        return self._bearish_db.read_tracker(tracker_query, tracker_type)

    def get_tickers_without_financials(self, tickers: List[Ticker]) -> List[Ticker]:
        tracked_tickers = self._get_tracked_tickers(TrackerQuery(), FinancialsTracker)
        return [t for t in tickers if t not in tracked_tickers]

    def get_tickers_without_price(self, tickers: List[Ticker]) -> List[Ticker]:
        return [
            t
            for t in tickers
            if t not in self._get_tracked_tickers(TrackerQuery(), PriceTracker)
        ]

    def get_ticker_with_price(self) -> List[Ticker]:
        return [
            Ticker(symbol=t)
            for t in self._get_tracked_tickers(TrackerQuery(), PriceTracker)
        ]

    def write_many_financials(self, tickers: List[Ticker]) -> None:
        tickers = self.get_tickers_without_financials(tickers)
        logger.warning(
            f"Found tickers without financials: {[t.symbol for t in tickers]}"
        )
        chunks = batch(tickers, size=self.batch_size)
        for source in self.financials_sources:
            logger.debug("getting data tickers")
            for chunk in chunks:
                try:
                    financials_ = source.read_financials(chunk)
                except (InvalidApiKeyError, LimitApiKeyReachedError, Exception) as e:
                    logger.error(f"Error reading data using {source.__source__}: {e}")
                    continue

                if not financials_:
                    logger.warning("No financial data found.")
                    continue
                self._bearish_db.write_financials(financials_)
                self._bearish_db.write_trackers(
                    [
                        FinancialsTracker(
                            symbol=t.symbol,
                            source=source.__source__,
                            exchange=t.exchange,
                        )
                        for t in tickers
                    ]
                )

            break

    @validate_call
    def write_many_series(self, tickers: List[Ticker], type: SeriesLength) -> None:
        tickers = self.get_tickers_without_price(tickers)
        chunks = batch(tickers, self.batch_size)
        for source in self.price_sources:
            for chunk in chunks:
                try:
                    series_ = source.read_series(chunk, type)
                except (InvalidApiKeyError, LimitApiKeyReachedError, Exception) as e:
                    logger.error(f"Error reading series: {e}")
                    continue
                if series_:
                    price_date = Prices(prices=series_).get_last_date()
                    self._bearish_db.write_series(series_)
                    self._bearish_db.write_trackers(
                        [
                            PriceTracker(
                                symbol=t.symbol,
                                source=source.__source__,
                                exchange=t.exchange,
                                date=price_date,
                            )
                            for t in tickers
                        ]
                    )
                break

    def read_sources(self) -> List[str]:
        return self._bearish_db.read_sources()

    def get_tickers(self, exchange_query: ExchangeQuery) -> List[Ticker]:
        return self._bearish_db.get_tickers(exchange_query)

    def get_detailed_tickers(self, filter: Filter) -> None:
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries), self.get_asset_sources()
            )
        )

        tickers = filter.filter(tickers)
        asset_query = AssetQuery(symbols=Symbols(equities=tickers))  # type: ignore
        self.write_detailed_assets(asset_query)

    def get_financials(self, filter: Filter) -> None:
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries),
                self.get_detailed_asset_sources(),
            )
        )
        tickers = filter.filter(tickers)
        logger.debug(f"Found tickers: {[t.symbol for t in tickers]}")
        self.write_many_financials(tickers)

    def get_prices(self, filter: Filter) -> None:
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries),
                self.get_detailed_asset_sources(),
            )
        )
        tickers = filter.filter(tickers)
        self.write_many_series(tickers, "max")

    def run_analysis(self, filter: Filter) -> None:
        tickers = self.get_tickers(
            self.exchanges.get_exchange_query(
                cast(List[Countries], filter.countries),
                self.get_detailed_asset_sources(),
            )
        )
        tickers = filter.filter(tickers)
        for ticker in tickers:
            analysis = Analysis.from_ticker(self._bearish_db, ticker)
            self._bearish_db.write_analysis(analysis)

    def update_prices(self, symbols: List[str]) -> None:
        tickers = self._get_tracked_tickers(TrackerQuery(), PriceTracker)
        tickers = [t for t in tickers if t.symbol in symbols]
        self.write_many_series(tickers, "max")


@app.command()
def run(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
) -> None:

    console.log(
        f"Fetching assets to database for countries: {countries}, with filters: {filters}",
    )
    source_api_keys = SourceApiKeys.from_file(api_keys)
    bearish = Bearish(path=path, api_keys=source_api_keys)
    with console.status("[bold green]Fetching Tickers data..."):
        bearish.write_assets()
        filter = Filter(countries=countries, filters=filters)
        bearish.get_detailed_tickers(filter)
        console.log("[bold][red]Tickers downloaded!")
    with console.status("[bold green]Fetching Financial data..."):
        bearish.get_financials(filter)
        console.log("[bold][red]Financial downloaded!")
    with console.status("[bold green]Fetching Price data..."):
        bearish.get_prices(filter)
        console.log("[bold][red]Price downloaded!")
    with console.status("[bold green]Running analysis..."):
        bearish.run_analysis(filter)
        console.log("[bold][red]Analysis done!")


@app.command()
def tickers(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
    skip_base_tickers: Optional[bool] = False,
) -> None:
    with console.status("[bold green]Fetching Tickers data..."):
        logger.info(
            f"Writing assets to database for countries: {countries}",
        )
        source_api_keys = SourceApiKeys.from_file(api_keys)
        bearish = Bearish(path=path, api_keys=source_api_keys)
        if not skip_base_tickers:
            console.log("[green]Fetching base Tickers[/green]")
            bearish.write_assets()
        filter = Filter(countries=countries, filters=filters)
        console.log("[green]Fetching detailed Tickers[/green]")
        bearish.get_detailed_tickers(filter)
        console.log("[bold][red]Tickers downloaded!")


@app.command()
def financials(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
) -> None:
    with console.status("[bold green]Fetching Financial data..."):
        source_api_keys = SourceApiKeys.from_file(api_keys)
        bearish = Bearish(path=path, api_keys=source_api_keys)
        filter = Filter(countries=countries, filters=filters)
        bearish.get_financials(filter)
        console.log("[bold][red]Financial data downloaded!")


@app.command()
def prices(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
) -> None:
    with console.status("[bold green]Fetching Price data..."):
        source_api_keys = SourceApiKeys.from_file(api_keys)
        bearish = Bearish(path=path, api_keys=source_api_keys)
        filter = Filter(countries=countries, filters=filters)
        bearish.get_prices(filter)
        console.log("[bold][red]Price data downloaded!")


@app.command()
def analysis(
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
) -> None:
    with console.status("[bold green]Running analysis..."):
        source_api_keys = SourceApiKeys.from_file(api_keys)
        bearish = Bearish(path=path, api_keys=source_api_keys)
        filter = Filter(countries=countries, filters=filters)
        bearish.run_analysis(filter)
        ViewsFactory().compute(bearish_db=bearish._bearish_db)
        console.log("[bold][red]Analysis done!")


@app.command()
def views(
    path: Path,
    api_keys: Optional[Path] = None,
) -> None:
    with console.status("[bold green]Running views..."):
        source_api_keys = SourceApiKeys.from_file(api_keys)
        bearish = Bearish(path=path, api_keys=source_api_keys)
        ViewsFactory().compute(bearish_db=bearish._bearish_db)
        console.log("[bold][red]views done!")


@app.command()
def update_prices(
    path: Path,
    symbols: Annotated[List[str], typer.Argument()],
    api_keys: Optional[Path] = None,
) -> None:
    source_api_keys = SourceApiKeys.from_file(api_keys)
    bearish = Bearish(path=path, api_keys=source_api_keys)
    bearish.update_prices(symbols)


if __name__ == "__main__":
    app()
