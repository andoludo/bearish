from selenium.webdriver.common.by import By

from bearish.scrapers.type import Locator


class TradingCountry:
    germany: Locator = Locator(by=By.XPATH, value='//*[@id="source-item-2-0-5"]/div')
    belgium: Locator = Locator(by=By.XPATH, value='//*[@id="source-item-2-0-1"]/div')
    france: Locator = Locator(by=By.XPATH, value='//*[@id="source-item-2-0-10"]/div')
    us: Locator = Locator(
        by=By.XPATH, value='//*[@id="source-item-1-0-0"]/div/div[2]/div[2]'
    )


class InvestingCountry:
    germany: int = 17
    france: int = 22
    belgium: int = 34
    usa: int = 5
