import datetime
from pathlib import Path
from typing import List, Optional

from bearish.database.crud import BearishDb
from bearish.database.schemas import PriceCurrencyORM
from bearish.fx import CORE_CURRENCIES, currencies_in_use, fx_symbol, fx_tickers, normalise_currency, write_fx_prices
from bearish.main import Bearish
from bearish.models.assets.assets import Assets
from bearish.models.base import Ticker
from bearish.models.financials.base import Financials
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery, Symbols
from bearish.sources.base import AbstractSource
from bearish.types import SeriesLength


class FakeFxPrice(Price):
    __source__ = "Yfinance"


class FakeFxSource(AbstractSource):
    """Returns one quote per requested pair, so write_many_series can be exercised offline."""

    __source__ = "Yfinance"
    countries: List[str] = []  # type: ignore[assignment]  # noqa: RUF012
    requested: List[str] = []  # noqa: RUF012

    def set_api_key(self, api_key: Optional[str]) -> None: ...

    def _read_assets(self, query: Optional[AssetQuery] = None) -> Assets:
        return Assets()

    def _read_financials(self, tickers: List[str]) -> List[Financials]:
        return []

    def _read_series(self, tickers: List[str], type: SeriesLength) -> List[Price]:
        self.requested.extend(tickers)
        return [
            FakeFxPrice(
                symbol=symbol, date=datetime.date(2026, 10, 22), open=1.0, high=1.0, low=1.0, close=1.0 + i, volume=0.0
            )
            for i, symbol in enumerate(tickers)
        ]


def test_fx_symbol_and_tickers() -> None:
    assert fx_symbol("jpy") == "USDJPY=X"
    assert fx_symbol("USD", base="EUR") == "EURUSD=X"
    assert [t.symbol for t in fx_tickers(["JPY", "EUR", "USD", "EUR"])] == ["USDEUR=X", "USDJPY=X"]


def test_normalise_currency_handles_minor_units_and_junk() -> None:
    assert normalise_currency(" eur ") == "EUR"
    assert normalise_currency("GBp") == "GBP"
    assert normalise_currency("ZAc") == "ZAR"
    assert normalise_currency("") is None
    assert normalise_currency("N/A") is None
    assert normalise_currency(None) is None


def test_currencies_in_use_reads_asset_tables(bearish_db_with_assets: BearishDb) -> None:
    currencies = currencies_in_use(bearish_db_with_assets)
    assert "USD" not in currencies
    assert set(CORE_CURRENCIES) <= set(currencies)
    assert currencies == sorted(currencies)
    assert all(len(code) == 3 for code in currencies)


def test_write_fx_prices_fills_pricecurrency_and_fxrate_view(tmp_path: Path) -> None:
    source = FakeFxSource()
    bearish = Bearish(
        path=tmp_path / "fx.db",
        asset_sources=[],
        detailed_asset_sources=[],
        financials_sources=[],
        price_sources=[source],
    )
    symbols = write_fx_prices(bearish, currencies=["EUR", "JPY", "USD"])
    assert symbols == ["USDEUR=X", "USDJPY=X"]
    assert source.requested == symbols

    stored = bearish.read_series(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="USDJPY=X")])), months=12 * 10, table=PriceCurrencyORM
    )
    assert [p.close for p in stored] == [2.0]
    rates = bearish._bearish_db.read_query("SELECT base, quote, rate FROM fxrate ORDER BY quote")
    assert rates.to_dict(orient="records") == [
        {"base": "USD", "quote": "EUR", "rate": 1.0},
        {"base": "USD", "quote": "JPY", "rate": 2.0},
    ]
    # FX pairs are not equities: nothing lands in price / pricetracker
    assert bearish._bearish_db.read_query("SELECT COUNT(*) AS n FROM price")["n"].iloc[0] == 0
    assert bearish._bearish_db.read_query("SELECT COUNT(*) AS n FROM pricetracker")["n"].iloc[0] == 0
