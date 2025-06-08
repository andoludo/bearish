from datetime import datetime
from typing import Optional, List, Dict, Any, cast, ClassVar

import requests  # type: ignore

from bearish.exchanges.exchanges import Countries
from bearish.models.assets.assets import Assets
from bearish.models.base import SourceBase
from bearish.models.financials.base import Financials
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery
from bearish.sources.base import AbstractSource
from bearish.types import Sources, SeriesLength
from bearish.utils.utils import get_start_date


def compute_url(ticker: str, api_key: str, from_: Optional[str] = None) -> str:
    from_ = from_ if from_ else "2019-01-02"
    return f"https://api.tiingo.com/tiingo/daily/{ticker.lower()}/prices?startDate={from_}&token={api_key}"


def read_api(
    api_key: str, ticker: str, from_: Optional[str] = None
) -> List[Dict[str, Any]]:
    headers = {"Content-Type": "application/json"}
    request_response = requests.get(
        compute_url(ticker, api_key, from_), headers=headers, timeout=10
    )
    return cast(List[Dict[str, Any]], request_response.json())


class TiingoSourceBase(SourceBase):
    __source__: Sources = "Tiingo"


class TiingoPrice(TiingoSourceBase, Price):
    __alias__: ClassVar[Dict[str, str]] = {
        "date": "date",
        "close": "close",
        "high": "high",
        "low": "low",
        "open": "open",
        "volume": "volume",
        "divCash": "dividends",
        "splitFactor": "stock_splits",
    }


class TiingoSource(TiingoSourceBase, AbstractSource):
    countries: List[Countries] = ["US"]  # noqa: RUF012

    def set_api_key(self, api_key: str) -> None:
        TiingoSourceBase.__api_key__ = api_key

    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        return Assets()

    def _read_financials(self, tickers: List[str]) -> List[Financials]:
        return [Financials()]

    def _read_series(self, tickers: List[str], type: SeriesLength) -> List[TiingoPrice]:  # type: ignore
        from_ = get_start_date(type)
        prices = []
        for ticker in tickers:
            datas = read_api(self.__api_key__, ticker, from_)
            prices.extend(
                [
                    TiingoPrice.model_validate(
                        {
                            **data,
                            "symbol": ticker,
                            "date": datetime.strptime(
                                data["date"], "%Y-%m-%dT%H:%M:%S.%fZ"
                            ).date(),
                        }
                    )
                    for data in datas
                ]
            )
        return prices
