import logging
import tempfile
from pathlib import Path

import pytest
from pytest_mongo import factories

from bearish.scrapers.base import init_chrome
from bearish.scrapers.investing import (
    InvestingScreenerScraper,
    InvestingSettings,
    InvestingTickerScraper,
)
from bearish.scrapers.mongodb import MongoDBCLient
from bearish.scrapers.settings import InvestingCountry

logger = logging.getLogger(__name__)
# sudo apt-get update
# sudo apt-get install -y mongodb
# sudo apt-get install -y mongodb-org
# https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/
@pytest.fixture
def invest_settings() -> InvestingSettings:
    return InvestingSettings(
        suffixes=[
            "-income-statement",
        ]
    )

mongo_my_proc = factories.mongo_proc(
    port=None, logsdir='/tmp')
# mongo_my = factories.mongodb('mongo_my_proc')
def test_investing_screener_belgium(mongo_my_proc, invest_settings: InvestingSettings) -> None:
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
        MongoDBCLient("screener").create_many(data)
        assert data
        assert Path(temp_path).joinpath("investing", "screener", "belgium").exists()