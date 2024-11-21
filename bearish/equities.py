from typing import List, TYPE_CHECKING, Literal

from pydantic import (
    Field,
    model_validator, )

from bearish.models.base import BaseBearishModel

if TYPE_CHECKING:
    from bearish.database.crud import BearishDb

RAW_EQUITIES_DATA_URL = "https://raw.githubusercontent.com/JerBouma/FinanceDatabase/refs/heads/main/database/equities.csv"



SeriesType = Literal["full", "compact"]





# class DailyOhlcv(BaseOhlcv):
#     date: Annotated[
#         datetime,
#         BeforeValidator(to_datetime),
#         Field(validation_alias=AliasChoices("Date")),
#     ]
#     symbol: Annotated[str, Field(validation_alias=AliasChoices("2. Symbol"))]
#     timezone: Annotated[
#         Optional[str], Field(None, validation_alias=AliasChoices("5. Time Zone"))
#     ]

#
# class DailySeries(BaseBearishModel):
#     daily_ohlcv: List[DailyOhlcv]
#
#     @classmethod
#     def _from_raw_alphavantage(
#         cls, data: Tuple[Dict[str, Any], Dict[str, Any]]
#     ) -> List[DailyOhlcv]:
#         time_series, metadata = data
#         return [
#             DailyOhlcv(**(v | {"date": k} | metadata)) for k, v in time_series.items()
#         ]
#
#     @classmethod
#     def from_alphavantage(
#         cls, equity: "Equity", type: SeriesType = "compact"
#     ) -> "DailySeries":
#         ts = TimeSeries(key=os.environ["ALPHAVANTAGE_API_KEY"])
#         data = ts.get_daily(equity.symbol, outputsize=type)
#         daily_ohlcv = cls._from_raw_alphavantage(data)
#         return cls(daily_ohlcv=daily_ohlcv)
#
#     @classmethod
#     def from_yfinance(
#         cls, equity: "Equity", type: SeriesType = "compact"
#     ) -> "DailySeries":
#         type = "max" if type == "full" else "5d"
#         ticker = yf.Ticker(equity.symbol)
#         data = ticker.history(period=type)
#         records = data.reset_index().to_dict(orient="records")
#         daily_ohlcv = [
#             DailyOhlcv(**(record | {"symbol": equity.symbol})) for record in records
#         ]
#         return cls(daily_ohlcv=daily_ohlcv)
#
#     def write(self, database: "BearishDb"):
#         database.write_series(self.daily_ohlcv)
#
#
#
# class Equities(BaseBearishModel):
#     equities: List[Equity]
#
#     @classmethod
#     def from_dataframe(cls, equities: pd.DataFrame) -> "Equities":
#         equities = equities.dropna(subset=["symbol", "country"])
#         equities_mapping = [equity.to_dict() for _, equity in equities.iterrows()]
#         equities = [Equity(**equity_mapping) for equity_mapping in equities_mapping]
#         return cls(equities=equities)
#
#     @classmethod
#     def from_url(cls,url: Optional[str] = None) -> "Equities":
#         url = url or RAW_EQUITIES_DATA_URL
#         response = requests.get(url)
#         if not response.ok:
#             raise Exception(
#                 f"Failed to download equities data from {url}"
#             )
#         equities = pd.read_csv(StringIO(response.text))
#         return cls.from_dataframe(equities)
#
#     def write(self, database: "BearishDb"):
#         database.write_equities(self.equities)







if __name__ == "__main__":
    from bearish.database.crud import BearishDb

    bearish_db = BearishDb()
    # equities = Equities.from_url()
    # equities.write(bearish_db)
    equities = bearish_db.read_equities(
        EquityQuery(countries=["Belgium"], exchanges=["BRU"])
    )
    for equity in equities:
        daily_series = DailySeries.from_yfinance(equity)
        daily_series.write(bearish_db)
