import datetime
from pathlib import Path
from typing import List, Optional

import requests_mock

from bearish.database.crud import BearishDb
from bearish.database.schemas import PriceCommodityORM
from bearish.exchanges.exchanges import Countries
from bearish.macro.commodities import COMMODITIES, commodities_with
from bearish.macro.models import MacroSeries, Observation
from bearish.macro.pipelines.commodities import (
    write_commodity_observations,
    write_commodity_prices,
    write_commodity_reference,
    write_country_exposures,
)
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.sources.comtrade import COMTRADE_PREVIEW_URL
from bearish.main import Bearish
from bearish.models.base import Ticker
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery, Symbols
from bearish.sources.base import AbstractSource
from bearish.types import SeriesLength


class StubPinkSheet(AbstractMacroSource):
    __source__ = "WorldBankPinkSheet"

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        return [
            Observation(series_id=s.series_id, date=datetime.date(2026, 1, 1), value=100.0, as_of=datetime.date(2026, 2, 1))
            for s in series
        ]


class StubPriceSource(AbstractSource):
    __source__ = "Yfinance"
    countries: List[Countries] = ["US"]  # noqa: RUF012

    def set_api_key(self, api_key: Optional[str]) -> None: ...

    def _read_assets(self, query=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def _read_financials(self, tickers):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def _read_series(self, tickers: List[str], type: SeriesLength) -> List[Price]:
        return [
            Price(symbol=t, source="Yfinance", date=datetime.date.today(), open=1, high=1, low=1, close=1, volume=1)
            for t in tickers
        ]


def test_reference_and_observations(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "c.db")
    write_commodity_reference(db)
    assert len(db.read_commodities()) == len(COMMODITIES)
    written = write_commodity_observations(db, sources=[StubPinkSheet(pause=0)])
    assert written == len(commodities_with("pinksheet_series"))
    assert write_commodity_observations(db, sources=[StubPinkSheet(pause=0)]) == 0  # unchanged values, no new vintage
    trackers = db.read_macro_trackers()
    assert {t.source for t in trackers} == {"WorldBankPinkSheet"}
    assert len(db.read_macro_series()) >= written


def test_commodity_prices_go_to_pricecommodity(tmp_path: Path) -> None:
    bearish = Bearish(
        path=tmp_path / "p.db",
        asset_sources=[],
        detailed_asset_sources=[],
        financials_sources=[],
        price_sources=[StubPriceSource()],
    )
    symbols = write_commodity_prices(bearish, "1d")
    assert "GC=F" in symbols
    series = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="GC=F")])), months=24, table=PriceCommodityORM
    )
    assert series and series[0].symbol == "GC=F"
    assert bearish._bearish_db.read_query("SELECT COUNT(*) AS n FROM pricetracker")["n"].iloc[0] == 0  # track=False


def test_country_exposures_written(tmp_path: Path, macro_data_dir: Path) -> None:
    db = BearishDb(database_path=tmp_path / "e.db")
    from bearish.macro.countries import country_from

    france = country_from("FRA")
    assert france is not None
    with requests_mock.Mocker() as req:
        req.get(
            COMTRADE_PREVIEW_URL,
            text=lambda request, context: (
                macro_data_dir / "comtrade" / f"fra_2023_{request.qs['flowcode'][0].upper()}.json"
            ).read_text(),
        )
        rows = write_country_exposures(db, year=2023, countries=[france], pause=0)
    assert rows > 0
    assert len(db.read_country_exposures(country="FRA")) == rows
