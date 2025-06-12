import pytest
import yfinance as yf

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
    ticker_ = yf.Ticker("AAPL")
    results = YfinanceFinancialMetrics.from_ticker(ticker_)
    assert results
    assert all(isinstance(result, YfinanceFinancialMetrics) for result in results)


def test_balance_sheet():
    ticker_ = yf.Ticker("AAPL")
    results = yFinanceBalanceSheet.from_ticker(ticker_)
    assert results
    assert all(isinstance(result, yFinanceBalanceSheet) for result in results)


def test_cashflow():
    ticker_ = yf.Ticker("AAPL")
    results = yFinanceCashFlow.from_ticker(ticker_)
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

@pytest.mark.skip(reason="yfinance bug?")
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
    ticker_ = yf.Ticker("AAPL")
    earnings_date = yFinanceEarningsDate.from_ticker(ticker_)
    assert earnings_date


def test_earnings_data():
    ticker_ = yf.Ticker("MLHCF.PA")
    earnings_data = yFinanceEarningsDate.from_ticker(ticker_)
    assert not earnings_data


def test_bug_financials():
    ticker_ = yf.Ticker("ALHIT.PA")
    financial_metrics = YfinanceFinancialMetrics.from_ticker(ticker_)
    balance_sheets = yFinanceBalanceSheet.from_ticker(ticker_)
    cash_flows = yFinanceCashFlow.from_ticker(ticker_)
    earnings_date = yFinanceEarningsDate.from_ticker(ticker_)
    assert financial_metrics
    assert balance_sheets
    assert not cash_flows
    assert earnings_date
