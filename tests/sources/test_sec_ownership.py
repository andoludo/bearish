import datetime
import json
import re
from pathlib import Path

import pytest
import requests_mock

import bearish.sources.sec_ownership as MODULE
from bearish.sources.edgar_filings import SUBMISSIONS_URL
from bearish.sources.sec_ownership import (
    fetch_ownership,
    ownership_filings,
    parse_schedule_13dg,
)

DATA = Path(__file__).parents[1] / "data" / "sources" / "sec_ownership"
CIK = "0001145986"  # Aspen Aerogels


class _FakeMapper:
    """Stand-in for sec_cik_mapper.StockMapper, which downloads the SEC ticker file on init."""

    ticker_to_cik = {"ASPN": "1145986"}


@pytest.fixture(autouse=True)
def _offline_cik_mapper(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if "network" in {marker.name for marker in request.node.iter_markers()}:
        return
    monkeypatch.setattr(MODULE, "StockMapper", _FakeMapper)


def test_parse_schedule_13g() -> None:
    rows = parse_schedule_13dg(
        (DATA / "schedule13g_000149315226047542.xml").read_text(),
        "ASPN",
        "0001493152-26-047542",
        "SCHEDULE 13G",
        datetime.date(2026, 10, 19),
    )
    assert [r.reporting_person for r in rows] == ["Orin Hirschman", "AIGH Capital Management LLC"]
    first = rows[0]
    assert first.issuer_cik == CIK
    assert first.issuer_name == "ASPEN AEROGELS, INC."
    assert first.issuer_cusip == "04523Y105"
    assert first.event_date == datetime.date(2026, 9, 30)
    assert first.rule == "Rule 13d-1(b)"
    assert first.percent_of_class == pytest.approx(8.6)
    assert first.shares_owned == pytest.approx(7_150_126)
    assert first.sole_voting == pytest.approx(7_150_126) and first.shared_voting == 0.0
    assert first.person_type == "HC,IN"  # repeated typeOfReportingPerson elements are joined
    assert not first.is_amendment
    assert first.form_type == "SCHEDULE 13G"


def test_parse_schedule_13d_amendment() -> None:
    rows = parse_schedule_13dg(
        (DATA / "schedule13da_000119312526401393.xml").read_text(),
        "ASPN",
        "0001193125-26-401393",
        "SCHEDULE 13D/A",
        datetime.date(2026, 9, 24),
    )
    assert [r.reporting_person for r in rows] == ["Wood River Capital, LLC", "Koch, Inc."]
    wood_river = rows[0]
    assert wood_river.is_amendment
    assert wood_river.event_date == datetime.date(2026, 9, 23)
    assert wood_river.issuer_cik == CIK  # 13D spells the element issuerCIK
    assert wood_river.issuer_cusip == "04523Y105"
    assert wood_river.rule is None  # 13D has no 13d-1 rule designation
    # An exit filing: reported figures are zero, which is a value, not a gap.
    assert wood_river.shares_owned == 0.0
    assert wood_river.percent_of_class == 0.0
    assert wood_river.person_type == "OO"
    assert rows[1].person_type == "CO"


def test_parse_handles_missing_numbers_and_percent_sign() -> None:
    xml = """<?xml version="1.0"?><edgarSubmission xmlns="http://www.sec.gov/edgar/schedule13g"><formData>
    <coverPageHeader><eventDateRequiresFilingThisStatement>12/31/2025</eventDateRequiresFilingThisStatement>
    <issuerInfo><issuerCik>0000000001</issuerCik><issuerName>X</issuerName></issuerInfo></coverPageHeader>
    <coverPageHeaderReportingPersonDetails><reportingPersonName>Some Fund</reportingPersonName>
    <classPercent>5.2%</classPercent>
    <reportingPersonBeneficiallyOwnedAggregateNumberOfShares>1,234,567</reportingPersonBeneficiallyOwnedAggregateNumberOfShares>
    </coverPageHeaderReportingPersonDetails></formData></edgarSubmission>"""
    (row,) = parse_schedule_13dg(xml, "X", "acc", "SCHEDULE 13G", datetime.date(2026, 1, 1))
    assert row.percent_of_class == pytest.approx(5.2)
    assert row.shares_owned == pytest.approx(1_234_567)
    assert row.sole_voting is None and row.shared_dispositive is None
    assert row.issuer_cusip is None and row.person_type is None and row.rule is None


def test_ownership_filings_skips_legacy_text_filings() -> None:
    payload = json.loads((DATA / "submissions_ASPN.json").read_text())
    refs = ownership_filings(payload)
    assert len(refs) == 8
    assert all(form.startswith("SCHEDULE 13") for _, _, _, form in refs)
    assert all(document.endswith("primary_doc.xml") for _, _, document, _ in refs)
    since_2026 = ownership_filings(payload, since=datetime.date(2026, 1, 1))
    assert [a for a, *_ in since_2026] == [
        "0001493152-26-047542",
        "0001193125-26-401393",
        "0000919574-26-005154",
        "0000102909-26-000744",
        "0000919574-26-000984",
    ]


def test_fetch_ownership_offline() -> None:
    archive = re.compile(r"https://www\.sec\.gov/Archives/edgar/data/1145986/(\d+)/primary_doc\.xml")
    documents = {
        "000149315226047542": (DATA / "schedule13g_000149315226047542.xml").read_text(),
        "000119312526401393": (DATA / "schedule13da_000119312526401393.xml").read_text(),
    }

    def _document(request: requests_mock.request._RequestObjectProxy, context: object) -> str:
        return documents[archive.match(request.url).group(1)]

    with requests_mock.Mocker() as req:
        req.get(SUBMISSIONS_URL.format(cik=CIK), text=(DATA / "submissions_ASPN.json").read_text())
        req.get(archive, text=_document)
        rows = fetch_ownership(["ASPN", "NOCIK"], pause=0, max_filings=2)

    assert {r.form_type for r in rows} == {"SCHEDULE 13G", "SCHEDULE 13D/A"}
    assert len(rows) == 4
    assert {r.symbol for r in rows} == {"ASPN"}
    assert req.call_count == 3  # one submissions page + two filings (max_filings)


@pytest.mark.network
def test_fetch_ownership_live() -> None:
    rows = fetch_ownership(["AAPL"], pause=0.2, max_filings=2)
    assert rows
    assert all(r.symbol == "AAPL" and r.issuer_cik == "0000320193" for r in rows)
    assert any(r.percent_of_class is not None and r.percent_of_class > 5 for r in rows)
