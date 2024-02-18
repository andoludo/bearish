from bearish.scrapers.model import Ticker, unflatten_json


def test_screener(investing_record: dict, trading_record: dict) -> None:
    investing = unflatten_json(Ticker, investing_record)
    trading = unflatten_json(Ticker, trading_record)
    assert Ticker(**investing)
    assert Ticker(**trading)


def test_ticker(ticker_trading: dict) -> None:
    income_statement_trading = unflatten_json(Ticker, ticker_trading)
    assert Ticker(**income_statement_trading)


def test_unflatten_json(trading_record: dict) -> None:
    nested_data = unflatten_json(Ticker, trading_record)
    assert nested_data["fundamental"]["ratios"]["price_earning_ratio"]
