import json
import logging
from pathlib import Path

import pytest

from bearish.scrapers.main import DataSource, Scraper

logger = logging.getLogger(__name__)

@pytest.skip("Too slow")
def test_investing_main_scraper() -> None:
    scraper = Scraper(source=DataSource.investing, country="belgium")
    scraper.scrape(skip_existing=False)

@pytest.skip("Too slow")
def test_investing_main_scraper_france() -> None:
    scraper = Scraper(source=DataSource.investing, country="france")
    scraper.scrape(skip_existing=False)

@pytest.skip("Too slow")
def test_investing_main_scraper_germany() -> None:
    scraper = Scraper(source=DataSource.investing, country="germany")
    scraper.scrape(skip_existing=False)

@pytest.skip("Too slow")
def test_investing_main_scraper_db_json() -> None:
    scraper = Scraper(source=DataSource.investing, country="belgium")
    db_json = scraper.create_db_json()
    scraper = Scraper(source=DataSource.investing, country="france")
    db_json += scraper.create_db_json()
    f = Path("/home/aan/Documents/bullish/data/db_json.json")
    f.touch(exist_ok=True)
    with f.open(mode="w") as p:
        json.dump(db_json, p, indent=4)

@pytest.skip("Too slow")
def test_trading_main_scraper() -> None:
    scraper = Scraper(source=DataSource.trading, country="belgium")
    scraper.scrape()
