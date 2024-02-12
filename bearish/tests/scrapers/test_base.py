from pathlib import Path

import pytest
from selenium.webdriver.common.by import By

from bearish.scrapers.base import BasePage, Locator


def test_save_test_pages():
    urls = [
        "https://the-internet.herokuapp.com/tables",
        "https://the-internet.herokuapp.com/challenging_dom",
        "https://seleniumbase.io/demo_page",
    ]
    for url in urls:
        base_page = BasePage(url=url)
        base_page.go()
        path = Path(__file__).parent.joinpath("data", f"{url.split('/')[-1]}.html")
        with path.open("w") as file:
            file.write(base_page.browser.page_source)


def test_base_page():
    base_page = BasePage(
        url="file:///home/aan/Documents/stocks/tests/scrapers/data/web_test_01.html"
    )
    base_page.go()
    base_page.click(
        Locator(by=By.XPATH, value='//*[@id="yui_3_17_2_1_1705796758268_68"]/a')
    )
    a = 12


def get_test_url(file: str):
    return f'file://{Path(__file__).parent.joinpath("data", file)}'


@pytest.fixture
def infinite_scroll():
    return get_test_url("infinite_scroll.html")


def test_scroll_down(infinite_scroll):
    base_page = BasePage(url="https://the-internet.herokuapp.com/infinite_scroll")
    base_page.go()
    base_page.scroll_down(Locator(by=By.XPATH, value='//*[@id="content"]/div'))
    a = 12
