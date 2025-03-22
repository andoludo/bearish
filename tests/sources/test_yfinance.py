import yfinance

from bearish.models.base import Ticker
from bearish.models.query.query import AssetQuery, Symbols
from bearish.sources.yfinance import (
    YfinanceFinancialMetrics,
    yFinanceBalanceSheet,
    yFinanceCashFlow,
    yFinanceSource,
    YfinanceEquity,
    YfinanceEtf,
    yFinanceEarningsDate,
)


def test_yfinance():
    results = YfinanceFinancialMetrics.from_ticker("AAPL")
    assert results
    assert all(isinstance(result, YfinanceFinancialMetrics) for result in results)


def test_balance_sheet():
    results = yFinanceBalanceSheet.from_ticker("AAPL")
    assert results
    assert all(isinstance(result, yFinanceBalanceSheet) for result in results)


def test_cashflow():
    results = yFinanceCashFlow.from_ticker("AAPL")
    assert results
    assert all(isinstance(result, yFinanceCashFlow) for result in results)


def test_get_ticker():
    tickers = [Ticker(symbol="MSFT"), Ticker(symbol="AAPL"), Ticker(symbol="GOOG")]
    equities = YfinanceEquity.from_tickers(tickers)
    assert len(equities.equities) == len(tickers)


def test_yFinanceSource_update_assets():
    tickers = [Ticker(symbol="MSFT"), Ticker(symbol="AAPL"), Ticker(symbol="GOOG")]
    assets = yFinanceSource()._read_assets(
        AssetQuery(symbols=Symbols(equities=tickers))
    )
    assert len(assets.equities) == len(tickers)


def test_yFinanceSource_update_non_existent_assets():
    tickers = [
        Ticker(symbol="IDONOTEXISRS"),
        Ticker(symbol="AAPL"),
        Ticker(symbol="GOOG"),
    ]
    assets = yFinanceSource()._read_assets(
        AssetQuery(symbols=Symbols(equities=tickers))
    )
    assert len(assets.equities) == len(tickers) - 1


def test_yFinanceSource_no_country():
    tickers = [Ticker(symbol="ML.PA")]
    assets = yFinanceSource()._read_assets(
        AssetQuery(symbols=Symbols(equities=tickers))
    )
    assert len(assets.equities) == len(tickers)


def test_yFinanceSource_with_etf():
    assets = yFinanceSource()._read_assets(
        AssetQuery(
            symbols=Symbols(
                equities=[Ticker(symbol="MSFT")], etfs=[Ticker(symbol="SPY")]
            )
        )
    )
    assert assets.equities
    assert assets.etfs


def test_yfinance_etf():
    ticker = Ticker(symbol="SPY")
    etf = YfinanceEtf.from_tickers([ticker])
    assert etf


def test_yfinance_equity():
    tickers = [Ticker(symbol="HO.PA"), Ticker(symbol="GOOG")]
    equities = YfinanceEquity.from_tickers(tickers)
    assert equities
    assert len(equities.equities) == len(tickers)


def test_yfinance_earnings():
    earnings_date = yFinanceEarningsDate.from_ticker("AAPL")
    assert earnings_date


def test_earnings_data():
    earnings_data = yFinanceEarningsDate.from_ticker("MLHCF.PA")
    assert not earnings_data
