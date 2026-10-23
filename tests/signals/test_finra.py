import datetime
import json
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.signals.sources.finra import (
    PUBLICATION_LAG,
    SHORT_INTEREST_URL,
    fetch_short_interest,
    fetch_short_volume,
    parse_short_volume,
    short_interest_rows,
    short_interest_signals,
)

DATA = Path(__file__).parents[1] / "data" / "signals" / "finra"
D = datetime.date
ROWS = json.loads((DATA / "short_interest_amd_nvda_2026.json").read_text())


def test_short_interest_signals_are_published_with_a_lag() -> None:
    signals = short_interest_signals(ROWS, fetched_on=D(2026, 10, 23))
    by_key = {(s.symbol, s.signal, s.date): s for s in signals}
    assert {s.symbol for s in signals} == {"AMD", "NVDA"}
    assert {s.signal for s in signals} == {"SHORT_INTEREST", "DAYS_TO_COVER", "SHORT_INTEREST_CHG"}
    nvda = by_key[("NVDA", "SHORT_INTEREST", D(2026, 9, 30))]
    assert nvda.value > 1e8
    assert nvda.as_of == D(2026, 9, 30) + PUBLICATION_LAG
    latest = max(s.date for s in signals)
    # a settlement fetched before its nominal publication date is stamped with the fetch date
    assert by_key[("NVDA", "SHORT_INTEREST", latest)].as_of <= D(2026, 10, 23)


def test_short_interest_rows_paginates_on_record_total() -> None:
    with requests_mock.Mocker() as req:
        req.post(
            SHORT_INTEREST_URL,
            [
                {"json": ROWS[:20], "headers": {"record-total": str(len(ROWS))}},
                {"json": ROWS[20:], "headers": {"record-total": str(len(ROWS))}},
            ],
        )
        import bearish.signals.sources.finra as finra

        original = finra.PAGE_LIMIT
        finra.PAGE_LIMIT = 20
        try:
            rows = short_interest_rows(["nvda", "AMD"], D(2026, 1, 1), D(2026, 10, 23), pause=0)
        finally:
            finra.PAGE_LIMIT = original
    assert len(rows) == len(ROWS)
    first_body = req.request_history[0].json()
    assert first_body["domainFilters"][0]["values"] == ["AMD", "NVDA"]
    assert first_body["dateRangeFilters"][0]["startDate"] == "2026-01-01"
    assert req.request_history[1].json()["offset"] == 20


def test_parse_short_volume_skips_trailer_and_filters() -> None:
    text = (DATA / "CNMSshvol20261021.txt").read_text()
    everyone = parse_short_volume(text)
    assert {s.symbol for s in everyone} == {"AAPL", "AMD", "MSFT", "NVDA", "SMCI", "VRT"}
    nvda = parse_short_volume(text, {"NVDA"})
    assert len(nvda) == 1
    assert nvda[0].signal == "SHORT_VOLUME_RATIO"
    assert 0 < nvda[0].value < 1
    assert nvda[0].date == nvda[0].as_of == D(2026, 10, 21)


def test_fetch_short_volume_skips_weekends_and_missing_days() -> None:
    text = (DATA / "CNMSshvol20261021.txt").read_text()
    with requests_mock.Mocker() as req:
        # requests_mock gives precedence to the matcher registered last
        req.get(re.compile(r"https://cdn\.finra\.org/.*"), status_code=403)
        req.get(re.compile(r"https://cdn\.finra\.org/.*CNMSshvol20261021\.txt"), text=text)
        signals = fetch_short_volume(days=7, symbols=["nvda"], end=D(2026, 10, 25), pause=0)
    # 25 Oct 2026 is a Sunday: 7 calendar days hold 5 weekdays, one of which has a file
    assert req.call_count == 5
    assert [(s.symbol, s.date) for s in signals] == [("NVDA", D(2026, 10, 21))]


@pytest.mark.network
def test_short_interest_live() -> None:
    signals = fetch_short_interest(["NVDA"], datetime.date.today() - datetime.timedelta(days=60))
    assert any(s.signal == "SHORT_INTEREST" for s in signals)
