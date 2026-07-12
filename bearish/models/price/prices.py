import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from pydantic import BaseModel

from bearish.models.base import Ticker
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery, Symbols
from bearish.utils.utils import to_dataframe


if TYPE_CHECKING:
    from bearish.interface.interface import BearishDbBase
logger = logging.getLogger(__name__)


class Prices(BaseModel):
    prices: list[Price]

    def get_last_date(self) -> date:
        return sorted(self.prices, key=lambda price: price.date)[-1].date

    def ticker_date(self, symbol: str) -> date:
        symbol_date = sorted(
            [p for p in self.prices if p.symbol == symbol], key=lambda p: p.date
        )
        if not symbol_date:
            return date(1970, 1, 1)
        return symbol_date[-1].date

    @classmethod
    def from_ticker(cls, bearish_db: "BearishDbBase", ticker: Ticker) -> "Prices":
        prices = bearish_db.read_series(
            AssetQuery(symbols=Symbols(equities=[ticker])), months=12 * 8  # type: ignore
        )
        return cls(prices=prices)

    def to_dataframe(self) -> pd.DataFrame:
        return to_dataframe(self.prices)

    def to_csv(self, json_path: Path | str) -> None:
        self.to_dataframe().to_csv(json_path)

    @classmethod
    def from_csv(cls, json_path: Path | str) -> "Prices":
        data = pd.read_csv(json_path)
        data["date"] = pd.to_datetime(data["date"], utc=True)
        return cls(
            prices=[
                Price.model_validate(d)
                for d in data.replace(np.nan, None).to_dict(orient="records")
            ]
        )
