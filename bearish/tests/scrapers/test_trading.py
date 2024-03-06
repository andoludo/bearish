import logging
import tempfile
from pathlib import Path

import pytest
from selenium.webdriver.common.by import By

from bearish.scrapers.settings import TradingCountry
from bearish.scrapers.trading import (
    TradingScreenerScraper,
    TradingSettings,
    TradingTickerScraper,
)
from bearish.scrapers.type import Locator

logger = logging.getLogger(__name__)


@pytest.fixture
def trading_settings() -> TradingSettings:
    return TradingSettings(
        pages_to_read={
            "overview": Locator(by=By.XPATH, value='//*[@id="overview"]/span[1]/span')
        },
        suffixes=[
            "/financials-income-statement/?statements-period=FY",
        ],
    )


def test_trading_screener_belgium(trading_settings: TradingSettings) -> None:
    with tempfile.TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory).joinpath("trading_view")
        scraper = TradingScreenerScraper(
            country=TradingCountry.belgium,
            settings=trading_settings,
            bearish_path=temp_path,
        )
        data = scraper.scrape()
        assert Path(temp_path).joinpath("trading", "screener", "belgium").exists()
        assert data


def test_trading_ticker(trading_settings: TradingSettings) -> None:
    with tempfile.TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory).joinpath("trading_view")
        scraper = TradingTickerScraper(
            exchange="EURONEXT-ABI",
            bearish_path=temp_path,
            update=True,
            settings=trading_settings,
        )
        data = scraper.scrape()
        assert Path(temp_path).joinpath("trading", "ticker", "EURONEXT-ABI").exists()
        assert "historical" in data
