import re
from enum import Enum
from itertools import zip_longest
from typing import List

import pandas as pd
import unidecode
from bs4 import BeautifulSoup
from pydantic import Field, model_validator
from selenium.webdriver.common.by import By

from bearish.scrapers.base import BasePage, BaseSettings, BaseTickerPage, Locator

TRADING = "trading"


class TradingSettings(BaseSettings):
    pop_up: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="overlap-manager-root"]/div[2]/div/div[2]/div/div/div[1]/button',
    )
    country_dialog: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-screener-container"]/div/div/div[1]/div[2]/div[1]/div[2]/div/div[1]/div',
    )
    apply_country: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="overlap-manager-root"]/div/div/div[2]/div/div[4]/span/button[2]/span',
    )
    screener_table: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-screener-container"]/div/div/div[2]/div/div/div[2]/div/table/tbody',
    )
    pages_to_read: dict[str, Locator] = {
        "overview": Locator(by=By.XPATH, value='//*[@id="overview"]/span[1]/span'),
        "perfromance": Locator(
            by=By.XPATH, value='//*[@id="performance"]/span[1]/span'
        ),
        "valuation": Locator(by=By.XPATH, value='//*[@id="valuation"]/span[1]/span'),
        "dividends": Locator(by=By.XPATH, value='//*[@id="dividends"]/span[1]/span'),
        "profitability": Locator(
            by=By.XPATH, value='//*[@id="profitability"]/span[1]/span'
        ),
        "cash_flow": Locator(by=By.XPATH, value='//*[@id="cashFlow"]/span[1]/span'),
        "income_statement": Locator(
            by=By.XPATH, value='//*[@id="incomeStatement"]/span[1]/span'
        ),
        "balance_sheet": Locator(
            by=By.XPATH, value='//*[@id="balanceSheet"]/span[1]/span'
        ),
        "technicals": Locator(by=By.XPATH, value='//*[@id="technicals"]/span[1]/span'),
    }
    canvas: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[1]/div/div/table/tr[1]/td[2]/div/canvas[2]',
    )
    tooltip: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[3]/div/div[1]/div/div/span[2]',
    )
    period: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[2]/div/div[2]/button[7]',
    )
    date: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[3]/div/div[2]',
    )
    suffixes: List[str] = [
        # "/financials-overview/",
        "/financials-income-statement/?statements-period=FY",
        "/financials-balance-sheet/?statements-period=FY",
        "/financials-cash-flow/?statements-period=FY",
        "/financials-statistics-and-ratios/",
        "/financials-dividends/",
        "/financials-earnings/?earnings-period=FY&revenues-period=FY",
        "/financials-revenue/",
        "/news/",
        "/technicals/",
        "/forecast/",
    ]


class TradingCountry(Enum):
    germany: Locator = Locator(by=By.XPATH, value='//*[@id="source-item-2-0-5"]/div')
    belgium: Locator = Locator(by=By.XPATH, value='//*[@id="source-item-2-0-1"]/div')
    france: Locator = Locator(by=By.XPATH, value='//*[@id="source-item-2-0-10"]/div')
    us: Locator = Locator(
        by=By.XPATH, value='//*[@id="source-item-1-0-0"]/div/div[2]/div[2]'
    )


def bs4_read_html(page_source):
    soup = BeautifulSoup(page_source, "html.parser")
    data = []
    for tr in soup.find("table").find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            row = [td.text for td in tr.find_all("th")] + ["name", "exchange"]
        else:
            row = (
                [tds[0].find("a").text]
                + [td.text for td in tds[1:]]
                + [tds[0].find("sup").text, tds[0].find("a").get("href").split("/")[2]]
            )
        data.append(row)
    return [pd.DataFrame(data[1:], columns=data[0])]


class TradingScreenerScraper(BasePage):
    country: TradingCountry
    source: str = TRADING
    settings: TradingSettings = Field(default=TradingSettings())

    def _get_country_name(self):
        return self._get_country_name_per_enum(TradingCountry, self.country)

    @model_validator(mode="before")
    def url_validator(cls, data):
        data.update(
            {
                "url": "https://www.tradingview.com/stock-screener/?aff_id=3037&source=StockTrader"
            }
        )
        return data

    def remove_popup(self):
        self.click(self.settings.pop_up)

    def select_country(self):
        self.click(self.settings.country_dialog)
        self.click(self.country)
        self.click(self.settings.apply_country)

    def _read_html(self):
        return bs4_read_html(self.browser.page_source)

    def scroll_down_and_read_pages(self):
        for _, locator in self.settings.pages_to_read.items():
            self.click(locator)
            self.scroll_down_and_read(self.settings.screener_table)

    def _preprocess_tables(self):
        return pd.concat([table[0] for table in self._tables], axis=1)

    def _custom_scrape(self):
        self.full_screen()
        self.remove_popup()
        self.select_country()
        self.scroll_down_and_read_pages()
        data = self._preprocess_tables()
        self._encoding = "unicode"
        data = data.to_dict(orient="records")
        for data_ in data:
            data_["reference"] = data_["exchange"]
        return data


def find_by_class(div, partial_text):
    return [
        c.get_text() for c in div.find_all("div", re.compile(rf"\b{partial_text}\b"))
    ]


class TradingTickerScraper(BaseTickerPage):
    exchange: str
    source: str = TRADING
    settings: TradingSettings = Field(default=TradingSettings())

    def _preprocess_tables(self):
        results = {}
        for table in self._tables:
            results.update(table.to_dict())
        return results

    def _read_html(self):
        BeautifulSoup(unidecode.unidecode(self.browser.page_source), "html5lib")
        soup = BeautifulSoup(
            unidecode.unidecode(self.browser.page_source), "html5lib"
        )  # Why two times?
        soup.prettify()
        divs = soup.find_all("div", {"data-name": True})
        titles = [
            find_by_class(div, "value")
            for div in soup.find_all("div", re.compile(r"\blargeHeight\b"))
        ]
        full_data = {}
        for div in divs:
            values = find_by_class(div, "value")
            title = [
                c.get_text() for c in div.find_all("span", re.compile(r"\btitleText\b"))
            ]
            if values and title and titles:
                full_data[title[0]] = {
                    date: value
                    for date, value in reversed(
                        list(zip_longest(reversed(titles[0]), reversed(values)))
                    )
                }
        return pd.DataFrame(full_data)

    def _custom_scrape(self):
        return self.read_pages()

    @model_validator(mode="before")
    def url_validator(cls, data):
        return {
            "url": f"https://www.tradingview.com/symbols/{data['exchange']}",
            "exchange": data["exchange"],
        }

    def read_historical(self):
        self.click(self.settings.period)
        self.click(self.settings.canvas)
        tool_tip = self.init_visible_element(self.settings.tooltip)
        time = self.init_visible_element(self.settings.date)
        read = lambda: (time.read(), tool_tip.read())
        canvas_element = self.get_element(self.settings.canvas)
        results = self.move_from_left_to_right_border(canvas_element, read)
        historical_data = {
            "historical": {"Price": {r[0]: r[1] for r in results if r[0]}}
        }
        return historical_data

    def read_pages(self):
        historical_data = self.read_historical()
        for suffix in self.settings.suffixes:
            url = self.url + suffix
            self.browser.get(url)
            self.read_current_page(pause=5)
        data = self._preprocess_tables()
        data.update(historical_data)
        return data
