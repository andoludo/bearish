import logging
from datetime import date
from pathlib import Path
from typing import Annotated, Optional

import numpy as np
import pandas as pd
from pydantic import BeforeValidator, Field, BaseModel

from bearish.models.base import Ticker
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery, Symbols
from bearish.utils.utils import to_float
from bearish.interface.interface import BearishDbBase
import pandas_ta as ta  # type: ignore

logger = logging.getLogger(__name__)


def buy_opportunity(
    series_a: pd.Series, series_b: pd.Series  # type: ignore
) -> Optional[date]:
    sell = ta.cross(series_a=series_a, series_b=series_b)
    buy = ta.cross(series_a=series_b, series_b=series_a)
    if not buy[buy == 1].index.empty and not sell[sell == 1].index.empty:
        last_buy_signal = pd.Timestamp(buy[buy == 1].index[-1])
        last_sell_signal = pd.Timestamp(sell[sell == 1].index[-1])
        if last_buy_signal > last_sell_signal:
            return last_buy_signal
    return None


def price_growth(prices: pd.DataFrame, days: int) -> float:
    last_index = prices.last_valid_index()
    delta = pd.Timedelta(days=days)
    start_index = last_index - delta  # type: ignore
    return (
        (prices.loc[start_index].open - prices.loc[last_index].open)  # type: ignore
        * 100
        / prices.loc[last_index].open
    )


class TechnicalAnalysis(BaseModel):
    rsi_last_value: Optional[float] = None
    macd_12_26_9_buy_date: Optional[date] = None
    ma_50_200_buy_date: Optional[date] = None
    slope_7: Optional[float] = None
    slope_14: Optional[float] = None
    slope_30: Optional[float] = None
    slope_60: Optional[float] = None
    last_adx: Optional[float] = None
    last_dmp: Optional[float] = None
    last_dmn: Optional[float] = None
    last_price: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
        ),
    ]
    last_price_date: Annotated[
        Optional[date],
        Field(
            default=None,
        ),
    ]
    year_to_date_growth: Annotated[
        Optional[float],
        Field(
            default=None,
        ),
    ]
    last_52_weeks_growth: Annotated[
        Optional[float],
        Field(
            default=None,
        ),
    ]
    last_week_growth: Annotated[
        Optional[float],
        Field(
            default=None,
        ),
    ]
    last_month_growth: Annotated[
        Optional[float],
        Field(
            default=None,
        ),
    ]
    last_year_growth: Annotated[
        Optional[float],
        Field(
            default=None,
        ),
    ]

    @classmethod
    def from_data(cls, prices: pd.DataFrame) -> "TechnicalAnalysis":
        try:
            last_index = prices.last_valid_index()
            year_to_date_days = (
                last_index
                - pd.Timestamp(year=last_index.year, month=1, day=1, tz="UTC")  # type: ignore
            ).days
            year_to_date_growth = price_growth(prices, year_to_date_days)
            last_52_weeks_growth = price_growth(prices=prices, days=399)
            last_week_growth = price_growth(prices=prices, days=7)
            last_month_growth = price_growth(prices=prices, days=31)
            last_year_growth = price_growth(prices=prices, days=365)
            prices.ta.sma(50, append=True)
            prices.ta.sma(200, append=True)
            prices.ta.adx(append=True)
            prices["SLOPE_14"] = ta.linreg(prices.close, slope=True, length=14)
            prices["SLOPE_7"] = ta.linreg(prices.close, slope=True, length=7)
            prices["SLOPE_30"] = ta.linreg(prices.close, slope=True, length=30)
            prices["SLOPE_60"] = ta.linreg(prices.close, slope=True, length=60)
            prices.ta.macd(append=True)
            prices.ta.rsi(append=True)

            rsi_last_value = prices.RSI_14.iloc[-1]
            macd_12_26_9_buy_date = buy_opportunity(
                prices.MACDs_12_26_9, prices.MACD_12_26_9
            )
            ma_50_200_buy_date = buy_opportunity(prices.SMA_200, prices.SMA_50)
            return cls(
                rsi_last_value=rsi_last_value,
                macd_12_26_9_buy_date=macd_12_26_9_buy_date,
                ma_50_200_buy_date=ma_50_200_buy_date,
                last_price=prices.close.iloc[-1],
                last_price_date=prices.index[-1],
                last_adx=prices.ADX_14.iloc[-1],
                last_dmp=prices.DMP_14.iloc[-1],
                last_dmn=prices.DMN_14.iloc[-1],
                slope_7=prices.SLOPE_7.iloc[-1],
                slope_14=prices.SLOPE_14.iloc[-1],
                slope_30=prices.SLOPE_30.iloc[-1],
                slope_60=prices.SLOPE_60.iloc[-1],
                year_to_date_growth=year_to_date_growth,
                last_52_weeks_growth=last_52_weeks_growth,
                last_week_growth=last_week_growth,
                last_month_growth=last_month_growth,
                last_year_growth=last_year_growth,
            )
        except Exception as e:
            logger.error(f"Failing to calculate technical analysis: {e}")
            return cls()  # type: ignore


class Prices(BaseModel):
    prices: list[Price]

    def get_last_date(self) -> date:
        return sorted(self.prices, key=lambda price: price.date)[-1].date

    @classmethod
    def from_ticker(cls, bearish_db: BearishDbBase, ticker: Ticker) -> "Prices":
        prices = bearish_db.read_series(
            AssetQuery(symbols=Symbols(equities=[ticker])), months=12 * 5  # type: ignore
        )
        return cls(prices=prices)

    def to_dataframe(self) -> pd.DataFrame:

        data = pd.DataFrame.from_records([p.model_dump() for p in self.prices])
        if data.empty:
            return data
        data = data.set_index("date", inplace=False)
        data = data.sort_index(inplace=False)

        data.index = pd.to_datetime(data.index, utc=True)
        return data

    def to_csv(self, json_path: Path | str) -> None:
        self.to_dataframe().to_csv(json_path)

    def technical_analysis(self) -> TechnicalAnalysis:
        data = self.to_dataframe()
        if data.empty:
            return TechnicalAnalysis()  # type: ignore
        try:
            return TechnicalAnalysis.from_data(self.to_dataframe())
        except Exception as e:
            logger.error(f"Failing to calculate technical analysis: {e}")
            return TechnicalAnalysis()  # type: ignore

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
