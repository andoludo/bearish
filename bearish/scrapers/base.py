import abc
import glob
import os
import time
from datetime import datetime
from functools import cached_property, partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union

import pandas as pd
import simplejson
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, computed_field
from selenium.common import MoveTargetOutOfBoundsException, TimeoutException
from selenium.webdriver import ActionChains, Chrome, Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.webdriver import WebDriver as BaseWebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait


from bearish.scrapers.model import HistoricalData


from bearish.scrapers.settings import TradingCountry, InvestingCountry
from bearish.scrapers.type import Locator


class BaseElement:
    def __init__(
        self,
        browser: Chrome,
        locator: Locator,
        expected_condition_function: Callable[
            [tuple[str, str]],
            Callable[
                [BaseWebDriver | WebDriver | WebElement], Literal[False] | WebElement
            ],
        ] = expected_conditions.presence_of_element_located,
    ) -> None:
        self._browser = browser
        self._locator = locator
        self._element: WebElement = WebDriverWait(browser, 20).until(
            expected_condition_function(locator.to_tuple())
        )

    def click(self) -> None:
        self._element.click()

    def write_simple(self, value: str) -> None:
        self._element.clear()
        self._element.send_keys(value)

    def write(self, value: str) -> None:
        self.write_simple(value)
        self._element.send_keys(value)  # Why two times?

    def scroll_down(self) -> None:
        current_height = self._element.size["height"]
        previous_height = None
        while previous_height != current_height:
            ActionChains(self._browser).send_keys_to_element(
                self._element, Keys.PAGE_DOWN
            ).pause(1).perform()
            time.sleep(1)
            previous_height = current_height
            current_height = self._element.size["height"]

    def move_by_x_offset_from_left_border(self, x_offset: int) -> None:

        x_offset = x_offset - (self._element.rect["width"]) / 2
        ActionChains(self._browser).move_to_element_with_offset(
            self._element, x_offset, 0
        ).perform()

    def width(self) -> int:
        return int(self._element.rect["width"])

    def read(self) -> str:
        return self._element.text.strip()


def move_by_x_offset_from_left_border(element: BaseElement, x_offset: int) -> bool:
    right_border = x_offset > element.width()
    if not right_border:
        element.move_by_x_offset_from_left_border(x_offset)
    return right_border


def init_chrome(load_strategy_none: bool = False, headless: bool = False) -> Chrome:
    option = Options()
    if headless:
        option.add_argument("--headless")
    if load_strategy_none:
        option.page_load_strategy = "none"
    return Chrome(options=option)


def bearish_path_fun() -> Path:
    current_working_directory = Path.cwd()
    bearish_path = current_working_directory / "bearish"
    bearish_path.mkdir(parents=True, exist_ok=True)
    return bearish_path


class BaseSettings(BaseModel):
    ...


def clean_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    cleaned_data = {}
    for name, value in data.items():
        if isinstance(value, dict):
            cleaned_data[str(name)] = clean_dict(value)
        else:
            cleaned_data[str(name)] = value
    return cleaned_data


def _replace_values(
    tables: list[pd.DataFrame], replace_values: Dict[str, str]
) -> list[pd.DataFrame]:
    def find_and_replace(
        element: float | str | int, replace_values: Dict[str, str]
    ) -> float | str | int:
        for old_value, new_value in replace_values.items():
            if element == old_value:
                return new_value
        return element

    new_tables = []
    if not replace_values:
        return tables
    for table in tables:
        table_ = table.applymap(  # type: ignore
            partial(find_and_replace, replace_values=replace_values)
        )
        new_tables.append(table_)
    return new_tables


def move_from_left_to_right_border(
    element: BaseElement,
    action: Callable[[], Tuple[str, str, str, str, str]],
    x_offset_start: int = 1,
) -> List[Tuple[str, str, str, str, str]]:
    x_offset = x_offset_start
    actions = []
    right_border = False
    while not right_border:
        try:
            right_border = move_by_x_offset_from_left_border(element, x_offset=x_offset)
            if not right_border:
                actions.append(action())
        except (MoveTargetOutOfBoundsException, TimeoutException):
            break
        x_offset += 1
    return actions


def _get_country_name_per_enum(enum: Type[TradingCountry] | Type[InvestingCountry], country: Locator | int) -> str:
    return next(
        k
        for k, v in enum.__dict__.items()
        if isinstance(v, (Locator, int)) and v == country
    )


def _clean(
    data: List[Dict[str, Any]] | Dict[str, Any]
) -> List[Dict[str, Any]] | Dict[str, Any]:
    if isinstance(data, list):
        return [clean_dict(data_) for data_ in data]
    else:
        return clean_dict(data)


class CountryNameMixin:
    @abc.abstractmethod
    def _get_country_name(self) -> str:
        ...



class BasePage(BaseModel):
    url: str
    source: Literal["trading", "investing", "yahoo"]
    settings: BaseSettings
    browser: WebDriver = Field(default_factory=init_chrome, description="")
    bearish_path: Path = Field(default_factory=bearish_path_fun, description="")
    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=True)
    _tables = PrivateAttr(default_factory=list)
    _skip_existing = PrivateAttr(default=True)
    _encoding = PrivateAttr(default=None)

    def go(self) -> None:
        self.browser.get(self.url)

    def pause(self, seconds: int) -> None:
        ActionChains(self.browser).pause(seconds).perform()

    def refresh(self) -> None:
        self.browser.refresh()

    def full_screen(self) -> None:
        self.browser.fullscreen_window()

    def click(self, locator: Locator) -> None:
        BaseElement(self.browser, locator).click()

    def init_visible_element(self, locator: Locator) -> BaseElement:
        element = BaseElement(
            self.browser,
            locator,
            expected_condition_function=expected_conditions.visibility_of_element_located,
        )
        return element

    def get_element(self, locator: Locator) -> BaseElement:
        return BaseElement(self.browser, locator)

    def write(self, locator: Locator, value: str) -> None:
        BaseElement(self.browser, locator).write(value)

    def scroll_down(self, locator: Locator) -> None:
        self.wait_until_ready(locator).scroll_down()

    def scroll_down_and_read(self, locator: Locator) -> None:
        self.scroll_down(locator)
        self.read_current_page()

    def _read_html(self) -> list[pd.DataFrame]:
        return pd.read_html(self.browser.page_source)

    def read_current_page(
        self, pause: int = 1, replace_values: Optional[Dict[str, str]] = None
    ) -> None:
        self.pause(pause)
        tables = self._read_html()
        new_tables = _replace_values(tables, replace_values=replace_values or {})
        self._tables.append(new_tables)

    @abc.abstractmethod
    def _preprocess_tables(
        self,
    ) -> Union[
        List[Dict[str, Any]], Dict[str, Any]
    ]:  # TODO: anti-pattern needs to be changed
        ...

    @abc.abstractmethod
    def _custom_scrape(
        self,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:  # anti pattern -> code is wrong
        ...

    def _exist_files_in_folder(self) -> bool:
        return bool(
            self.folder_path.exists()
            and self.folder_path.is_dir()
            and len(list(self.folder_path.iterdir()))
        )

    def get_stored_raw(self) -> Path:
        if self._skip_existing and self._exist_files_in_folder():
            return self._get_latest_file()
        else:
            return self.path

    def scrape(
        self, skip_existing: bool = True
    ) -> Optional[
        Dict[str, Any] | list[Dict[str, Any]]
    ]:  # anti pattern -> code is wrong
        self._skip_existing = skip_existing
        if self._skip_existing and self._exist_files_in_folder():
            return None
        self.go()
        records = self._custom_scrape()
        self.to_json(data=records)
        return records

    @computed_field  # type: ignore
    @cached_property
    def folder_path(self) -> Path:

        path = (
            self.bearish_path
            / self.source
            / type(self)
            .__name__.lower()
            .replace(self.source, "")
            .replace("scraper", "")
        )

        if hasattr(self, "country"):

            path = path / self._get_country_name()
        elif hasattr(self, "exchange"):
            path = path / self.exchange
        else:
            pass
        return path

    @computed_field  # type: ignore
    @cached_property
    def path(self) -> Path:
        file_name = f"{datetime.now().strftime('%Y_%m_%d_%H_%M')}.json"
        self.folder_path.mkdir(parents=True, exist_ok=True)
        path = self.folder_path / file_name
        return path

    def _get_latest_file(self) -> Path:
        list_of_files = glob.glob(
            f"{self.folder_path}/*"
        )  # * means all if need specific format then *.csv
        return Path(max(list_of_files, key=os.path.getctime))

    def to_json(self, data: Dict[str, Any] | List[Dict[str, Any]]) -> None:
        self.path.touch(exist_ok=True)
        with self.path.open(mode="w") as f:
            simplejson.dump(
                _clean(data), f, indent=4, ignore_nan=True, encoding=self._encoding
            )

    def wait_until_ready(self, locator: Locator) -> BaseElement:
        return BaseElement(
            self.browser,
            locator,
            expected_condition_function=expected_conditions.visibility_of_element_located,
        )

    def close(self) -> None:
        self.browser.close()


class BaseTickerPage(BasePage):
    update: bool = False

    @abc.abstractmethod
    def read_historical(self) -> HistoricalData:
        ...
