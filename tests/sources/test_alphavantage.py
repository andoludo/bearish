import json
import os
import pickle
from pathlib import Path

import pandas as pd
import pytest
from alpha_vantage.fundamentaldata import FundamentalData

from bearish.sources.alphavantage import (
    AlphaVantageFinancialMetrics,
    AlphaVantageBalanceSheet,
    AlphaVantageCashFlow,
    AlphaVantageSource,
    AlphaVantageBase,
)


@pytest.mark.skip("check later")
def test_alpha_vantage_fundamental_data():
    fundamentals = FundamentalData(key=os.environ["ALPHAVANTAGE_API_KEY"])
    #
    # company_overview = fundamentals.get_company_overview("AAPL")
    # company_overview_path = Path(__file__).parent / "company_overview.json"
    # company_overview_path.write_text(json.dumps(company_overview, indent=4))

    dividends = fundamentals.get_dividends("AAPL")
    dividends_path = Path(__file__).parent / "dividends.pkl"
    dividends_path.write_bytes(pickle.dumps(dividends))

    splits = fundamentals.get_splits("AAPL")
    splits_path = Path(__file__).parent / "splits.pkl"
    splits_path.write_bytes(pickle.dumps(splits))

    statement_annual = fundamentals.get_income_statement_annual("AAPL")
    statement_annual_path = Path(__file__).parent / "statement_annual.pkl"
    statement_annual_path.write_bytes(pickle.dumps(statement_annual))

    income_statement_quarterly = fundamentals.get_income_statement_quarterly("AAPL")
    income_statement_quarterly_path = (
        Path(__file__).parent / "income_statement_quarterly.pkl"
    )
    income_statement_quarterly_path.write_bytes(
        pickle.dumps(income_statement_quarterly)
    )

    balance_sheet_annual = fundamentals.get_balance_sheet_annual("AAPL")
    balance_sheet_annual_path = Path(__file__).parent / "balance_sheet_annual.pkl"
    balance_sheet_annual_path.write_bytes(pickle.dumps(balance_sheet_annual))

    balance_sheet_quarterly = fundamentals.get_balance_sheet_quarterly("AAPL")
    balance_sheet_quarterly_path = Path(__file__).parent / "balance_sheet_quarterly.pkl"
    balance_sheet_quarterly_path.write_bytes(pickle.dumps(balance_sheet_quarterly))

    cash_flow_annual = fundamentals.get_cash_flow_annual("AAPL")
    cash_flow_annual_path = Path(__file__).parent / "cash_flow_annual.pkl"
    cash_flow_annual_path.write_bytes(pickle.dumps(cash_flow_annual))

    earnings_annual = fundamentals.get_earnings_annual("AAPL")
    earnings_annual_path = Path(__file__).parent / "earnings_annual.pkl"
    earnings_annual_path.write_bytes(pickle.dumps(earnings_annual))

    earnings_quarterly = fundamentals.get_earnings_quarterly("AAPL")
    earnings_quarterly_path = Path(__file__).parent / "earnings_quarterly.pkl"
    earnings_quarterly_path.write_bytes(pickle.dumps(earnings_quarterly))


def test_financials():
    company_overview_path = Path(__file__).parent / "company_overview.json"
    company_overview = json.loads(company_overview_path.read_text())
    result = AlphaVantageFinancialMetrics.from_json(company_overview[0])
    assert result
    assert isinstance(result, AlphaVantageFinancialMetrics)


def test_balance_sheet():
    balance_sheet_annual_path = Path(__file__).parent / "balance_sheet_annual.pkl"
    balance_sheet_annual = pickle.loads(balance_sheet_annual_path.read_bytes())
    balance_sheet_quarterly_path = Path(__file__).parent / "balance_sheet_quarterly.pkl"
    balance_sheet_quarterly = pickle.loads(balance_sheet_quarterly_path.read_bytes())
    results_annual = AlphaVantageBalanceSheet.from_dataframe(
        "AAPL", balance_sheet_annual[0]
    )
    results_quarterly = AlphaVantageBalanceSheet.from_dataframe(
        "AAPL", balance_sheet_quarterly[0]
    )
    data_quarterly = balance_sheet_quarterly[0]
    data_annual = balance_sheet_annual[0]
    data_to_add = data_quarterly[
        ~data_quarterly["fiscalDateEnding"].isin(data_annual["fiscalDateEnding"])
    ]
    data_combined = pd.concat([data_annual, data_to_add], ignore_index=True)
    results_combined = AlphaVantageBalanceSheet.from_dataframe("AAPL", data_combined)
    assert results_annual
    assert results_quarterly
    assert all(
        isinstance(result, AlphaVantageBalanceSheet) for result in results_annual
    )
    assert all(
        isinstance(result, AlphaVantageBalanceSheet) for result in results_quarterly
    )
    assert all(
        isinstance(result_combined, AlphaVantageBalanceSheet)
        for result_combined in results_combined
    )


def test_cash_flow():
    cash_flow_annual_path = Path(__file__).parent / "cash_flow_annual.pkl"
    cash_flow_annual = pickle.loads(cash_flow_annual_path.read_bytes())
    results = AlphaVantageCashFlow.from_dataframe("AAPL", cash_flow_annual[0])
    assert results
    assert all(isinstance(result, AlphaVantageCashFlow) for result in results)


class FakeFundamentalData:
    def get_company_overview(self, ticker):
        overview_path = Path(__file__).parent / "company_overview.json"
        return json.loads(overview_path.read_text())

    def get_balance_sheet_annual(self, ticker):
        path = Path(__file__).parent / "balance_sheet_annual.pkl"
        return pickle.loads(path.read_bytes())

    def get_balance_sheet_quarterly(self, ticker):
        path = Path(__file__).parent / "balance_sheet_quarterly.pkl"
        return pickle.loads(path.read_bytes())

    def get_cash_flow_annual(self, ticker):
        path = Path(__file__).parent / "cash_flow_annual.pkl"
        return pickle.loads(path.read_bytes())


class FakeTimeSeries:
    def get_symbol_search(self, ticker):
        # data = TimeSeries(
        #     key=os.environ["ALPHAVANTAGE_API_KEY"]
        # ).get_symbol_search("AAPL")
        # balance_sheet_annual_path = Path(__file__).parent / "symbol_search.pkl"
        # balance_sheet_annual_path.write_bytes(pickle.dumps(data))
        symbol_search_path = Path(__file__).parent / "symbol_search.pkl"
        return pickle.loads(symbol_search_path.read_bytes())

    def get_daily(self, ticker, outputsize: str = "full"):
        # data = TimeSeries(
        #     key=os.environ["ALPHAVANTAGE_API_KEY"]
        # ).get_daily("AAPL",outputsize=outputsize)
        path = Path(__file__).parent / "daily_series.pkl"
        # path.write_bytes(pickle.dumps(data))
        return pickle.loads(path.read_bytes())


def test_alphavantage_read_assets():
    tickers = ["AAPL"]
    AlphaVantageBase.fundamentals = FakeFundamentalData()
    AlphaVantageBase.timeseries = FakeTimeSeries()
    assets = AlphaVantageSource().read_assets(filters=tickers)
    assert assets


def test_alphavantage_read_financials():
    ticker = "AAPL"
    AlphaVantageBase.fundamentals = FakeFundamentalData()
    AlphaVantageBase.timeseries = FakeTimeSeries()
    financials = AlphaVantageSource().read_financials(ticker)
    assert financials


def test_alphavantage_read_series():
    ticker = "AAPL"
    AlphaVantageBase.fundamentals = FakeFundamentalData()
    AlphaVantageBase.timeseries = FakeTimeSeries()
    series = AlphaVantageSource().read_series(ticker, "full")
    assert series