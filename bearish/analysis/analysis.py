from typing import get_args, Optional

from bearish.interface.interface import BearishDbBase
from bearish.models.assets.equity import BaseEquity
from bearish.models.base import Ticker
from bearish.models.financials.base import FundamentalAnalysis, Financials
from bearish.models.price.prices import TechnicalAnalysis, Prices
from bearish.models.query.query import Symbols, AssetQuery
from bearish.types import TickerOnlySources


class Analysis(BaseEquity, TechnicalAnalysis, FundamentalAnalysis):
    price_per_earning_ratio: Optional[float] = None

    @classmethod
    def from_ticker(cls, bearish_db: BearishDbBase, ticker: Ticker) -> "Analysis":
        asset = bearish_db.read_assets(
            AssetQuery(
                symbols=Symbols(equities=[ticker]),  # type: ignore
                excluded_sources=get_args(TickerOnlySources),
            )
        )
        equity = asset.get_one_equity()
        fundamental_analysis = Financials.from_ticker(
            bearish_db, ticker
        ).fundamental_analysis(ticker)
        technical_analysis = Prices.from_ticker(bearish_db, ticker).technical_analysis()
        return cls.model_validate(
            equity.model_dump()
            | fundamental_analysis.model_dump()
            | technical_analysis.model_dump()
            | {
                "price_per_earning_ratio": (
                    (
                        technical_analysis.last_price
                        / fundamental_analysis.earning_per_share
                    )
                    if technical_analysis.last_price is not None
                    and fundamental_analysis.earning_per_share != 0
                    and fundamental_analysis.earning_per_share is not None
                    else None
                )
            }
        )
