"""FOMC meeting calendar from federalreserve.gov as MarketEvents.

Two page layouts are parsed:

* the meeting calendar (https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm),
  covering the last five years and the scheduled ones ahead: month/day cells,
  ``*`` marks meetings with a Summary of Economic Projections, ``(notation
  vote)`` / ``(unscheduled)`` qualifiers;
* the yearly historical pages (``fomchistorical{year}.htm``), whose headings read
  ``January 27-28 Meeting - 2015`` / ``March 15 (unscheduled) Meeting - 2020`` /
  ``September 17 Conference Call - 2001``.

The event date is the decision day, i.e. the last day of the meeting. Tags:
``scheduled`` (regular meeting), ``unscheduled`` (unscheduled meeting or
conference call), ``notation_vote``, ``sep`` (projections released) and
``upcoming`` for meetings after today. Cancelled meetings are dropped.
"""

import datetime
import logging
import re
import time
from typing import Dict, Iterable, List, Optional

import requests

from bearish.signals.models import MarketEvent

logger = logging.getLogger(__name__)

CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
HISTORICAL_URL = "https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm"
HEADERS = {"User-Agent": "bearish (https://github.com/andoludo/bearish)"}
SOURCE = "Federal Reserve FOMC calendar"
_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        1,
    )
}
_MONTHS.update({name[:3]: number for name, number in list(_MONTHS.items())})

_YEAR_PANEL = re.compile(r"<h4><a id=\"\d+\">(\d{4}) FOMC Meetings</a></h4>(.*?)(?=<h4><a id=|\Z)", re.DOTALL)
_MEETING_ROW = re.compile(
    r"fomc-meeting__month[^>]*><strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<(.*?)(?=fomc-meeting__month|\Z)",
    re.DOTALL,
)
_HEADING = re.compile(
    r"^(?P<month>[A-Za-z]+) (?P<day>\d{1,2})(?:-(?:(?P<month2>[A-Za-z]+) )?(?P<day2>\d{1,2}))?"
    r"(?: \((?P<qualifier>[^)]+)\))?\s*(?P<kind>Meeting|Conference Call)?\s*-\s*(?P<year>\d{4})$"
)


def _month(name: str) -> int:
    key = name.strip().lower()
    return _MONTHS[key] if key in _MONTHS else _MONTHS[key[:3]]


def _event(day: datetime.date, tags: Iterable[str], name: str, today: datetime.date) -> MarketEvent:
    tag_list = list(dict.fromkeys(tags))
    if day > today:
        tag_list.append("upcoming")
    return MarketEvent(
        event_id=f"FOMC_{day.isoformat()}",
        event_type="fomc",
        name=name,
        date=day,
        country="USA",
        tags=",".join(tag_list),
        source=SOURCE,
        as_of=today,
    )


def parse_calendar_page(page: str, today: Optional[datetime.date] = None) -> List[MarketEvent]:
    """Meetings listed on the current calendar page (several years per page)."""
    today = today or datetime.date.today()
    events: List[MarketEvent] = []
    for year_text, panel in _YEAR_PANEL.findall(page):
        year = int(year_text)
        for month_text, raw_date, rest in _MEETING_ROW.findall(panel):
            date_text = raw_date.strip()
            qualifier = re.search(r"\(([^)]+)\)", date_text)
            label = qualifier.group(1).lower() if qualifier else ""
            if "cancel" in label:
                continue
            days = re.findall(r"\d{1,2}", date_text)
            months = [m for m in re.split(r"[/-]", month_text.strip()) if m]
            if not days:
                continue
            end_month = _month(months[-1])
            end_year = year + 1 if len(months) > 1 and end_month < _month(months[0]) else year
            day = datetime.date(end_year, end_month, int(days[-1]))
            tags = (
                ["notation_vote"]
                if "notation" in label
                else ["unscheduled"]
                if "unscheduled" in label
                else ["scheduled"]
            )
            if "*" in date_text or "Projection Materials" in rest:
                tags.append("sep")
            events.append(_event(day, tags, f"FOMC {label or 'meeting'} {day.isoformat()}", today))
    return events


def parse_historical_page(page: str, today: Optional[datetime.date] = None) -> List[MarketEvent]:
    """Meetings and conference calls from one ``fomchistorical{year}.htm`` page."""
    today = today or datetime.date.today()
    events: List[MarketEvent] = []
    for heading in re.findall(r"<h5[^>]*>([^<]*)</h5>", page):
        match = _HEADING.match(heading.strip())
        if match is None:
            continue
        qualifier = (match.group("qualifier") or "").lower()
        if "cancel" in qualifier:
            continue
        year = int(match.group("year"))
        month = _month(match.group("month2") or match.group("month"))
        day = datetime.date(year, month, int(match.group("day2") or match.group("day")))
        if "notation" in qualifier:
            tags = ["notation_vote"]
        elif "unscheduled" in qualifier or match.group("kind") == "Conference Call":
            tags = ["unscheduled"]
        else:
            tags = ["scheduled"]
        events.append(_event(day, tags, f"FOMC {heading.strip()}", today))
    return events


def _get(url: str, timeout: int = 60) -> str:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_fomc_meetings(
    start_year: int = 1994, end_year: Optional[int] = None, pause: float = 1.0
) -> List[MarketEvent]:
    """FOMC meetings from ``start_year`` on: calendar page for recent years, historical pages before."""
    today = datetime.date.today()
    calendar = parse_calendar_page(_get(CALENDAR_URL), today)
    by_id: Dict[str, MarketEvent] = {e.event_id: e for e in calendar if e.date.year >= start_year}
    first_calendar_year = min((e.date.year for e in calendar), default=today.year)
    for year in range(start_year, min(first_calendar_year, (end_year or today.year) + 1)):
        time.sleep(pause)
        try:
            for event in parse_historical_page(_get(HISTORICAL_URL.format(year=year)), today):
                by_id.setdefault(event.event_id, event)
        except requests.RequestException as e:
            logger.warning(f"Could not read FOMC historical page for {year}: {e}")
    events = [e for e in by_id.values() if end_year is None or e.date.year <= end_year]
    return sorted(events, key=lambda e: e.date)
