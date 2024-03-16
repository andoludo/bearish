import logging
import tempfile
from pathlib import Path

from bearish.scrapers.base import init_chrome
from bearish.scrapers.investing import (
    InvestingScreenerScraper,
    InvestingSettings,
    InvestingTickerScraper,
)
from bearish.scrapers.settings import InvestingCountry

logger = logging.getLogger(__name__)


def test_investing_screener_belgium(invest_settings: InvestingSettings) -> None:
    with tempfile.TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory).joinpath("investing")
        browser = init_chrome(headless=True)
        scraper = InvestingScreenerScraper(
            browser=browser,
            country=InvestingCountry.belgium,
            settings=invest_settings,
            bearish_path=temp_path,
            first_page_only=True,
        )
        data = scraper.scrape()
        assert data
        assert Path(temp_path).joinpath("investing", "screener", "belgium").exists()


def test_investing_ticker_scraper(invest_settings: InvestingSettings) -> None:
    with tempfile.TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory).joinpath("investing")
        scraper = InvestingTickerScraper(
            exchange="ucb",
            settings=invest_settings,
            browser=init_chrome(headless=True),
            bearish_path=temp_path,
        )
        data = scraper.scrape()
        assert Path(temp_path).joinpath("investing", "ticker", "ucb").exists()
        assert "historical" in data
