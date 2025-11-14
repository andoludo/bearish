import datetime
import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional, List, Any, get_args, Annotated, cast, Union, Type, Callable

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
from sqlmodel import SQLModel

from bearish.database.crud import BearishDb
from bearish.database.schemas import PriceIndexORM, PriceEtfORM
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
from bearish.models.assets.index import PRICE_INDEX
from bearish.models.base import Ticker, TrackerQuery, FinancialsTracker, PriceTracker
from bearish.models.financials.base import Financials
from bearish.models.price.price import Price
from bearish.models.price.prices import Prices
from bearish.models.query.query import AssetQuery, Symbols
from bearish.models.sec.sec import Secs
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
    countries: List[CountriesEnum] = Field(default_factory=list)
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
    auto_migration: bool = True
    batch_size: int = Field(default=100)
    pause: int = Field(default=60)
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
        self._bearish_db = BearishDb(
            database_path=self.path, auto_migration=self.auto_migration
        )
        for source in set(
            self.financials_sources
            + self.price_sources
            + self.asset_sources
            + self.detailed_asset_sources
        ):
            source.set_pause(self.pause)
            try:
                source.set_api_key(
                    self.api_keys.keys.get(
                        source.__source__, os.environ.get(source.__source__.upper())  # type: ignore
                    )
                )
            except Exception as e:
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

    def set_batch_size(self, batch_size: int) -> None:
        self.batch_size = batch_size

    def set_pause(self, pause: int) -> None:
        for source in set(
            self.financials_sources
            + self.price_sources
            + self.asset_sources
            + self.detailed_asset_sources
        ):
            source.set_pause(pause)

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

    def read_series(
        self,
        assets_query: AssetQuery,
        months: int = 1,
        table: Optional[Type[SQLModel]] = None,
    ) -> List[Price]:
        return self._bearish_db.read_series(assets_query, months=months, table=table)

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
        logger.warning(f"Found tickers without financials: {len(tickers)}")
        chunks = batch(tickers, size=self.batch_size)
        source = self.financials_sources[0]

        for chunk in chunks:
            logger.debug(f"getting financial data for {len(chunk)} tickers")
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
                    for t in chunk
                ]
            )

    @validate_call
    def write_many_series(
        self,
        tickers: List[Ticker],
        type: SeriesLength,
        apply_filter: bool = True,
        table: Optional[Type[SQLModel]] = None,
        track: bool = True,
    ) -> None:
        chunks = batch(tickers, self.batch_size)
        source = self.price_sources[0]
        for chunk in chunks:
            logger.debug(f"getting financial data for {len(chunk)} tickers")
            try:
                series_ = source.read_series(chunk, type, apply_filter=apply_filter)
            except (InvalidApiKeyError, LimitApiKeyReachedError, Exception) as e:
                logger.error(f"Error reading series: {e}")
                continue
            if series_:
                self._bearish_db.write_series(series_, table=table)
                if track:
                    prices_date = Prices(prices=series_)
                    self._bearish_db.write_trackers(
                        [
                            PriceTracker(
                                symbol=t.symbol,
                                source=source.__source__,
                                exchange=t.exchange,
                                date=prices_date.ticker_date(t.symbol),
                            )
                            for t in chunk
                        ]
                    )

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

    def get_prices_index(self, series_length: SeriesLength = "max") -> None:
        asset_query = AssetQuery(symbols=Symbols(index=PRICE_INDEX))  # type: ignore
        assets = self.read_assets(asset_query)
        self.write_many_series(
            [Ticker(symbol=i.symbol) for i in assets.index],
            series_length,
            apply_filter=False,
            table=PriceIndexORM,
            track=False,
        )

    def get_prices_etf(
        self, series_length: SeriesLength = "max", limit: Optional[int] = None
    ) -> List[str]:
        query_etfs = "SELECT DISTINCT symbol from etf;"
        etf_symbols = self._bearish_db.read_query(query_etfs)["symbol"].tolist()
        if limit:
            etf_symbols = etf_symbols[:limit]
        self.write_many_series(
            [Ticker(symbol=symbol) for symbol in etf_symbols],
            series_length,
            apply_filter=False,
            table=PriceEtfORM,
            track=False,
        )
        return etf_symbols

    def _update(
        self,
        tracker_type: Union[Type[PriceTracker], Type[FinancialsTracker]],
        write_function: Callable[[List[Ticker]], None],
        symbols: Optional[List[str]] = None,
        reference_date: Optional[datetime.date] = None,
        delay: int = 5,
    ) -> None:
        reference_date = reference_date or datetime.date.today()
        tickers = self._get_tracked_tickers(
            TrackerQuery(reference_date=reference_date, delay=delay), tracker_type
        )
        if symbols is not None:
            tickers = [t for t in tickers if t.symbol in symbols]
        write_function(tickers)

    def update_prices(  # noqa: PLR0913
        self,
        symbols: Optional[List[str]] = None,
        reference_date: Optional[datetime.date] = None,
        delay: int = 1,
        series_length: SeriesLength = "1mo",
        batch_size: int = 100,
        pause: int = 60,
    ) -> None:
        def write_function(tickers: List[Ticker]) -> None:
            logger.debug(f"Updating prices for {len(tickers)} tickers")
            self.write_many_series(tickers, series_length, apply_filter=False)

        self.set_batch_size(batch_size)
        self.set_pause(pause)
        self._update(
            PriceTracker,
            write_function,
            symbols=symbols,
            reference_date=reference_date,
            delay=delay,
        )

    def update_financials(
        self,
        symbols: Optional[List[str]] = None,
        reference_date: Optional[datetime.date] = None,
        delay: int = 20,
    ) -> None:
        def write_function(tickers: List[Ticker]) -> None:
            self.write_many_financials(tickers)

        self._update(
            FinancialsTracker,
            write_function,
            symbols=symbols,
            reference_date=reference_date,
            delay=delay,
        )


@app.command()
def run(  # noqa: PLR0913
    path: Path,
    countries: Annotated[List[CountriesEnum], typer.Argument()],
    filters: Optional[str] = None,
    api_keys: Optional[Path] = None,
    etf: bool = True,
    index: bool = True,
    sec: bool = True,
    financials: bool = True,
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
    with console.status("[bold green]Fetching Price data..."):
        bearish.get_prices(filter)
        console.log("[bold][red]Price downloaded!")
    if index:
        with console.status("[bold green]Fetching Price index..."):
            bearish.get_prices_index()
            console.log("[bold][red]Price index downloaded!")
    if etf:
        with console.status("[bold green]Fetching Etf price..."):
            bearish.get_prices_etf()
            console.log("[bold][red]Price etf downloaded!")
    if sec:
        with console.status("[bold green]Fetching SEC data..."):
            Secs.upload(bearish._bearish_db)  # type: ignore
            console.log("[bold][red]SEC data downloaded!")
    if financials:
        with console.status("[bold green]Fetching Financial data..."):
            bearish.get_financials(filter)
            console.log("[bold][red]Financial downloaded!")


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
def sec(
    path: Path,
    api_keys: Optional[Path] = None,
) -> None:
    with console.status("[bold green]Fetching SEC data..."):
        source_api_keys = SourceApiKeys.from_file(api_keys)
        bearish = Bearish(path=path, api_keys=source_api_keys)
        Secs.upload(bearish._bearish_db)  # type: ignore


@app.command()
def update(
    path: Path,
    symbols: Optional[List[str]] = None,
    api_keys: Optional[Path] = None,
    series_length: str = "1mo",
) -> None:
    source_api_keys = SourceApiKeys.from_file(api_keys)
    bearish = Bearish(path=path, api_keys=source_api_keys)
    bearish.update_prices(symbols, series_length=series_length)  # type: ignore
    bearish.get_prices_index(series_length=series_length)  # type: ignore
    bearish.get_prices_etf(series_length=series_length)  # type: ignore
    Secs.upload(bearish._bearish_db)  # type: ignore
    bearish.update_financials(symbols)


if __name__ == "__main__":
    app()
