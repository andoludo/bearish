from pathlib import Path

import pandas as pd

from bearish.main import Bearish
from bearish.models.base import Ticker
from bearish.models.price.prices import Prices
from bearish.models.query.query import AssetQuery, Symbols


def read_prices(symbol: str) -> pd.DataFrame:
    bearish = Bearish(
        path=Path(__file__).parents[1] / "data" / "bear.db",
    )

    prices = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol=symbol)])), months=24 * 4
    )
    return Prices(prices=prices).to_dataframe()


if __name__ == "__main__":
    symbol = "MSFT"
    prices_df = read_prices(symbol)
    prices_df.to_csv(
        Path(__file__).parents[1] / "data" / f"prices_{symbol.lower()}.csv"
    )
