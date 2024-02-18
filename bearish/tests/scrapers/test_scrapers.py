import json
import logging
from pathlib import Path

from bearish.scrapers.main import Country, DataSource, Scraper

logger = logging.getLogger(__name__)


def test_investing_main_scraper() -> None:
    scraper = Scraper(source=DataSource.investing, country=Country.belgium)
    scraper.scrape(skip_existing=False)


def test_investing_main_scraper_france() -> None:
    scraper = Scraper(source=DataSource.investing, country=Country.belgium)
    scraper.scrape(skip_existing=False)


def test_investing_main_scraper_germany() -> None:
    scraper = Scraper(source=DataSource.investing, country=Country.germany)
    scraper.scrape(skip_existing=False)


def test_investing_main_scraper_db_json() -> None:
    scraper = Scraper(source=DataSource.investing, country=Country.belgium)
    db_json = scraper.create_db_json()
    scraper = Scraper(source=DataSource.investing, country=Country.france)
    db_json += scraper.create_db_json()
    f = Path("/home/aan/Documents/bullish/data/db_json.json")
    f.touch(exist_ok=True)
    with f.open(mode="w") as p:
        json.dump(db_json, p, indent=4)


def test_trading_main_scraper() -> None:
    scraper = Scraper(source=DataSource.trading, country=Country.belgium)
    scraper.scrape()
