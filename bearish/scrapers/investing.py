import contextlib
from enum import Enum
from functools import partial
from typing import Any, Dict, List, Literal

import pandas as pd
from pydantic import Field, model_validator
from selenium.common import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    TimeoutException,
)
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from bearish.scrapers.base import (
    BasePage,
    BaseSettings,
    BaseTickerPage,
    CountryNameMixin,
    Locator,
    _get_country_name_per_enum,
    init_chrome,
)
from bearish.scrapers.model import HistoricalData

COLUMNS_LENGTH = 2


class InvestingSettings(BaseSettings):
    pause: int = 5
    one_trust_button: Locator = Locator(by=By.ID, value="onetrust-button-group")
    date_picker: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="__next"]/div[2]/div[2]/div[2]/div[1]/div[2]/div[2]/div[2]/div[2]/div',
    )
    start_date_input: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="__next"]/div[2]/div[2]/div[2]/div[1]/div[2]/div[2]/div[2]/div[3]/div[1]/div[1]/input',
    )
    date_picker_apply: Locator = Locator(
        by=By.XPATH,
        value='//*[@id="__next"]/div[2]/div[2]/div[2]/div[1]/div[2]/div[2]/div[2]/div[3]/div[2]/span[2]',
    )
    statement_annual_button: Locator = Locator(
        by=By.XPATH, value='//*[@id="leftColumn"]/div[8]/div[1]/a[1]'
    )
    start_date: str = "02-02-2018"
    suffixes: list[str] = Field(
        default=[
            "-income-statement",
            "-balance-sheet",
            "-cash-flow",
            "-ratios",
            "-dividends",
            "-earnings",
        ]
    )
    value_replacements: dict[str, str] = Field(
        default={
            "Total Revenue": "Total Revenue quarterly",
            "Cost of Revenue, Total": "Cost of Revenue, Total quarterly",
            "Gross Profit": "Gross Profit quarterly",
            "Total Operating Expenses": "Total Operating Expenses quarterly",
            "Operating Income": "Operating Income quarterly",
            "Net Income Before Taxes": "Net Income Before Taxes quarterly",
            "Net Income After Taxes": "Net Income After Taxes quarterly",
            "Net Income": "Net Income quarterly",
            "Revenue growthTTM YoY": "Revenue growthTTM YoY quarterly",
        }
    )

    def get_statements_urls(self, exchange: str) -> List[str]:

        return [
            f"https://www.investing.com/equities/{exchange}" + suffix
            for suffix in self.suffixes
        ]


class InvestingCountry(Enum):
    germany: int = 17
    france: int = 22
    belgium: int = 34
    usa: int = 5


class InvestingScreenerScraper(BasePage, CountryNameMixin):
    country: int
    settings: InvestingSettings = Field(default=InvestingSettings())
    source: Literal["trading", "investing", "yahoo"] = "investing"
    browser: WebDriver = Field(
        default_factory=lambda: init_chrome(load_strategy_none=True, headless=True),
        description="",
    )

    def _get_country_name(self) -> str:
        return _get_country_name_per_enum(InvestingCountry, self.country)

    @model_validator(mode="before")
    @classmethod
    def url_validator(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        return data | {
            "url": f"https://www.investing.com/stock-screener/?sp=country::{data['country'].value}|"
            f"sector::a|industry::a|equityType::"
            "a|exchange::14|eq_pe_ratio::-670.36,370.54%3Ceq_market_cap;1",
            "country": data["country"],
        }

    def click_one_trust_button(self) -> None:
        self.click(self.settings.one_trust_button)

    def _preprocess_tables(self) -> List[Dict[str, Any]]:
        dataframe = pd.concat([table[-1] for table in self._tables])
        new_dataframe = pd.DataFrame()
        for columns_ in dataframe.columns:
            if isinstance(columns_, tuple) and len(columns_) == COLUMNS_LENGTH:
                for i, _ in enumerate(columns_):
                    new_series = dataframe[columns_].apply(
                        partial(lambda x, index: x[index], index=i)
                    )
                    if not new_series.any():
                        continue
                    column_name = f"{columns_[0]}_{i}" if i else columns_[0]
                    new_dataframe[column_name] = new_series
            else:
                new_dataframe[columns_] = dataframe[columns_]
        new_dataframe = new_dataframe.rename(columns={"Name_1": "reference"})
        return new_dataframe.to_dict(orient="records")  # type: ignore

    def _read_html(self) -> List[pd.DataFrame]:
        return pd.read_html(self.browser.page_source, extract_links="all")

    def read_next_pages(self) -> None:
        page_number = 2
        while True:
            try:
                self.click(Locator(by=By.LINK_TEXT, value=str(page_number)))
                self.read_current_page(pause=self.settings.pause)
            except (ElementClickInterceptedException, TimeoutException):
                break
            page_number += 1

    def _custom_scrape(self) -> list[dict[str, Any]]:
        self.click_one_trust_button()
        self.read_current_page(pause=self.settings.pause)
        self.read_next_pages()
        return self._preprocess_tables()


class InvestingTickerScraper(BaseTickerPage):
    exchange: str
    source: Literal["trading", "investing", "yahoo"] = "investing"
    settings: InvestingSettings = Field(default=InvestingSettings())
    browser: WebDriver = Field(
        default_factory=lambda: init_chrome(load_strategy_none=True, headless=False),
        description="",
    )

    @model_validator(mode="before")
    @classmethod
    def url_validator(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        return data | {
            "url": f"https://www.investing.com/equities/{data['exchange']}-historical-data",
            "exchange": data["exchange"],
        }

    def click_one_trust_button(self) -> None:
        with contextlib.suppress(TimeoutException):
            self.click(self.settings.one_trust_button)

    def read_historical(self, pause: int = 1) -> HistoricalData:
        self.click(self.settings.date_picker)
        self.write(self.settings.start_date_input, self.settings.start_date)
        self.click(self.settings.date_picker_apply)
        self.pause(pause)
        datas = self._read_html()
        data = next(data for data in datas if "Price" in data.columns)
        data.index = data["Date"]  # type: ignore
        return HistoricalData(**data.to_dict())  # type: ignore

    def _preprocess_tables(self) -> Dict[str, Any]:
        tables = [table for tables in self._tables for table in tables]
        records = {}
        for table in tables:
            table.index = table.iloc[:, 0]
            records.update(table.T.to_dict())
        return records

    def _custom_scrape(self) -> Dict[str, Any]:
        self.click_one_trust_button()
        historical_data = {
            "historical": self.read_historical(pause=self.settings.pause).model_dump()
        }
        for url in self.settings.get_statements_urls(self.exchange):
            self.browser.get(url)
            self.read_current_page(
                pause=self.settings.pause,
                replace_values=self.settings.value_replacements,
            )
            try:
                self.click(self.settings.statement_annual_button)
                self.read_current_page(pause=self.settings.pause)
            except (ElementNotInteractableException, ElementClickInterceptedException):
                pass
        records = self._preprocess_tables()
        records.update(historical_data)
        return records
