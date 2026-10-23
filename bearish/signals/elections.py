"""US federal general elections 1946-2026 as curated MarketEvents.

Party control of the House and Senate per Congress comes from the official
party-division pages of the House Historian
(https://history.house.gov/Institution/Party-Divisions/Party-Divisions/) and
the Senate Historical Office (https://www.senate.gov/history/partydiv.htm).
The table is kept in code so event studies never depend on those pages being
reachable; ``parse_house_divisions`` / ``parse_senate_divisions`` re-derive it
from the pages and a network test checks the two still agree.

Tags describe the government **after** the election (the new Congress and,
for presidential years, the incoming president):

* ``midterm`` / ``presidential``
* ``unified`` (president's party holds both chambers) / ``divided``
* ``pres_party_lost_house`` / ``pres_party_lost_senate``: the party of the
  president in office on election day controlled the chamber before the
  election and not after
* ``pending`` for an election whose outcome is not known yet (outcome None)
"""

import datetime
import html
import re
from typing import Dict, List, Literal, Optional, Tuple

from bearish.signals.models import MarketEvent

Party = Literal["D", "R"]

# (house majority, senate majority) at the start of each Congress.
# 107th: 50-50 Senate, Republican control through VP Cheney from 20 Jan 2001
# (Democrats from 6 Jun 2001 after Jeffords' switch); the start-of-Congress
# organisation under the new president is used.
CONGRESS_CONTROL: Dict[int, Tuple[Party, Party]] = {
    79: ("D", "D"),
    80: ("R", "R"),
    81: ("D", "D"),
    82: ("D", "D"),
    83: ("R", "R"),
    84: ("D", "D"),
    85: ("D", "D"),
    86: ("D", "D"),
    87: ("D", "D"),
    88: ("D", "D"),
    89: ("D", "D"),
    90: ("D", "D"),
    91: ("D", "D"),
    92: ("D", "D"),
    93: ("D", "D"),
    94: ("D", "D"),
    95: ("D", "D"),
    96: ("D", "D"),
    97: ("D", "R"),
    98: ("D", "R"),
    99: ("D", "R"),
    100: ("D", "D"),
    101: ("D", "D"),
    102: ("D", "D"),
    103: ("D", "D"),
    104: ("R", "R"),
    105: ("R", "R"),
    106: ("R", "R"),
    107: ("R", "R"),
    108: ("R", "R"),
    109: ("R", "R"),
    110: ("D", "D"),
    111: ("D", "D"),
    112: ("R", "D"),
    113: ("R", "D"),
    114: ("R", "R"),
    115: ("R", "R"),
    116: ("D", "R"),
    117: ("D", "D"),
    118: ("R", "D"),
    119: ("R", "R"),
}

# Presidential terms (party, inauguration date) since 1945.
PRESIDENCIES: Tuple[Tuple[datetime.date, Party, str], ...] = (
    (datetime.date(1945, 4, 12), "D", "Truman"),
    (datetime.date(1953, 1, 20), "R", "Eisenhower"),
    (datetime.date(1961, 1, 20), "D", "Kennedy/Johnson"),
    (datetime.date(1969, 1, 20), "R", "Nixon/Ford"),
    (datetime.date(1977, 1, 20), "D", "Carter"),
    (datetime.date(1981, 1, 20), "R", "Reagan/Bush"),
    (datetime.date(1993, 1, 20), "D", "Clinton"),
    (datetime.date(2001, 1, 20), "R", "Bush"),
    (datetime.date(2009, 1, 20), "D", "Obama"),
    (datetime.date(2017, 1, 20), "R", "Trump"),
    (datetime.date(2021, 1, 20), "D", "Biden"),
    (datetime.date(2025, 1, 20), "R", "Trump"),
)

FIRST_ELECTION_YEAR = 1946
LAST_ELECTION_YEAR = 2026
CURATED_AS_OF = datetime.date(2026, 10, 23)


def election_day(year: int) -> datetime.date:
    """The Tuesday after the first Monday in November."""
    first = datetime.date(year, 11, 1)
    first_monday = first + datetime.timedelta(days=(0 - first.weekday()) % 7)
    return first_monday + datetime.timedelta(days=1)


def president_party(on: datetime.date) -> Party:
    party: Optional[Party] = None
    for start, term_party, _ in PRESIDENCIES:
        if on >= start:
            party = term_party
    if party is None:
        raise ValueError(f"No presidency recorded for {on}")
    return party


def congress_elected_in(year: int) -> int:
    """Number of the Congress chosen by the general election held in ``year``."""
    return 80 + (year - FIRST_ELECTION_YEAR) // 2


def _election(year: int) -> MarketEvent:
    day = election_day(year)
    presidential = year % 4 == 0
    kind = "presidential" if presidential else "midterm"
    incumbent = president_party(day)
    after = CONGRESS_CONTROL.get(congress_elected_in(year))
    before = CONGRESS_CONTROL[congress_elected_in(year) - 1]
    tags: List[str] = [kind]
    outcome: Optional[str] = None
    if after is None:
        tags.append("pending")
    else:
        new_president = president_party(datetime.date(year + 1, 1, 21)) if presidential else incumbent
        house, senate = after
        tags.append("unified" if house == senate == new_president else "divided")
        if before[0] == incumbent and house != incumbent:
            tags.append("pres_party_lost_house")
        if before[1] == incumbent and senate != incumbent:
            tags.append("pres_party_lost_senate")
        outcome = f"PRES={new_president},HOUSE={house},SENATE={senate}"
    return MarketEvent(
        event_id=f"US_{'PRES' if presidential else 'MIDTERM'}_{year}",
        event_type="election",
        name=f"{year} US {'presidential' if presidential else 'midterm'} election",
        date=day,
        country="USA",
        tags=",".join(tags),
        outcome=outcome,
        description=f"President's party on election day: {incumbent}; before: HOUSE={before[0]},SENATE={before[1]}",
        source="curated: House Historian / Senate Historical Office party divisions",
        as_of=CURATED_AS_OF,
    )


US_ELECTIONS: Tuple[MarketEvent, ...] = tuple(
    _election(year) for year in range(FIRST_ELECTION_YEAR, LAST_ELECTION_YEAR + 1, 2)
)


def midterms(include_pending: bool = False) -> List[MarketEvent]:
    return [e for e in US_ELECTIONS if "midterm" in e.tag_set() and (include_pending or "pending" not in e.tag_set())]


# --- verification against the official pages ------------------------------------

HOUSE_DIVISIONS_URL = "https://history.house.gov/Institution/Party-Divisions/Party-Divisions/"
SENATE_DIVISIONS_URL = "https://www.senate.gov/history/partydiv.htm"


def _flatten(page: str) -> str:
    text = re.sub(r"<script.*?</script>", "", page, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "|", text)
    text = html.unescape(text)
    text = re.sub(r"\|\s*(\|\s*)+", "|", text)
    return re.sub(r"\s+", " ", text)


def parse_house_divisions(page: str) -> Dict[int, Party]:
    """Majority party per Congress from the House Historian table (79th onward)."""
    control: Dict[int, Party] = {}
    pattern = re.compile(r"(\d+)(?:st|nd|rd|th) \((\d{4})[\u2013-](\d{4})\)\|(\d{3})\|(?:\d\|)?(\d{2,3})\|(\d{2,3})\|")
    for match in pattern.finditer(_flatten(page)):
        congress, democrats, republicans = int(match.group(1)), int(match.group(5)), int(match.group(6))
        if congress >= min(CONGRESS_CONTROL):
            control[congress] = "D" if democrats > republicans else "R"
    return control


def parse_senate_divisions(page: str) -> Dict[int, Party]:
    """Majority party per Congress from the Senate page (first listed majority)."""
    control: Dict[int, Party] = {}
    pattern = re.compile(
        r"(\d+)(?:st|nd|rd|th) Congress \((\d{4})\u2013(\d{4})\)\|\s*Majority Party[^:]*:\s*(Democrats|Republicans)"
    )
    for match in pattern.finditer(_flatten(page)):
        congress = int(match.group(1))
        if congress >= min(CONGRESS_CONTROL):
            control.setdefault(congress, "D" if match.group(4) == "Democrats" else "R")
    return control
