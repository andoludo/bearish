import logging
import tempfile
from pathlib import Path

import pytest

from bearish.scrapers.base import init_chrome
from bearish.scrapers.investing import (
    InvestingScreenerScraper,
    InvestingSettings,
    InvestingTickerScraper,
)
from bearish.scrapers.settings import InvestingCountry

logger = logging.getLogger(__name__)


@pytest.fixture
def invest_settings() -> InvestingSettings:
    return InvestingSettings(
        suffixes=[
            "-income-statement",
        ]
    )


def test_investing_screener_belgium(invest_settings: InvestingSettings) -> None:
    with tempfile.TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory).joinpath("investing")
        browser = init_chrome(load_strategy_none=True, headless=True)
        scraper = InvestingScreenerScraper(
            browser=browser,
            country=InvestingCountry.belgium,
            settings=invest_settings,
            bearish_path=temp_path,
        )
        data = scraper.scrape()
        assert data
        assert Path(temp_path).joinpath("investing", "screener", "belgium").exists()


def test_investing_screener_france(invest_settings: InvestingSettings) -> None:
    with tempfile.TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory).joinpath("investing")
        browser = init_chrome(load_strategy_none=True, headless=True)
        scraper = InvestingScreenerScraper(
            browser=browser,
            country=InvestingCountry.france,
            settings=invest_settings,
            bearish_path=temp_path,
        )
        data = scraper.scrape()
        assert data
        assert Path(temp_path).joinpath("investing", "screener", "france").exists()


def test_investing_ticker_scraper(invest_settings: InvestingSettings) -> None:
    with tempfile.TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory).joinpath("investing")
        scraper = InvestingTickerScraper(
            exchange="ucb",
            settings=invest_settings,
            browser=init_chrome(load_strategy_none=True, headless=True),
            bearish_path=temp_path,
        )
        data = scraper.scrape()
        assert Path(temp_path).joinpath("investing", "ticker", "ucb").exists()
        assert "historical" in data
