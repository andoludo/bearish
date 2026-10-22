import datetime
import json
from pathlib import Path

import pytest
import requests_mock

import bearish.sources.sec_xbrl as MODULE

from bearish.models.base import Ticker
from bearish.sources.sec_xbrl import COMPANYFACTS_URL, SecXbrlSource, parse_companyfacts

FIXTURE = Path(__file__).parents[1] / "data" / "sources" / "sec_xbrl" / "CIK0000320193.json"


class _FakeMapper:
    """Stand-in for sec_cik_mapper.StockMapper, which downloads the SEC ticker file on init."""

    ticker_to_cik = {"AAPL": "320193"}


@pytest.fixture(autouse=True)
def _offline_cik_mapper(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if "network" in {marker.name for marker in request.node.iter_markers()}:
        return
    monkeypatch.setattr(MODULE, "StockMapper", _FakeMapper)


@pytest.fixture
def companyfacts() -> dict:
    return json.loads(FIXTURE.read_text())


def test_parse_companyfacts_annual_rows(companyfacts: dict) -> None:
    financials = parse_companyfacts(companyfacts, "AAPL")
    fy2025 = next(m for m in financials.financial_metrics if m.date == datetime.date(2025, 9, 27))
    assert fy2025.source == "SEC"
    assert fy2025.filed_date == datetime.date(2025, 10, 31)
    assert 300e9 < fy2025.total_revenue < 500e9
    assert 50e9 < fy2025.net_income < 150e9
    assert 5 < fy2025.basic_eps < 10
    assert fy2025.gross_profit == pytest.approx(fy2025.total_revenue - fy2025.cost_of_revenue, rel=1e-6)

    balance = next(b for b in financials.balance_sheets if b.date == datetime.date(2025, 9, 27))
    assert balance.filed_date == datetime.date(2025, 10, 31)
    assert balance.total_assets == pytest.approx(balance.total_liabilities + balance.total_shareholder_equity, rel=1e-6)
    assert 1e10 < balance.common_stock_shares_outstanding < 2e10

    cash_flow = next(c for c in financials.cash_flows if c.date == datetime.date(2025, 9, 27))
    assert cash_flow.operating_cash_flow > 50e9
    assert cash_flow.capital_expenditure < 0  # outflows are stored negative, as yfinance does
    assert cash_flow.repurchase_of_capital_stock < 0


def test_parse_companyfacts_quarterly_rows_exclude_year_to_date(companyfacts: dict) -> None:
    financials = parse_companyfacts(companyfacts, "AAPL")
    quarters = {m.date: m for m in financials.quarterly_financial_metrics}
    assert datetime.date(2026, 6, 27) in quarters
    june = quarters[datetime.date(2026, 6, 27)]
    assert june.filed_date == datetime.date(2026, 7, 31)
    assert 50e9 < june.total_revenue < 150e9  # one quarter, not nine months
    assert all(m.filed_date is not None for m in financials.quarterly_financial_metrics)
    # 10-K balance sheets double as the fourth-quarter snapshot
    assert datetime.date(2025, 9, 27) in {b.date for b in financials.quarterly_balance_sheets}
    assert len(financials.quarterly_cash_flows) >= 10


def test_filed_date_is_the_first_filing_that_reported_the_period(companyfacts: dict) -> None:
    financials = parse_companyfacts(companyfacts, "AAPL")
    fy2024 = next(m for m in financials.financial_metrics if m.date == datetime.date(2024, 9, 28))
    # FY2024 is restated as a comparative in the FY2025 10-K (filed 2025-10-31);
    # the row must keep the original 10-K date.
    assert fy2024.filed_date == datetime.date(2024, 11, 1)


def test_parse_companyfacts_empty_payload() -> None:
    assert parse_companyfacts({"facts": {}}, "X").is_empty()


def test_source_reads_financials_through_the_api(companyfacts: dict) -> None:
    source = SecXbrlSource(delay=0)
    with requests_mock.Mocker() as req:
        req.get(COMPANYFACTS_URL.format(cik="0000320193"), json=companyfacts)
        financials = source.read_financials([Ticker(symbol="AAPL", exchange="NMS"), Ticker(symbol="NOT-A-TICKER")])
    assert len(financials) == 1
    assert financials[0].financial_metrics
    assert req.call_count == 1
    assert req.last_request.headers["User-Agent"]


def test_source_skips_non_us_tickers() -> None:
    source = SecXbrlSource(delay=0)
    with requests_mock.Mocker() as req:
        assert source.read_financials([Ticker(symbol="ML.PA", exchange="PAR")]) == []
        assert req.call_count == 0


@pytest.mark.network
def test_sec_xbrl_live() -> None:
    financials = SecXbrlSource().read_financials([Ticker(symbol="MSFT", exchange="NMS")])
    assert financials and financials[0].financial_metrics
    assert financials[0].financial_metrics[-1].filed_date is not None
