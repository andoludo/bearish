import datetime
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.signals.fomc import CALENDAR_URL, fetch_fomc_meetings, parse_calendar_page, parse_historical_page

DATA_DIR = Path(__file__).parents[1] / "data" / "signals" / "fomc"
TODAY = datetime.date(2026, 10, 23)


def test_parse_calendar_page() -> None:
    events = {e.event_id: e for e in parse_calendar_page((DATA_DIR / "fomccalendars.html").read_text(), TODAY)}
    assert events["FOMC_2026-03-18"].tag_set() == {"scheduled", "sep"}
    assert events["FOMC_2026-01-28"].tag_set() == {"scheduled"}
    assert events["FOMC_2025-08-22"].tag_set() == {"notation_vote"}
    assert events["FOMC_2026-10-28"].tag_set() == {"scheduled", "upcoming"}
    # cross-month meeting "Apr/May 30-1" -> decision on 1 May
    assert "FOMC_2024-05-01" in events
    assert all(e.event_type == "fomc" and e.date.year >= 2021 for e in events.values())


def test_parse_historical_pages() -> None:
    events_2020 = {e.date: e for e in parse_historical_page((DATA_DIR / "fomchistorical2020.html").read_text(), TODAY)}
    assert events_2020[datetime.date(2020, 3, 15)].tag_set() == {"unscheduled"}
    assert events_2020[datetime.date(2020, 3, 19)].tag_set() == {"notation_vote"}
    assert datetime.date(2020, 3, 18) not in events_2020  # cancelled meeting
    assert events_2020[datetime.date(2020, 1, 29)].tag_set() == {"scheduled"}
    events_2001 = {e.date: e for e in parse_historical_page((DATA_DIR / "fomchistorical2001.html").read_text(), TODAY)}
    assert events_2001[datetime.date(2001, 9, 17)].tag_set() == {"unscheduled"}  # post-9/11 conference call
    assert events_2001[datetime.date(2001, 1, 31)].tag_set() == {"scheduled"}  # January 30-31 meeting


def test_fetch_combines_historical_and_calendar_pages() -> None:
    with requests_mock.Mocker() as req:
        req.get(CALENDAR_URL, text=(DATA_DIR / "fomccalendars.html").read_text())
        # requests_mock tries the most recently registered matcher first
        req.get(re.compile(r".*fomchistorical\d{4}\.htm"), status_code=404)
        req.get(re.compile(r".*fomchistorical2020\.htm"), text=(DATA_DIR / "fomchistorical2020.html").read_text())
        events = fetch_fomc_meetings(start_year=2019, pause=0)
    years = {e.date.year for e in events}
    assert {2020, 2021, 2026} <= years
    assert 2019 not in years  # its page failed: logged and skipped
    assert [e.date for e in events] == sorted(e.date for e in events)


@pytest.mark.network
def test_fetch_fomc_live() -> None:
    events = fetch_fomc_meetings(start_year=datetime.date.today().year - 1, pause=0.5)
    assert len(events) >= 8
