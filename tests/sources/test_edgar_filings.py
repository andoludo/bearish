"""Tests for the EDGAR filings fetcher and the filed_date backfill."""
import datetime
import json
from pathlib import Path

import pytest

from bearish.models.sec.filing import Filing
from bearish.sources.edgar_filings import parse_submissions

FIXTURE = Path(__file__).parents[1] / "data" / "sources" / "edgar" / "submissions_AAPL.json"
CIK = "0000320193"


def _fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_parse_submissions_keeps_statements_and_8k() -> None:
    filings = parse_submissions(_fixture_payload(), "AAPL", CIK)
    # fixture holds one 10-K, two 10-Q, two 8-K, one form 4 (skipped)
    assert len(filings) == 5
    assert {f.form_type for f in filings} == {"10-K", "10-Q", "8-K"}
    assert all(isinstance(f, Filing) for f in filings)
    assert all(f.items is None for f in filings if f.form_type != "8-K")


def test_parse_submissions_parses_dates() -> None:
    filings = parse_submissions(_fixture_payload(), "AAPL", CIK)
    annual = next(f for f in filings if f.form_type == "10-K")
    assert annual.period_end == datetime.date(2024, 9, 28)
    assert annual.filed_date == datetime.date(2024, 11, 1)
    assert annual.filed_date > annual.period_end
    assert annual.accession_number == "0000320193-24-000123"
    assert annual.cik == CIK
    assert annual.symbol == "AAPL"


def test_parse_submissions_8k_items_and_event_date() -> None:
    by_accession = {f.accession_number: f for f in parse_submissions(_fixture_payload(), "AAPL", CIK)}
    with_event_date = by_accession["0000320193-24-000050"]
    assert with_event_date.period_end == datetime.date(2024, 3, 14)
    assert with_event_date.filed_date == datetime.date(2024, 3, 15)
    assert with_event_date.items == "5.02,9.01"  # whitespace normalised
    assert with_event_date.item_codes() == ["5.02", "9.01"]
    # the 8-K row without a reportDate falls back to the filing date
    without_event_date = by_accession["0000320193-24-000067"]
    assert without_event_date.period_end == without_event_date.filed_date == datetime.date(2024, 5, 1)
    assert without_event_date.item_codes() == ["2.02", "9.01"]


def test_parse_submissions_skips_statements_without_report_date() -> None:
    payload = _fixture_payload()
    recent = payload["filings"]["recent"]
    recent["reportDate"][0] = ""  # the 10-K
    filings = parse_submissions(payload, "AAPL", CIK)
    assert not any(f.form_type == "10-K" for f in filings)


def test_parse_submissions_without_items_key() -> None:
    payload = _fixture_payload()
    payload["filings"]["recent"].pop("items")
    filings = parse_submissions(payload, "AAPL", CIK)
    assert len(filings) == 5
    assert all(f.items is None for f in filings)


def test_parse_submissions_empty_payload() -> None:
    assert parse_submissions({}, "AAPL", CIK) == []


def test_write_filings_is_idempotent(tmp_path) -> None:
    from bearish.database.crud import BearishDb

    filings = parse_submissions(_fixture_payload(), "AAPL", CIK)
    db = BearishDb(database_path=tmp_path / "bear.db")
    db.write_filings(filings)
    db.write_filings(filings)  # re-write: accession_number PK deduplicates

    loaded = db.read_filings("AAPL")
    assert len(loaded) == len(filings)
    assert len({f.accession_number for f in loaded}) == len(filings)
    assert [f.form_type for f in db.read_filings("AAPL", forms=["8-K"])] == ["8-K", "8-K"]
    assert loaded[0].filed_date >= loaded[-1].filed_date  # newest first


def test_backfill_sets_filed_date_only_on_exact_period_match(tmp_path) -> None:
    from bearish.database.crud import BearishDb
    from bearish.models.base import Ticker
    from bearish.models.financials.base import Financials
    from bearish.models.financials.metrics import FinancialMetrics
    from bearish.models.query.query import AssetQuery, Symbols

    db = BearishDb(database_path=tmp_path / "bear.db")
    matching = FinancialMetrics(
        symbol="AAPL", source="Yfinance", date=datetime.date(2024, 9, 28),
        net_income=1.0,
    )
    # an 8-K event date must never be taken as a statement filing date
    event_date_only = FinancialMetrics(
        symbol="AAPL", source="Yfinance", date=datetime.date(2024, 3, 14),
        net_income=4.0,
    )
    non_matching = FinancialMetrics(
        symbol="AAPL", source="Yfinance", date=datetime.date(2023, 9, 30),
        net_income=2.0,
    )
    other_symbol = FinancialMetrics(
        symbol="MSFT", source="Yfinance", date=datetime.date(2024, 9, 28),
        net_income=3.0,
    )
    db.write_financials(
        [Financials(financial_metrics=[matching, non_matching, other_symbol, event_date_only])]
    )
    db.write_filings(parse_submissions(_fixture_payload(), "AAPL", CIK))

    db.backfill_filed_dates()

    loaded = db.read_financials(
        AssetQuery(
            symbols=Symbols(
                equities=[Ticker(symbol="AAPL"), Ticker(symbol="MSFT")]
            )
        )
    ).financial_metrics
    def _as_date(value):
        # read_financials returns statement dates as datetimes
        return value.date() if isinstance(value, datetime.datetime) else value

    by_key = {(m.symbol, _as_date(m.date)): m for m in loaded}
    assert by_key[("AAPL", datetime.date(2024, 9, 28))].filed_date == datetime.date(2024, 11, 1)
    assert by_key[("AAPL", datetime.date(2023, 9, 30))].filed_date is None
    assert by_key[("AAPL", datetime.date(2024, 3, 14))].filed_date is None
    assert by_key[("MSFT", datetime.date(2024, 9, 28))].filed_date is None


@pytest.mark.network
def test_fetch_filings_live() -> None:
    from bearish.sources.edgar_filings import fetch_filings

    filings = fetch_filings(["AAPL"])
    annuals = [f for f in filings if f.form_type == "10-K"]
    assert annuals
    assert all(
        datetime.date(1990, 1, 1) < f.filed_date <= datetime.date.today()
        for f in annuals
    )
    assert all(f.filed_date >= f.period_end for f in annuals)
