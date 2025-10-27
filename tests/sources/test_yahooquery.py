from bearish.models.base import Ticker
from bearish.sources.yahooquery import YahooQueryEquity, YahooQuerySource


def test_yahooquery_equity():
    tickers = [Ticker(symbol="HO.PA"), Ticker(symbol="GOOG")]
    equities = YahooQueryEquity.from_tickers(tickers)
    assert equities
    assert len(equities.equities) == len(tickers)


def test_read_financials():
    tickers = [Ticker(symbol="HO.PA"), Ticker(symbol="GOOG")]
    financials = YahooQuerySource()._read_financials(
        tickers=[t.symbol for t in tickers]
    )
    assert financials


def test_read_series():
    tickers = [Ticker(symbol="HO.PA"), Ticker(symbol="GOOG")]
    prices = YahooQuerySource()._read_series(
        tickers=[t.symbol for t in tickers], type="7d"
    )
    assert prices


def test_yahooquery_indices():
    tickers = [Ticker(symbol="^GSPC"), Ticker(symbol="^FTSE")]
    equities = YahooQueryEquity.from_tickers(tickers)
    assert equities
    assert len(equities.equities) == len(tickers)
