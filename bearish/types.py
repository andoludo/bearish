from typing import Literal

Sources = Literal[
    "Tiingo",
    "investpy",
    "Yfinance",
    "FMP",
    "FMPAssets",
    "FinanceDatabase",
    "AlphaVantage",
]

SeriesLength = Literal["max", "1d", "5d"]
