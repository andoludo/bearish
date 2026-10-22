import datetime
import json
import re
from pathlib import Path

import pytest
import requests_mock

import bearish.sources.sec_insiders as MODULE

from bearish.sources.edgar_filings import SUBMISSIONS_URL
from bearish.sources.sec_insiders import (
    fetch_insider_transactions,
    insider_filings,
    parse_form4,
    xml_document_name,
)

DATA = Path(__file__).parents[1] / "data" / "sources" / "sec_insiders"


class _FakeMapper:
    """Stand-in for sec_cik_mapper.StockMapper, which downloads the SEC ticker file on init."""

    ticker_to_cik = {"AAPL": "320193"}


@pytest.fixture(autouse=True)
def _offline_cik_mapper(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if "network" in {marker.name for marker in request.node.iter_markers()}:
        return
    monkeypatch.setattr(MODULE, "StockMapper", _FakeMapper)


CIK = "0000320193"


def test_parse_form4_non_derivative_and_derivative_lines() -> None:
    rows = parse_form4(
        (DATA / "form4_000114036126040127.xml").read_text(),
        "AAPL",
        CIK,
        "0001140361-26-040127",
        datetime.date(2026, 10, 19),
    )
    assert len(rows) == 11
    assert [r.line_no for r in rows] == list(range(1, 12))
    first = rows[0]
    assert first.reporting_owner == "Borders Ben"
    assert first.owner_relationship == "officer"
    assert first.officer_title == "Principal Accounting Officer"
    assert first.transaction_code == "M"
    assert first.acquired_disposed == "A"
    assert first.price is None and first.value is None
    assert first.shares_owned_after == 40451
    assert not first.is_derivative
    derivatives = [r for r in rows if r.is_derivative]
    assert derivatives and all(r.security_title == "Restricted Stock Unit" for r in derivatives)
    sales = [r for r in rows if r.transaction_code == "S"]
    assert sales and all(r.acquired_disposed == "D" and r.value == pytest.approx(r.shares * r.price) for r in sales)


def test_parse_form4_open_market_sale() -> None:
    rows = parse_form4(
        (DATA / "form4_000114036126039785.xml").read_text(), "AAPL", CIK, "acc", datetime.date(2026, 10, 15)
    )
    assert len(rows) == 1
    sale = rows[0]
    assert sale.transaction_date == datetime.date(2026, 10, 13)
    assert (sale.transaction_code, sale.acquired_disposed) == ("S", "D")
    assert sale.value == pytest.approx(2399 * 345.0)
    assert sale.source == "SEC"


def test_insider_filings_filters_forms_and_dates() -> None:
    payload = json.loads((DATA / "submissions_AAPL.json").read_text())
    refs = insider_filings(payload)
    assert len(refs) == 5
    assert refs[0][0] == "0001140361-26-040127"
    assert insider_filings(payload, since=datetime.date(2026, 10, 15))[-1][1] >= datetime.date(2026, 10, 15)
    assert len(insider_filings(payload, since=datetime.date(2026, 10, 15))) == 3
    assert xml_document_name("xslF345X06/form4.xml") == "form4.xml"
    assert xml_document_name("primary.html") is None


def test_fetch_insider_transactions_with_mocked_edgar() -> None:
    payload = json.loads((DATA / "submissions_AAPL.json").read_text())
    with requests_mock.Mocker() as req:
        req.get(SUBMISSIONS_URL.format(cik=CIK), json=payload)
        req.get(
            re.compile(r"https://www\.sec\.gov/Archives/edgar/data/320193/(\d+)/form4\.xml"),
            text=lambda request, context: (
                (DATA / f"form4_{request.url.rsplit('/', 2)[-2]}.xml").read_text()
                if (DATA / f"form4_{request.url.rsplit('/', 2)[-2]}.xml").exists()
                else "<ownershipDocument/>"
            ),
        )
        transactions = fetch_insider_transactions(["AAPL", "ML.PA"], pause=0, max_filings=3)
    assert {t.accession_number for t in transactions} == {"0001140361-26-040127", "0001140361-26-039785"}
    assert len(transactions) == 12
    assert all(t.symbol == "AAPL" and t.cik == CIK for t in transactions)
    assert {t.filed_date for t in transactions} == {datetime.date(2026, 10, 19), datetime.date(2026, 10, 15)}


@pytest.mark.network
def test_fetch_insider_transactions_live() -> None:
    transactions = fetch_insider_transactions(["AAPL"], max_filings=2)
    assert transactions
    assert all(t.transaction_date <= datetime.date.today() for t in transactions)
