"""GDELT 1.0 daily event files: conflict intensity between and within countries.

Each day GDELT publishes ``https://data.gdeltproject.org/events/YYYYMMDD.export.CSV.zip``,
a tab-separated file (58 columns, no header) of every machine-coded event
first seen in the news that day. Only five columns are read: the actors'
country codes (CAMEO, ISO-3 compatible for the countries used here),
``QuadClass`` (1 verbal cooperation, 2 material cooperation, 3 verbal conflict,
4 material conflict), ``GoldsteinScale`` and ``AvgTone``. Observations are
dated by the file (the day the events were added), not by the event's own
``SQLDATE``, which can be weeks earlier for retrospective articles.

Catalog ``source_code`` is ``pair|<A>|<B>|<metric>`` for an undirected
country pair or ``country|<ISO3>|<metric>`` for every event involving one
country, with ``metric`` in :data:`METRICS`. A file is ~8 MB zipped; one
download serves every requested series for that day.
"""

import datetime
import io
import logging
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import observations_from_series

logger = logging.getLogger(__name__)

GDELT_DAILY_URL = "https://data.gdeltproject.org/events/{day}.export.CSV.zip"
# Each day is one ~8 MB download shared by every series; keep the default
# first run modest and pass an explicit start for a longer history.
DEFAULT_BACKFILL_DAYS = 120

# column positions in the 58-column GDELT 1.0 event export
ACTOR1_COUNTRY, ACTOR2_COUNTRY, QUAD_CLASS, GOLDSTEIN, AVG_TONE = 7, 17, 29, 30, 34
COLUMNS = {
    ACTOR1_COUNTRY: "actor1",
    ACTOR2_COUNTRY: "actor2",
    QUAD_CLASS: "quad",
    GOLDSTEIN: "goldstein",
    AVG_TONE: "tone",
}

MATERIAL_CONFLICT = 4
VERBAL_CONFLICT = 3

# concept -> metric key in source codes
METRICS: Dict[str, str] = {
    "GDELT_CONFLICT_EVENTS": "conflict_events",
    "GDELT_VERBAL_CONFLICT": "verbal_conflict",
    "GDELT_GOLDSTEIN": "goldstein",
    "GDELT_TONE": "tone",
}

# CAMEO actor-country codes that differ from ISO-3.
CAMEO_TO_ISO3: Dict[str, str] = {"ROM": "ROU"}

# Undirected pairs with a history of market-moving tension (Kosovo is not
# coded as a country by GDELT, so SRB-XKX is absent).
PAIRS: Tuple[Tuple[str, str], ...] = (
    ("CHN", "USA"),
    ("CHN", "TWN"),
    ("RUS", "UKR"),
    ("IRN", "ISR"),
    ("ISR", "PSE"),
    ("ISR", "LBN"),
    ("IND", "PAK"),
    ("KOR", "PRK"),
    ("PRK", "USA"),
    ("IRN", "USA"),
    ("SAU", "YEM"),
    ("CHN", "PHL"),
    ("CHN", "JPN"),
    ("ARM", "AZE"),
    ("USA", "VEN"),
)


def pair_entity(first: str, second: str) -> str:
    """Entity code for an undirected pair: the two ISO-3 codes sorted and joined."""
    return "_".join(sorted((first.upper(), second.upper())))


def parse_daily_export(content: bytes) -> pd.DataFrame:
    """Read the columns used here from one zipped daily export."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        name = archive.namelist()[0]
        frame = pd.read_csv(
            archive.open(name),
            sep="\t",
            header=None,
            usecols=list(COLUMNS),
            dtype=str,
            quoting=3,
            keep_default_na=False,
        )
    frame = frame.rename(columns=COLUMNS)
    for column in ("actor1", "actor2"):
        frame[column] = frame[column].str.strip().replace(CAMEO_TO_ISO3)
    frame["quad"] = pd.to_numeric(frame["quad"], errors="coerce")
    frame["goldstein"] = pd.to_numeric(frame["goldstein"], errors="coerce")
    frame["tone"] = pd.to_numeric(frame["tone"], errors="coerce")
    return frame


def _metrics(events: pd.DataFrame) -> Dict[str, float]:
    return {
        "conflict_events": float((events["quad"] == MATERIAL_CONFLICT).sum()),
        "verbal_conflict": float((events["quad"] == VERBAL_CONFLICT).sum()),
        "goldstein": float(events["goldstein"].mean()) if len(events) else float("nan"),
        "tone": float(events["tone"].mean()) if len(events) else float("nan"),
    }


def aggregate_day(
    frame: pd.DataFrame, pairs: List[Tuple[str, str]], countries: List[str]
) -> Dict[Tuple[str, ...], Dict[str, float]]:
    """Daily metrics keyed by ``("pair", A, B)`` (A < B) or ``("country", ISO3)``.

    Pairs are undirected: events with A acting on B and B acting on A both
    count. Country metrics cover every event with the country as either actor.
    """
    result: Dict[Tuple[str, ...], Dict[str, float]] = {}
    if pairs:
        low = frame[["actor1", "actor2"]].min(axis=1)
        high = frame[["actor1", "actor2"]].max(axis=1)
        for first, second in pairs:
            a, b = sorted((first, second))
            result[("pair", a, b)] = _metrics(frame[(low == a) & (high == b)])
    for country in countries:
        result[("country", country)] = _metrics(frame[(frame["actor1"] == country) | (frame["actor2"] == country)])
    return result


def split_source_code(source_code: str) -> Tuple[Tuple[str, ...], str]:
    parts = source_code.split("|")
    if parts[0] == "pair" and len(parts) == 4:  # noqa: PLR2004
        a, b = sorted((parts[1], parts[2]))
        return ("pair", a, b), parts[3]
    if parts[0] == "country" and len(parts) == 3:  # noqa: PLR2004
        return ("country", parts[1]), parts[2]
    raise ValueError(f"Invalid GDELT source code: {source_code}")


class GdeltSource(AbstractMacroSource):
    __source__ = "GDELT"
    pause: float = 0.5
    timeout: int = 120
    backfill_days: int = DEFAULT_BACKFILL_DAYS
    cache_dir: Optional[Path] = None

    def _download(self, day: datetime.date) -> Optional[bytes]:
        stamp = day.strftime("%Y%m%d")
        cached = self.cache_dir / f"{stamp}.export.CSV.zip" if self.cache_dir else None
        if cached is not None and cached.exists():
            return cached.read_bytes()
        try:
            content = self._get(GDELT_DAILY_URL.format(day=stamp)).content
        except requests.HTTPError as e:
            logger.warning(f"GDELT file for {stamp} unavailable: {e}")
            return None
        if cached is not None:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(content)
        return content

    def days(self, start: Optional[datetime.date], end: Optional[datetime.date] = None) -> List[datetime.date]:
        """Days to download: ``start`` (or the backfill window) up to yesterday."""
        end = end or self.today() - datetime.timedelta(days=1)
        first = start or end - datetime.timedelta(days=self.backfill_days - 1)
        return [first + datetime.timedelta(days=offset) for offset in range((end - first).days + 1)]

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        keys: Dict[str, Tuple[Tuple[str, ...], str]] = {s.source_code: split_source_code(s.source_code) for s in series}
        pairs = sorted({(key[1], key[2]) for key, _ in keys.values() if key[0] == "pair"})
        countries = sorted({key[1] for key, _ in keys.values() if key[0] == "country"})
        values: Dict[str, Dict[pd.Timestamp, float]] = defaultdict(dict)
        for day in self.days(start):
            content = self._download(day)
            if content is None:
                continue
            daily = aggregate_day(parse_daily_export(content), pairs, countries)
            for source_code, (key, metric) in keys.items():
                values[source_code][pd.Timestamp(day)] = daily[key][metric]
        as_of = self.today()
        observations: List[Observation] = []
        for macro_series in series:
            points = values.get(macro_series.source_code)
            if not points:
                continue
            observations.extend(observations_from_series(macro_series, pd.Series(points), as_of, start))
        return observations
