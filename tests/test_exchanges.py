from bearish.exchanges.exchanges import exchanges_factory, Exchange
from bearish.models.base import Ticker
from bearish.models.query.query import AssetQuery, Symbols


def test_exchange_get_suffixes():
    exchanges = exchanges_factory()
    suffixes = exchanges.get_exchanges(["France", "Germany"])
    assert suffixes


def test_exchange_get_aliases():
    exchanges = exchanges_factory()
    aliases = exchanges.get_exchanges(["US"], type="aliases")
    assert aliases


def test_get_exchange_query():
    exchanges = exchanges_factory()
    query = exchanges.get_exchange_query(["US", "Germany"])
    assert query


def test_ticker_included():
    exchanges = exchanges_factory()
    ticker = Ticker(symbol="ALMNG.PA")
    ticker_included = exchanges.ticker_belongs_to_countries(ticker, countries=["US"])
    assert not ticker_included


def test_asset_query_exchange():
    exchanges = exchanges_factory()
    asset_query = AssetQuery(
        symbols=Symbols(
            equities=[Ticker(symbol="AAPL", exchange="NASDAQ"), Ticker(symbol="AIR.PA")]
        )
    )
    exchange_query = exchanges.get_exchange_query(["US", "Germany"])
    symbols_ = asset_query.symbols.filter(exchange_query.included)
    assert symbols_.equities[0] == Ticker(symbol="AAPL", exchange="NASDAQ")
