from bearish.database.crud import BearishDb
from bearish.exchanges.exchanges import exchanges_factory


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


def test_detailed_assets_(bear_db: BearishDb) -> None:
    exchanges = exchanges_factory()
    query = exchanges.get_exchange_query(["US", "Germany"])
    tickers = bear_db._get_tickers(query)
    assert tickers
