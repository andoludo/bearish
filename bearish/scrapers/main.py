import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic._internal._model_construction import ModelMetaclass

from bearish.scrapers.base import bearish_path_fun
from bearish.scrapers.investing import (
    InvestingCountry,
    InvestingScreenerScraper,
    InvestingTickerScraper,
)
from bearish.scrapers.model import Ticker, merge, unflatten_json
from bearish.scrapers.trading import (
    TradingCountry,
    TradingScreenerScraper,
    TradingTickerScraper,
)

logger = logging.getLogger(__name__)


@dataclass
class Source:
    screener: ModelMetaclass
    ticker: ModelMetaclass
    country: Enum


class DataSource(Enum):
    investing = Source(
        screener=InvestingScreenerScraper,
        ticker=InvestingTickerScraper,
        country=InvestingCountry,
    )
    trading = Source(
        screener=TradingScreenerScraper,
        ticker=TradingTickerScraper,
        country=TradingCountry,
    )


class Country(Enum):
    germany: str = "germany"
    france: str = "france"
    belgium: str = "belgium"
    usa: str = "usa"


class Scraper(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=True)
    bearish_path: Optional[Path] = Field(
        default_factory=bearish_path_fun, description=""
    )
    source: DataSource
    country: Country

    def _filter_by_symbols(
        self, tickers: list[Ticker], symbols: Optional[list[str]] = None
    ) -> list[Ticker]:
        if not symbols:
            return tickers
        return [ticker for ticker in tickers if ticker.symbol in symbols]

    def scrape(
        self, skip_existing: bool = True, symbols: Optional[list[str]] = None
    ) -> None:
        screener_scraper = self.source.screener(
            country=getattr(self.source.country, self.country),
            bearish_path=self.bearish_path,
        )
        screener_scraper.scrape(skip_existing=skip_existing)
        tickers = Ticker.from_json(screener_scraper.get_stored_raw())
        tickers = self._filter_by_symbols(tickers=tickers, symbols=symbols)
        for ticker in tickers:
            scraper = self.source.ticker(
                exchange=ticker.reference, bearish_path=self.bearish_path
            )
            try:
                scraper.scrape(skip_existing=skip_existing)
            except Exception as e:
                logger.error(f"Fail {ticker.reference}. reason: {e}")

    def create_db_json(self) -> list[dict]:
        scraper = self._scraper()
        if not scraper.get_stored_raw().exists():
            return
        tickers = Ticker.from_json(scraper.get_stored_raw())
        db_json = []
        for ticker in tickers:
            ticker_scraper = self.source.ticker(
                browser=None, exchange=ticker.reference, bearish_path=self.bearish_path
            )
            if not ticker_scraper.get_stored_raw().exists():
                continue
            data = json.loads(ticker_scraper.get_stored_raw().read_text())
            data = unflatten_json(Ticker, data)
            ticker_ = Ticker(**data)
            merge(Ticker, ticker, ticker_)
            db_json.append(ticker.model_dump())
        return db_json
