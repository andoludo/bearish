import abc
import glob
import os
import time
from datetime import datetime
from enum import Enum
from functools import cached_property, partial
from pathlib import Path
from typing import Callable, Optional, Tuple

import pandas as pd
import simplejson
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, computed_field
from selenium.common import MoveTargetOutOfBoundsException, TimeoutException
from selenium.webdriver import ActionChains, Chrome, Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait


class Locator(BaseModel):
    by: str
    value: str
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def to_tuple(self) -> Tuple[str, str]:
        return (self.by, self.value)

    def __hash__(self):
        return hash(self.value)


class BaseElement:
    def __init__(
        self,
        browser: Chrome,
        locator: Locator,
        expected_condition_function: Callable = expected_conditions.presence_of_element_located,
    ) -> None:
        self._browser = browser
        self._locator = locator
        self._element = WebDriverWait(browser, 10).until(
            expected_condition_function(locator.to_tuple())
        )

    def click(self):
        self._element.click()

    def write(self, value: str):
        self._element.clear()
        self._element.send_keys(value)
        self._element.send_keys(value)  # Why two times?

        # WebDriverWait(self._browser, 10).until(
        #     expected_conditions.text_to_be_present_in_element(self._locator.to_tuple(), value)
        # )

    def scroll_down(self):
        current_height = self._element.size["height"]
        previous_height = None
        while previous_height != current_height:
            ActionChains(self._browser).send_keys_to_element(
                self._element, Keys.PAGE_DOWN
            ).pause(1).perform()
            time.sleep(1)
            previous_height = current_height
            current_height = self._element.size["height"]

    def move_by_x_offset_from_left_border(self, x_offset):
        ActionChains(self._browser).move_to_element_with_offset(
            self._element, x_offset - (self._element.rect["width"]) / 2, 0
        ).perform()

    def width(self):
        return self._element.rect["width"]

    def read(self):
        return self._element.text.strip()


def init_chrome(load_strategy_none=False, headless=False):
    option = Options()
    if headless:
        option.add_argument("--headless")
    if load_strategy_none:
        option.page_load_strategy = "none"
    return Chrome(options=option)


def bearish_path_fun():
    current_working_directory = Path.cwd()
    bearish_path = current_working_directory / "bearish"
    bearish_path.mkdir(parents=True, exist_ok=True)
    return bearish_path


class Sources(Enum):
    trading_view: str = "trading"
    investing: str = "investing"
    yahoo: str = "yahoo"


class BaseSettings(BaseModel):
    ...


def clean_dict(data):
    cleaned_data = {}
    for name, value in data.items():
        if isinstance(value, dict):
            cleaned_data[str(name)] = clean_dict(value)
        else:
            cleaned_data[str(name)] = value
    return cleaned_data


class BasePage(BaseModel):
    url: str
    source: Sources
    settings: BaseSettings
    browser: Optional[Chrome] = Field(default_factory=init_chrome, description="")
    bearish_path: Optional[Path] = Field(default_factory=bearish_path_fun, description="")
    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=True)
    _tables = PrivateAttr(default_factory=lambda: [])
    _skip_existing = PrivateAttr(default=True)
    _encoding = PrivateAttr(default=None)

    def go(self):
        self.browser.get(self.url)

    def pause(self, seconds: int):
        ActionChains(self.browser).pause(seconds).perform()

    def refresh(self):
        self.browser.refresh()

    def full_screen(self):
        self.browser.fullscreen_window()

    def click(self, locator: Locator):
        BaseElement(self.browser, locator).click()

    def init_visible_element(self, locator: Locator):
        element = BaseElement(
            self.browser,
            locator,
            expected_condition_function=expected_conditions.visibility_of_element_located,
        )
        return element

    def get_element(self, locator: Locator):
        return BaseElement(self.browser, locator)

    def move_by_x_offset_from_left_border(self, element, x_offset: int):
        right_border = x_offset > element.width()
        if not right_border:
            element.move_by_x_offset_from_left_border(x_offset)
        return right_border

    def move_from_left_to_right_border(self, element, action: Callable):
        x_offset = 1
        actions = []
        right_border = False
        while not right_border:
            try:
                right_border = self.move_by_x_offset_from_left_border(
                    element, x_offset=x_offset
                )
                if not right_border:
                    actions.append(action())
            except (MoveTargetOutOfBoundsException, TimeoutException):
                break
            x_offset += 1
        return actions

    def write(self, locator: Locator, value: str):
        BaseElement(self.browser, locator).write(value)

    def scroll_down(self, locator: Locator):
        self.wait_until_ready(locator).scroll_down()

    def scroll_down_and_read(self, locator: Locator):
        self.scroll_down(locator)
        self.read_current_page()

    def _read_html(self):
        return pd.read_html(self.browser.page_source)

    def read_current_page(self, pause: int = 1, replace_values: dict = None):
        self.pause(pause)
        tables = self._read_html()
        new_tables = self._replace_values(tables, replace_values=replace_values or {})
        self._tables.append(new_tables)

    def _replace_values(self, tables: list[pd.DataFrame], replace_values: dict):
        def find_and_replace(element, replace_values):
            for old_value, new_value in replace_values.items():
                if element == old_value:
                    return new_value
            return element

        new_tables = []
        if not replace_values:
            return tables
        for table in tables:
            table = table.applymap(
                partial(find_and_replace, replace_values=replace_values)
            )
            new_tables.append(table)
        return new_tables

    @abc.abstractmethod
    def _preprocess_tables(self):
        ...

    @abc.abstractmethod
    def _custom_scrape(self):
        ...

    def _exist_files_in_folder(self):
        return (
            self.folder_path.exists()
            and self.folder_path.is_dir()
            and len(list(self.folder_path.iterdir()))
        )

    def get_stored_raw(self):
        if self._skip_existing and self._exist_files_in_folder():
            return self._get_latest_file()
        else:
            return self.path

    def scrape(self, skip_existing: bool = True):
        self._skip_existing = skip_existing
        if self._skip_existing and self._exist_files_in_folder():
            return
        self.go()
        records = self._custom_scrape()
        self.to_json(data=records)
        return records

    def _get_country_name_per_enum(self, enum, country):
        return [
            k
            for k, v in enum.__dict__.items()
            if isinstance(v, enum) and v.value == country
        ][0]

    def _get_country_name(self):
        ...

    @computed_field
    @cached_property
    def folder_path(self) -> Path:
        source = self.source if isinstance(self.source, str) else self.source.value
        path = (
            self.bearish_path
            / source
            / type(self).__name__.lower().replace(source, "").replace("scraper", "")
        )

        if hasattr(self, "country"):

            path = path / self._get_country_name()
        elif hasattr(self, "exchange"):
            path = path / self.exchange
        else:
            pass
        return path

    @computed_field
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

    def to_json(self, data):
        self.path.touch(exist_ok=True)
        with self.path.open(mode="w") as f:
            simplejson.dump(
                self._clean(data), f, indent=4, ignore_nan=True, encoding=self._encoding
            )

    def wait_until_ready(self, locator: Locator):
        return BaseElement(
            self.browser,
            locator,
            expected_condition_function=expected_conditions.visibility_of_element_located,
        )

    def close(self):
        self.browser.close()

    def _clean(self, data):
        if isinstance(data, list):
            cleaned_data = []
            for data_ in data:
                cleaned_data.append(clean_dict(data_))
            return cleaned_data
        else:
            return clean_dict(data)


class BaseTickerPage(BasePage):
    @abc.abstractmethod
    def read_historical(self):
        ...
