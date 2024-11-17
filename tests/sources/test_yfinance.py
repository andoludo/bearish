from bearish.sources.yfinance import YfinanceFinancialMetrics, yFinanceBalanceSheet, yFinanceCashFlow, yFinanceSource


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


def test_yFinanceSource():
    yFinanceSource().update_financials("AAPL")