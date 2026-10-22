import datetime
from pathlib import Path
from typing import List, Optional

from bearish.exchanges.exchanges import Countries
from bearish.main import Bearish
from bearish.models.assets.assets import Assets
from bearish.models.base import Ticker, TrackerQuery, FinancialsTracker
from bearish.models.financials.base import Financials
from bearish.models.financials.metrics import FinancialMetrics
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery
from bearish.sources.base import AbstractSource
from bearish.types import SeriesLength


class _StubFinancials(AbstractSource):
    """Covers only the symbols in ``covers``; records what it was asked for."""

    countries: List[Countries] = ["US", "Germany"]  # noqa: RUF012
    covers: List[str] = []
    asked: List[List[str]] = []

    def set_api_key(self, api_key: Optional[str]) -> None: ...

    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        return Assets()

    def _read_series(self, tickers: List[str], type: SeriesLength) -> List[Price]:
        return []

    def _read_financials(self, tickers: List[str]) -> List[Financials]:
        self.asked.append(list(tickers))
        return [
            Financials(
                financial_metrics=[
                    FinancialMetrics(symbol=symbol, source=self.__source__, date=datetime.date(2025, 12, 31), net_income=1.0)
                ]
            )
            for symbol in tickers
            if symbol in self.covers
        ]


class SecStub(_StubFinancials):
    __source__ = "SEC"


class YahooStub(_StubFinancials):
    __source__ = "Yfinance"


def test_financials_fall_through_sources_per_ticker(tmp_path: Path) -> None:
    sec = SecStub(covers=["AAPL"], asked=[])
    yahoo = YahooStub(covers=["AAPL", "SAP.DE"], asked=[])
    bearish = Bearish(
        path=tmp_path / "bear.db",
        asset_sources=[],
        detailed_asset_sources=[],
        price_sources=[],
        financials_sources=[sec, yahoo],
        macro_sources=[],
    )
    tickers = [Ticker(symbol="AAPL", exchange="NMS"), Ticker(symbol="SAP.DE", exchange="GER")]

    bearish.write_many_financials(tickers)

    assert sec.asked == [["AAPL", "SAP.DE"]]
    assert yahoo.asked == [["SAP.DE"]]  # only what SEC could not provide
    rows = bearish._bearish_db.read_query("SELECT symbol, source FROM financialmetrics ORDER BY symbol")
    assert rows.values.tolist() == [["AAPL", "SEC"], ["SAP.DE", "Yfinance"]]
    tracked = bearish._bearish_db.read_tracker(TrackerQuery(), FinancialsTracker)
    assert {t.symbol: t.source for t in tracked} == {"AAPL": "SEC", "SAP.DE": "Yfinance"}
