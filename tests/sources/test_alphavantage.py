import json
import os
import pickle
from pathlib import Path

import pandas as pd
import pytest
from alpha_vantage.fundamentaldata import FundamentalData

from bearish.exceptions import InvalidApiKeyError
from bearish.models.base import Ticker
from bearish.models.query.query import Symbols, AssetQuery
from bearish.sources.alphavantage import (
    AlphaVantageFinancialMetrics,
    AlphaVantageBalanceSheet,
    AlphaVantageCashFlow,
    AlphaVantageSource,
    AlphaVantageBase,
)
from tests.conftest import FakeFundamentalData, FakeTimeSeries


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


@pytest.fixture
def root_path() -> Path:
    return Path(__file__).parents[1].joinpath("data", "sources", "alphavantage")


def test_financials(root_path: Path):
    company_overview_path = root_path / "company_overview.json"
    company_overview = json.loads(company_overview_path.read_text())
    result = AlphaVantageFinancialMetrics.from_json(company_overview[0])
    assert result
    assert isinstance(result, AlphaVantageFinancialMetrics)


def test_balance_sheet(root_path: Path):
    balance_sheet_annual_path = root_path / "balance_sheet_annual.pkl"
    balance_sheet_annual = pickle.loads(balance_sheet_annual_path.read_bytes())
    balance_sheet_quarterly_path = root_path / "balance_sheet_quarterly.pkl"
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


def test_cash_flow(root_path: Path):
    cash_flow_annual_path = root_path / "cash_flow_annual.pkl"
    cash_flow_annual = pickle.loads(cash_flow_annual_path.read_bytes())
    results = AlphaVantageCashFlow.from_dataframe("AAPL", cash_flow_annual[0])
    assert results
    assert all(isinstance(result, AlphaVantageCashFlow) for result in results)


def test_alphavantage_read_assets():
    tickers = [Ticker(symbol="AAPL")]
    AlphaVantageBase.fundamentals = FakeFundamentalData()
    AlphaVantageBase.timeseries = FakeTimeSeries()
    assets = AlphaVantageSource()._read_assets(
        AssetQuery(symbols=Symbols(equities=tickers))
    )
    assert assets
    assert not assets.is_empty()


@pytest.mark.integration
def test_alphavantage_read_assets_integration():
    tickers = [Ticker(symbol="ML")]
    assets = AlphaVantageSource()._read_assets(
        AssetQuery(symbols=Symbols(equities=tickers))
    )
    assert assets
    assert not assets.is_empty()


def test_alphavantage_read_financials():
    ticker = "AAPL"
    AlphaVantageBase.fundamentals = FakeFundamentalData()
    AlphaVantageBase.timeseries = FakeTimeSeries()
    financials = AlphaVantageSource()._read_financials(ticker)
    assert financials


def test_alphavantage_read_series():
    ticker = "AAPL"
    AlphaVantageBase.fundamentals = FakeFundamentalData()
    AlphaVantageBase.timeseries = FakeTimeSeries()
    series = AlphaVantageSource().read_series(
        Ticker(symbol=ticker, exchange="NASDAQ"), "max"
    )
    assert series


@pytest.mark.skip("issue with api key")
def test_api_key():
    alpha = AlphaVantageSource()
    alpha.set_api_key("test")
    assert AlphaVantageCashFlow.from_ticker("AAPL")


@pytest.mark.order(1)
def test_no_api_key():
    with pytest.raises(InvalidApiKeyError):
        AlphaVantageCashFlow.from_ticker("AAPL")
