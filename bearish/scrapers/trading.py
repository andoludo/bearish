import re
from itertools import zip_longest
from typing import Any, Dict, List, Literal

import pandas as pd
import unidecode
from bs4 import BeautifulSoup
from bs4.element import Tag
from pydantic import Field, model_validator
from selenium.webdriver.common.by import By

from bearish.scrapers.base import (
    BasePage,
    BaseSettings,
    BaseTickerPage,
    CountryNameMixin,
    _get_country_name_per_enum,
    move_from_left_to_right_border,
)
from bearish.scrapers.type import Locator
from bearish.scrapers.model import HistoricalData
from bearish.scrapers.settings import TradingCountry

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
    country_market: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="overlap-manager-root"]/div/span/div[1]/div/div/div[10]',
    )
    apply_country: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="overlap-manager-root"]/div/div/div[2]/div/div[4]/span/button[2]/span',
    )
    screener_table: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-screener-container"]/div/div/div[2]/div/div/div[2]/div/table/tbody',
    )
    pages_to_read: Dict[str, Locator] = Field(
        default={
            "overview": Locator(by=By.XPATH, value='//*[@id="overview"]/span[1]/span'),
            "perfromance": Locator(
                by=By.XPATH, value='//*[@id="performance"]/span[1]/span'
            ),
            "valuation": Locator(
                by=By.XPATH, value='//*[@id="valuation"]/span[1]/span'
            ),
            "dividends": Locator(
                by=By.XPATH, value='//*[@id="dividends"]/span[1]/span'
            ),
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
            "technicals": Locator(
                by=By.XPATH, value='//*[@id="technicals"]/span[1]/span'
            ),
        }
    )
    candlesticks: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/span/span[2]/button[2]',
    )
    canvas: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[1]/div/div/table/tr[1]/td[2]'
        "/div/canvas[2]",
    )
    open: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[3]/div/div[1]/div/div[1]/div[2]',
    )
    high: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[3]/div/div[1]/div/div[2]/div[2]',
    )
    low: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[3]/div/div[1]/div/div[3]/div[2]',
    )
    close: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[3]/div/div[1]/div/div[4]/div[2]',
    )
    period: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[2]/div/div[2]/button[7]',
    )
    date: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="js-category-content"]/div[2]/div/section/div[1]/div[2]/div[3]/div/div[2]',
    )
    suffixes: List[str] = Field(
        default=[
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
    )


def bs4_read_html(page_source: str) -> list[pd.DataFrame]:
    soup = BeautifulSoup(page_source, "html.parser")
    data = []
    for tr in soup.find("table").find_all("tr"):  # type: ignore
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


class TradingScreenerScraper(BasePage, CountryNameMixin):
    country: Locator
    source: Literal["trading", "investing", "yahoo"] = Field(default="trading")
    settings: TradingSettings = Field(default=TradingSettings())

    def _get_country_name(self) -> str:  # TODO: change to Enum/ literal
        return _get_country_name_per_enum(TradingCountry, self.country)

    @model_validator(mode="before")
    @classmethod
    def url_validator(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        data.update(
            {
                "url": "https://www.tradingview.com/stock-screener/?aff_id=3037&source=StockTrader"
            }
        )
        return data

    def remove_popup(self) -> None:
        self.click(self.settings.pop_up)

    def select_country(self) -> None:
        self.click(self.settings.country_dialog)
        self.click(self.settings.country_market)
        self.click(self.country)
        self.click(self.settings.apply_country)

    def _read_html(self) -> list[pd.DataFrame]:
        return bs4_read_html(self.browser.page_source)

    def scroll_down_and_read_pages(self) -> None:
        for locator in self.settings.pages_to_read.values():
            self.click(locator)
            self.scroll_down_and_read(self.settings.screener_table)

    def _preprocess_tables(self) -> List[Dict[str, Any]]:
        data = pd.concat([table[0] for table in self._tables], axis=1)
        return data.to_dict(orient="records")  # type: ignore

    def _custom_scrape(self) -> List[Dict[str, Any]]:
        self.full_screen()
        self.remove_popup()
        self.select_country()
        self.scroll_down_and_read_pages()
        data = self._preprocess_tables()
        self._encoding = "unicode"
        for data_ in data:
            data_["reference"] = data_["exchange"]
        return data


def find_by_class(div: Tag, partial_text: str) -> list[str]:
    return [
        c.get_text() for c in div.find_all("div", re.compile(rf"\b{partial_text}\b"))
    ]


class TradingTickerScraper(BaseTickerPage):
    exchange: str
    source: Literal["trading", "investing", "yahoo"] = Field(default="trading")
    settings: TradingSettings = Field(default=TradingSettings())

    def _preprocess_tables(self) -> Dict[str, Any]:
        results = {}
        for tables in self._tables:
            for table in tables:
                results.update(table.to_dict())
        return results

    def _read_html(self) -> list[pd.DataFrame]:
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
                full_data[title[0]] = dict(
                    reversed(list(zip_longest(reversed(titles[0]), reversed(values))))
                )
        return [pd.DataFrame(full_data)]

    def _custom_scrape(self) -> Dict[str, Any]:
        return self.read_pages()

    @model_validator(mode="before")
    @classmethod
    def url_validator(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        return data | {
            "url": f"https://www.tradingview.com/symbols/{data['exchange']}",
            "exchange": data["exchange"],
        }

    def read_historical(self) -> HistoricalData:
        self.click(self.settings.period)
        self.click(self.settings.candlesticks)
        self.click(self.settings.canvas)
        low = self.init_visible_element(self.settings.low)
        high = self.init_visible_element(self.settings.high)
        open = self.init_visible_element(self.settings.open)
        close = self.init_visible_element(self.settings.close)
        time = self.init_visible_element(self.settings.date)
        read = lambda: (  # noqa : E731
            time.read(),
            low.read(),
            high.read(),
            open.read(),
            close.read(),
        )  # : E731
        canvas_element = self.get_element(self.settings.canvas)
        x_offset_start = (
            1
            if not self.update
            else int(canvas_element._element.size["width"] * 11 / 12)
        )
        results = move_from_left_to_right_border(
            canvas_element, read, x_offset_start=x_offset_start
        )
        data = {
            "Price": {r[0]: r[4] for r in results if r[0]},
            "High": {r[0]: r[2] for r in results if r[0]},
            "Low": {r[0]: r[1] for r in results if r[0]},
            "Open": {r[0]: r[3] for r in results if r[0]},
        }
        return HistoricalData(**data)

    def read_pages(self) -> Dict[str, Any]:
        historical_data = self.read_historical()
        for suffix in self.settings.suffixes:
            url = self.url + suffix
            self.browser.get(url)
            self.read_current_page(pause=5)
        data = self._preprocess_tables()
        data.update({"historical": historical_data.model_dump()})
        return data
