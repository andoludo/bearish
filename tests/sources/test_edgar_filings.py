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


def test_parse_submissions_filters_to_10k_10q() -> None:
    filings = parse_submissions(_fixture_payload(), "AAPL", CIK)
    # fixture holds one 10-K, two 10-Q, one 8-K (skipped), one form 4 (skipped)
    assert len(filings) == 3
    assert {f.form_type for f in filings} == {"10-K", "10-Q"}
    assert all(isinstance(f, Filing) for f in filings)


def test_parse_submissions_parses_dates() -> None:
    filings = parse_submissions(_fixture_payload(), "AAPL", CIK)
    annual = next(f for f in filings if f.form_type == "10-K")
    assert annual.period_end == datetime.date(2024, 9, 28)
    assert annual.filed_date == datetime.date(2024, 11, 1)
    assert annual.filed_date > annual.period_end
    assert annual.accession_number == "0000320193-24-000123"
    assert annual.cik == CIK
    assert annual.symbol == "AAPL"


def test_parse_submissions_skips_rows_without_report_date() -> None:
    filings = parse_submissions(_fixture_payload(), "AAPL", CIK)
    # the 8-K row has an empty reportDate AND a non-10-K/Q form
    assert not any(f.accession_number == "0000320193-24-000067" for f in filings)


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
    non_matching = FinancialMetrics(
        symbol="AAPL", source="Yfinance", date=datetime.date(2023, 9, 30),
        net_income=2.0,
    )
    other_symbol = FinancialMetrics(
        symbol="MSFT", source="Yfinance", date=datetime.date(2024, 9, 28),
        net_income=3.0,
    )
    db.write_financials(
        [Financials(financial_metrics=[matching, non_matching, other_symbol])]
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
