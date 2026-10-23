import datetime
from pathlib import Path

import pytest
import requests

from bearish.signals.elections import (
    CONGRESS_CONTROL,
    HOUSE_DIVISIONS_URL,
    SENATE_DIVISIONS_URL,
    US_ELECTIONS,
    election_day,
    midterms,
    parse_house_divisions,
    parse_senate_divisions,
    president_party,
)

DATA_DIR = Path(__file__).parents[1] / "data" / "signals" / "elections"
BY_ID = {e.event_id: e for e in US_ELECTIONS}
# 107th Congress: 50-50 Senate; the Senate page lists the Gore-VP majority (3-20 Jan 2001) first,
# the curated table records the Republican organisation under the new administration.
KNOWN_SENATE_DIFFERENCES = {107}


def test_every_federal_election_from_1946_to_2026() -> None:
    years = sorted(e.date.year for e in US_ELECTIONS)
    assert years == list(range(1946, 2027, 2))
    assert all(e.event_type == "election" and e.country == "USA" for e in US_ELECTIONS)
    assert len(midterms()) == 20
    assert BY_ID["US_MIDTERM_2026"].outcome is None
    assert BY_ID["US_MIDTERM_2026"].tag_set() == {"midterm", "pending"}
    assert midterms(include_pending=True)[-1].event_id == "US_MIDTERM_2026"


@pytest.mark.parametrize(
    ("year", "expected"),
    [
        (2026, datetime.date(2026, 11, 3)),
        (2022, datetime.date(2022, 11, 8)),
        (2020, datetime.date(2020, 11, 3)),
        (1994, datetime.date(1994, 11, 8)),
    ],
)
def test_election_day_is_tuesday_after_first_monday(year: int, expected: datetime.date) -> None:
    assert election_day(year) == expected


@pytest.mark.parametrize(
    ("event_id", "outcome", "tags"),
    [
        ("US_MIDTERM_2018", "PRES=R,HOUSE=D,SENATE=R", {"midterm", "divided", "pres_party_lost_house"}),
        ("US_MIDTERM_2022", "PRES=D,HOUSE=R,SENATE=D", {"midterm", "divided", "pres_party_lost_house"}),
        ("US_MIDTERM_2010", "PRES=D,HOUSE=R,SENATE=D", {"midterm", "divided", "pres_party_lost_house"}),
        (
            "US_MIDTERM_1994",
            "PRES=D,HOUSE=R,SENATE=R",
            {"midterm", "divided", "pres_party_lost_house", "pres_party_lost_senate"},
        ),
        (
            "US_MIDTERM_2006",
            "PRES=R,HOUSE=D,SENATE=D",
            {"midterm", "divided", "pres_party_lost_house", "pres_party_lost_senate"},
        ),
        ("US_MIDTERM_2002", "PRES=R,HOUSE=R,SENATE=R", {"midterm", "unified"}),
        ("US_PRES_2024", "PRES=R,HOUSE=R,SENATE=R", {"presidential", "unified", "pres_party_lost_senate"}),
        ("US_PRES_2008", "PRES=D,HOUSE=D,SENATE=D", {"presidential", "unified"}),
    ],
)
def test_known_outcomes(event_id: str, outcome: str, tags: set) -> None:
    event = BY_ID[event_id]
    assert event.outcome == outcome
    assert event.tag_set() == tags


def test_president_party() -> None:
    assert president_party(datetime.date(2018, 11, 6)) == "R"
    assert president_party(datetime.date(2021, 1, 19)) == "R"
    assert president_party(datetime.date(2021, 1, 20)) == "D"


def test_curated_table_matches_official_pages() -> None:
    house = parse_house_divisions((DATA_DIR / "house_party_divisions.html").read_text())
    senate = parse_senate_divisions((DATA_DIR / "senate_partydiv.html").read_text())
    assert set(CONGRESS_CONTROL) <= set(house)
    assert {c for c, (h, _) in CONGRESS_CONTROL.items() if house[c] != h} == set()
    assert {c for c, (_, s) in CONGRESS_CONTROL.items() if senate[c] != s} == KNOWN_SENATE_DIFFERENCES


@pytest.mark.network
def test_curated_table_matches_live_pages() -> None:
    headers = {"User-Agent": "bearish (https://github.com/andoludo/bearish)"}
    house = parse_house_divisions(requests.get(HOUSE_DIVISIONS_URL, headers=headers, timeout=60).text)
    senate = parse_senate_divisions(requests.get(SENATE_DIVISIONS_URL, headers=headers, timeout=60).text)
    assert {c for c, (h, _) in CONGRESS_CONTROL.items() if house.get(c) != h} == set()
    assert {c for c, (_, s) in CONGRESS_CONTROL.items() if senate.get(c) != s} == KNOWN_SENATE_DIFFERENCES
