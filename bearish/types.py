from typing import Literal

TickerOnlySources = Literal["investpy", "FMPAssets", "FinanceDatabase"]

Sources = Literal[
    "Tiingo",
    "investpy",
    "Yfinance",
    "FMP",
    "FMPAssets",
    "FinanceDatabase",
    "AlphaVantage",
    "YahooQuery",
]

SeriesLength = Literal["max", "1d", "5d"]
DELAY = 1
