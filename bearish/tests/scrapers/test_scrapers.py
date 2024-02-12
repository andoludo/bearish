import json
import logging

from bearish.scrapers.investing import (
    InvestingCountry,
    InvestingScreenerScraper,
    InvestingTickerScraper,
)
from bearish.scrapers.main import Country, Scraper, DataSource

from bearish.scrapers.trading import (
    TradingCountry,
    TradingScreenerScraper,
    TradingTickerScraper,
)


logger = logging.getLogger(__name__)

def test_investing_screener_scraper_belgium_check_path():
    scraper = InvestingScreenerScraper(country=InvestingCountry.belgium, bearish_path = "/tmp/")
    scraper.go()
    data = scraper.scrape()

def test_investing_screener_scraper_belgium():
    scraper = InvestingScreenerScraper(country=InvestingCountry.belgium)
    scraper.go()
    data = scraper.scrape()
    assert len(data.columns) == 80
    assert len(data) >= 100

def test_investing_screener_scraper_germany():
    scraper = InvestingScreenerScraper(country=InvestingCountry.germany)
    scraper.go()
    data = scraper.scrape()
    assert len(data.columns) == 80
    assert len(data) >= 100
def test_investing_screener_scraper_france():
    scraper = InvestingScreenerScraper(country=InvestingCountry.france)
    scraper.go()
    data = scraper.scrape()
    assert len(data.columns) == 80
    assert len(data) >= 100


def test_investing_ticker_scraper():
    scraper = InvestingTickerScraper(exchange="ucb")
    scraper.go()
    data = scraper.scrape()
    assert "historical" in data

from pathlib import Path

def remove_chrome_files_in_tmp():
    tmp_path = Path('/tmp')  # Update the path if your tmp directory is in a different location

    # Iterate through all files in the tmp directory that start with ".com.google.Chrome"
    for file_path in tmp_path.glob('.com.google.Chrome*'):
        try:
            # Remove the file
            file_path.unlink()
            print(f"Removed: {file_path}")
        except Exception as e:
            print(f"Error removing {file_path}: {e}")
def test_investing_main_scraper():
    for coutry in [Country.belgium, Country.france]:
        try:
            scraper = Scraper(source=DataSource.investing, country=coutry)
            scraper.scrape(skip_existing=False)
            remove_chrome_files_in_tmp()
        except:
            pass

def test_investing_main_scraper_france():
    scraper = Scraper(source=DataSource.investing, country=Country.belgium)
    scraper.scrape(skip_existing=False)

def test_investing_main_scraper_germany():
    scraper = Scraper(source=DataSource.investing, country=Country.germany)
    scraper.scrape(skip_existing=False)


def test_get_a_symbol():
    scraper = Scraper(source=DataSource.investing, country=Country.belgium)
    scraper.scrape(skip_existing=False, symbols=["ACKB"])
def test_investing_main_scraper_db_json():
    scraper = Scraper(source=DataSource.investing, country=Country.belgium)
    db_json = scraper.create_db_json()
    scraper = Scraper(source=DataSource.investing, country=Country.france)
    db_json += scraper.create_db_json()
    f = Path("/home/aan/Documents/stocks/data/db_json.json")
    f.touch(exist_ok=True)
    with f.open(mode="w") as p:
        json.dump(db_json, p, indent=4)

def test_trading_screener_belgium():
    scraper = TradingScreenerScraper(country=TradingCountry.belgium)
    data = scraper.scrape()


def test_trading_screener_france():
    scraper = TradingScreenerScraper(country=TradingCountry.france)
    data = scraper.scrape()


def test_trading_ticker():
    scraper = TradingTickerScraper(exchange="EURONEXT-ABI")
    data = scraper.scrape()
    assert "historical" in data


def test_trading_main_scraper():
    scraper = Scraper(source=DataSource.trading, country=Country.france)
    scraper.scrape()
