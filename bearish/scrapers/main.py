import json
import logging
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Type, Union

from pydantic import BaseModel, ConfigDict, Field
from selenium.webdriver.chrome.webdriver import WebDriver

from bearish.scrapers.base import BasePage, BaseSettings, bearish_path_fun, init_chrome
from bearish.scrapers.investing import InvestingScreenerScraper, InvestingTickerScraper
from bearish.scrapers.model import Ticker, merge, unflatten_json
from bearish.scrapers.settings import InvestingCountry, TradingCountry
from bearish.scrapers.trading import TradingScreenerScraper, TradingTickerScraper

logger = logging.getLogger(__name__)


class Source(BaseModel):
    screener: Union[Type[InvestingScreenerScraper], Type[TradingScreenerScraper]]
    ticker: Union[Type[InvestingTickerScraper], Type[TradingTickerScraper]]
    country: Union[Type[InvestingCountry], Type[TradingCountry]]


class DataSource:
    investing: Source = Source(
        screener=InvestingScreenerScraper,
        ticker=InvestingTickerScraper,
        country=InvestingCountry,
    )
    trading: Source = Source(
        screener=TradingScreenerScraper,
        ticker=TradingTickerScraper,
        country=TradingCountry,
    )


def _filter_by_symbols(
    tickers: list[Ticker], symbols: Optional[list[str]] = None
) -> list[Ticker]:
    if not symbols:
        return tickers
    return [ticker for ticker in tickers if ticker.symbol in symbols]


class Scraper(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=True)
    bearish_path: Optional[Path] = Field(
        default_factory=bearish_path_fun, description=""
    )
    source: Source
    country: Literal["germany", "france", "belgium", "usa"]
    settings: Optional[BaseSettings] = None
    browser: WebDriver = Field(default_factory=init_chrome, description="")

    def _screener_scraper(self, first_page_only: bool = False) -> BasePage:
        return self.source.screener(  # type: ignore
            country=getattr(self.source.country, self.country),
            bearish_path=self.bearish_path,
            first_page_only=first_page_only,
            settings=self.settings,
            browser=self.browser,
        )

    def scrape(
        self,
        skip_existing: bool = True,
        symbols: Optional[list[str]] = None,
        first_page_only: bool = False,
    ) -> None:
        screener_scraper = self._screener_scraper(first_page_only=first_page_only)
        screener_scraper.scrape(skip_existing=skip_existing)
        tickers = Ticker.from_json(
            screener_scraper.get_stored_raw(), source=self.source.screener.source
        )
        tickers = _filter_by_symbols(tickers=tickers, symbols=symbols)
        for ticker in tickers:
            scraper = self.source.ticker(  # type: ignore
                browser=self.browser,
                exchange=ticker.reference,
                bearish_path=self.bearish_path,
                settings=self.settings,
            )
            try:
                scraper.scrape(skip_existing=skip_existing)
            except Exception as e:
                logger.error(f"Fail {ticker.reference}. reason: {e}")

    def create_db_json(
        self, symbols: Optional[list[str]] = None
    ) -> list[Dict[str, Any]]:
        scraper = self._screener_scraper()
        if not scraper.get_stored_raw().exists():
            return []
        tickers = Ticker.from_json(
            scraper.get_stored_raw(), source=self.source.ticker.source
        )
        db_json = []
        tickers = _filter_by_symbols(tickers=tickers, symbols=symbols)
        for ticker in tickers:
            ticker_scraper = self.source.ticker(  # type: ignore
                browser=self.browser,
                exchange=ticker.reference,
                bearish_path=self.bearish_path,
                settings=self.settings,
            )
            if not ticker_scraper.get_stored_raw().exists():
                continue
            data = json.loads(ticker_scraper.get_stored_raw().read_text())
            data = unflatten_json(Ticker, data)
            ticker_ = Ticker(**data)
            merge(Ticker, ticker, ticker_)
            db_json.append(ticker.model_dump())
        return db_json

    def update_db_json(self, db_json_path: Path) -> None:
        db_json = json.loads(db_json_path.read_text())
        tickers = [Ticker(**ticker_json) for ticker_json in db_json]
        for ticker in tickers:
            ticker_scraper = self.source.ticker(  # type: ignore
                browser=self.browser,
                exchange=ticker.reference,
                bearish_path=self.bearish_path,
                settings=self.settings,
            )
            if ticker_scraper.source != ticker.source:
                continue
            records = ticker_scraper.scrape(skip_existing=False)
            if not records:
                continue
            Ticker.from_record(records, source=ticker.source)
