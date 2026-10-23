"""Curated geopolitical shocks and sanctions-wave detection.

``CONFLICT_EVENTS`` lists the onset dates of market-relevant geopolitical
shocks since 1990 so event studies can measure returns around them. Dates are
the day the shock became public (local date of the attack, invasion or
strike); for weekend events the first trading day after is the natural
event-study anchor.
"""

import datetime
from typing import List, Tuple

import pandas as pd

from bearish.interface.interface import BearishDbBase
from bearish.macro.models import MacroQuery
from bearish.signals.models import MarketEvent

CURATED_AS_OF = datetime.date(2026, 10, 23)
WAVE_THRESHOLD = 50


def _conflict(event_id: str, name: str, day: str, country: str, tags: str, description: str) -> MarketEvent:  # noqa: PLR0913
    return MarketEvent(
        event_id=f"CONFLICT_{event_id}",
        event_type="conflict",
        name=name,
        date=datetime.date.fromisoformat(day),
        country=country,
        tags=tags,
        description=description,
        source="curated",
        as_of=CURATED_AS_OF,
    )


CONFLICT_EVENTS: Tuple[MarketEvent, ...] = (
    _conflict(
        "IRQ_KWT_1990",
        "Iraq invades Kuwait",
        "1990-08-02",
        "IRQ",
        "war,oil,MENA",
        "Iraqi forces cross into Kuwait; oil prices double over the following weeks.",
    ),
    _conflict(
        "DESERT_STORM_1991",
        "Operation Desert Storm begins",
        "1991-01-17",
        "IRQ",
        "war,oil,MENA,us_involved",
        "US-led coalition air campaign against Iraq.",
    ),
    _conflict(
        "NATO_YUG_1999",
        "NATO bombing of Yugoslavia",
        "1999-03-24",
        "SRB",
        "war,EUR,us_involved",
        "NATO air campaign over Kosovo.",
    ),
    _conflict(
        "SEPT11_2001",
        "September 11 attacks",
        "2001-09-11",
        "USA",
        "terror,US",
        "Attacks on New York and Washington; US markets closed until 17 September.",
    ),
    _conflict(
        "AFG_2001",
        "US invasion of Afghanistan",
        "2001-10-07",
        "AFG",
        "war,ASIA,us_involved",
        "Operation Enduring Freedom begins.",
    ),
    _conflict(
        "IRQ_2003", "Invasion of Iraq", "2003-03-20", "IRQ", "war,oil,MENA,us_involved", "US-led invasion of Iraq."
    ),
    _conflict(
        "ISR_LBN_2006",
        "Israel-Hezbollah war",
        "2006-07-12",
        "LBN",
        "war,MENA",
        "Hezbollah cross-border raid triggers a 34-day war.",
    ),
    _conflict(
        "RUS_GEO_2008",
        "Russo-Georgian war",
        "2008-08-08",
        "GEO",
        "war,EUR,russia",
        "Russian forces enter South Ossetia and Georgia.",
    ),
    _conflict(
        "KOR_YEONPYEONG_2010",
        "Shelling of Yeonpyeong",
        "2010-11-23",
        "KOR",
        "war,ASIA,korea",
        "North Korean artillery strike on a South Korean island.",
    ),
    _conflict(
        "LBY_2011",
        "Libyan uprising",
        "2011-02-17",
        "LBY",
        "war,oil,MENA",
        "Uprising and civil war cut Libyan oil output.",
    ),
    _conflict(
        "CRIMEA_2014",
        "Russia seizes Crimea",
        "2014-02-27",
        "UKR",
        "war,EUR,russia",
        "Unmarked Russian troops seize the Crimean parliament.",
    ),
    _conflict(
        "ISIS_MOSUL_2014",
        "ISIS captures Mosul",
        "2014-06-10",
        "IRQ",
        "war,terror,oil,MENA",
        "Islamic State takes Iraq's second city.",
    ),
    _conflict(
        "PARIS_2015", "Paris attacks", "2015-11-13", "FRA", "terror,EUR", "Coordinated terrorist attacks in Paris."
    ),
    _conflict(
        "TUR_COUP_2016",
        "Turkish coup attempt",
        "2016-07-15",
        "TUR",
        "political,EUR,MENA",
        "Failed military coup in Turkey.",
    ),
    _conflict(
        "PRK_FIRE_FURY_2017",
        "'Fire and fury' North Korea standoff",
        "2017-08-08",
        "PRK",
        "nuclear,ASIA,korea,us_involved",
        "US-North Korea nuclear threats escalate.",
    ),
    _conflict(
        "IND_PAK_BALAKOT_2019",
        "Balakot airstrike",
        "2019-02-26",
        "PAK",
        "war,ASIA,nuclear",
        "Indian airstrike in Pakistan after the Pulwama attack.",
    ),
    _conflict(
        "ABQAIQ_2019",
        "Abqaiq-Khurais attack",
        "2019-09-14",
        "SAU",
        "oil,MENA,iran",
        "Drone and missile strike halves Saudi oil processing.",
    ),
    _conflict(
        "SOLEIMANI_2020",
        "US kills Qassem Soleimani",
        "2020-01-03",
        "IRN",
        "war,oil,MENA,iran,us_involved",
        "US drone strike in Baghdad; Iran retaliates on 8 January.",
    ),
    _conflict(
        "RUS_UKR_2022",
        "Russia invades Ukraine",
        "2022-02-24",
        "UKR",
        "war,oil,gas,grains,EUR,russia",
        "Full-scale Russian invasion of Ukraine.",
    ),
    _conflict(
        "TWN_PELOSI_2022",
        "Pelosi visit to Taiwan",
        "2022-08-02",
        "TWN",
        "tension,ASIA,taiwan,us_involved",
        "Visit followed by large Chinese military drills around Taiwan.",
    ),
    _conflict(
        "ISR_HAMAS_2023",
        "Hamas attack on Israel",
        "2023-10-07",
        "ISR",
        "war,terror,MENA",
        "Hamas attack and the Gaza war that follows.",
    ),
    _conflict(
        "RED_SEA_2023",
        "Houthi attacks on Red Sea shipping",
        "2023-11-19",
        "YEM",
        "shipping,oil,MENA",
        "Seizure of the Galaxy Leader; container lines divert around the Cape.",
    ),
    _conflict(
        "US_UK_HOUTHI_2024",
        "US and UK strike the Houthis",
        "2024-01-12",
        "YEM",
        "war,shipping,MENA,us_involved",
        "First coalition strikes on Houthi targets in Yemen.",
    ),
    _conflict(
        "IRN_ISR_APR_2024",
        "Iran's drone and missile attack on Israel",
        "2024-04-13",
        "IRN",
        "war,oil,MENA,iran",
        "First direct Iranian attack on Israel.",
    ),
    _conflict(
        "IRN_ISR_OCT_2024",
        "Iran's ballistic-missile attack on Israel",
        "2024-10-01",
        "IRN",
        "war,oil,MENA,iran",
        "Second direct Iranian attack on Israel.",
    ),
    _conflict(
        "IND_PAK_SINDOOR_2025",
        "Operation Sindoor",
        "2025-05-07",
        "PAK",
        "war,ASIA,nuclear",
        "Indian strikes in Pakistan after the Pahalgam attack.",
    ),
    _conflict(
        "ISR_IRN_JUN_2025",
        "Israel strikes Iran",
        "2025-06-13",
        "IRN",
        "war,oil,MENA,iran,nuclear",
        "Israeli strikes on Iranian nuclear and military sites.",
    ),
    _conflict(
        "US_IRN_JUN_2025",
        "US strikes Iranian nuclear sites",
        "2025-06-22",
        "IRN",
        "war,oil,MENA,iran,nuclear,us_involved",
        "US strikes on Fordow, Natanz and Isfahan.",
    ),
)


def sanctions_wave_events(
    counts: pd.DataFrame,
    threshold: int = WAVE_THRESHOLD,
    as_of: datetime.date | None = None,
) -> List[MarketEvent]:
    """One ``sanctions`` event per country and month with at least ``threshold`` new designations.

    ``counts`` is a month-start indexed frame with one column per ISO-3 code
    (as stored under ``SANCTIONS_NEW.<ISO3>``); a ``WLD`` column is ignored.
    """
    as_of = as_of or datetime.date.today()
    events: List[MarketEvent] = []
    for iso3 in counts.columns:
        if iso3 == "WLD":
            continue
        column = counts[iso3]
        months: List[pd.Timestamp] = list(pd.DatetimeIndex(column.index))
        for month, value in zip(months, column.tolist(), strict=True):
            if pd.isna(value) or value < threshold:
                continue
            day = month.date()
            events.append(
                MarketEvent(
                    event_id=f"SANCTIONS_{iso3}_{day:%Y-%m}",
                    event_type="sanctions",
                    name=f"OFAC designation wave: {int(value)} new {iso3} listings",
                    date=day,
                    end_date=(pd.Timestamp(day) + pd.offsets.MonthEnd(0)).date(),
                    country=iso3,
                    tags=f"sanctions,ofac,{iso3}",
                    outcome=str(int(value)),
                    description="Month with at least "
                    f"{threshold} new SDN designations attributed to {iso3} (dated to the month start).",
                    source="OFAC",
                    as_of=as_of,
                )
            )
    return sorted(events, key=lambda event: (event.date, event.event_id))


def sanctions_waves_from_db(db: BearishDbBase, threshold: int = WAVE_THRESHOLD) -> List[MarketEvent]:
    """Detect waves from the ``SANCTIONS_NEW.*`` observations already stored."""
    frame = db.read_macro_frame(MacroQuery(concepts=["SANCTIONS_NEW"]))
    if frame.empty:
        return []
    frame.columns = [str(column).split(".", 1)[1] for column in frame.columns]
    frame.index = pd.to_datetime(frame.index)
    return sanctions_wave_events(frame, threshold=threshold)
