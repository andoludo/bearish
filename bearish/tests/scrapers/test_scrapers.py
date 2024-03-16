import json
import logging
import tempfile
from pathlib import Path

import pytest

from bearish.scrapers.investing import InvestingSettings, UpdateInvestingSettings
from bearish.scrapers.main import DataSource, Scraper

logger = logging.getLogger(__name__)

@pytest.mark.local_only
def test_investing_main_scraper(invest_settings: InvestingSettings) -> None:
    with tempfile.TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory).joinpath("investing", "scraper")
        scraper = Scraper(
            source=DataSource.investing,
            country="belgium",
            bearish_path=temp_path,
            settings=invest_settings,
        )
        scraper.scrape(skip_existing=False, symbols=["UCB"], first_page_only=True)
        assert Path(temp_path).joinpath("investing", "screener", "belgium").exists()
        assert Path(temp_path).joinpath("investing", "ticker", "ucb").exists()
        db_json = scraper.create_db_json(symbols=["UCB"])
        assert len(db_json) == 1
        assert "historical" in db_json[0]

@pytest.mark.local_only
def test_investing_db_json_update(
    update_invest_settings: UpdateInvestingSettings,
) -> None:
    db_json_path = Path(__file__).parent.joinpath("data", "db.json")
    with tempfile.TemporaryDirectory() as temp_directory:
        temp_path = Path(temp_directory).joinpath("investing", "scraper")
        scraper = Scraper(
            source=DataSource.investing,
            country="belgium",
            bearish_path=temp_path,
            settings=update_invest_settings,
        )
        scraper.update_db_json(db_json_path)


@pytest.mark.skip("Too slow")
def test_investing_main_scraper_france(invest_settings: InvestingSettings) -> None:
    scraper = Scraper(
        source=DataSource.investing, country="france", settings=invest_settings
    )
    scraper.scrape(skip_existing=False)


@pytest.mark.skip("Too slow")
def test_investing_main_scraper_germany(invest_settings: InvestingSettings) -> None:
    scraper = Scraper(
        source=DataSource.investing, country="germany", settings=invest_settings
    )
    scraper.scrape(skip_existing=False)


@pytest.mark.skip("Too slow")
def test_investing_main_scraper_db_json(invest_settings: InvestingSettings) -> None:
    scraper = Scraper(
        source=DataSource.investing, country="belgium", settings=invest_settings
    )
    db_json = scraper.create_db_json()
    scraper = Scraper(
        source=DataSource.investing, country="france", settings=invest_settings
    )
    db_json += scraper.create_db_json()
    f = Path("/home/aan/Documents/bullish/data/db_json.json")
    f.touch(exist_ok=True)
    with f.open(mode="w") as p:
        json.dump(db_json, p, indent=4)
