from typing import Literal

TickerOnlySources = Literal["investpy", "FMPAssets", "FinanceDatabase"]

# "FMP"/"FMPAssets" (source removed: API discontinued for non-legacy users) and
# "AlphaVantage" (never had a source implementation) stay in the Literal so that
# rows already stored in existing databases keep validating.
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

SeriesLength = Literal["max", "1d", "5d", "1mo", "3mo", "6mo"]
DELAY = 0.2
