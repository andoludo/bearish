from bearish.exchanges.exchanges import exchanges_factory
from bearish.models.base import Ticker


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
