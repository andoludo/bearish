from typing import Dict, Any

import pandas as pd

from bearish.sources.yfinance import (
    YfinanceFinancialMetrics,
    yFinanceBalanceSheet,
    yFinanceCashFlow,
    yFinanceSource,
    YfinanceEquity, YfinanceEtf,
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
    tickers = ["MSFT", "AAPL", "GOOG"]
    equities = YfinanceEquity.from_tickers(tickers)
    assert len(equities) == len(tickers)


def test_yFinanceSource_update_assets():
    tickers = ["MSFT", "AAPL", "GOOG"]
    assets = yFinanceSource()._read_assets(keywords=tickers)
    assert len(assets.equities) == len(tickers)


def test_yFinanceSource_update_non_existent_assets():
    tickers = ["IDONOTEXISRS", "AAPL", "GOOG"]
    assets = yFinanceSource()._read_assets(keywords=tickers)
    assert len(assets.equities) == len(tickers) - 1


def test_yFinanceSource_no_country():
    tickers = ["ML.PA"]
    assets = yFinanceSource()._read_assets(keywords=tickers)
    assert len(assets.equities) == len(tickers) - 1

import yfinance as yf



def test_yfinance_etf():
    ticker = "SPY"
    etf = YfinanceEtf.from_tickers([ticker])
    a = 12



def test_yfinance_equity():
    tickers = ["HO.PA", "GOOG"]
    equities = YfinanceEquity.from_tickers(tickers)
    assert equities
    assert len(equities) == len(tickers)