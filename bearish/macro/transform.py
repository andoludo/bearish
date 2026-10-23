"""Period parsing and ingest-time transformations shared by macro sources."""

import datetime
import re
from typing import Callable, List, Optional, Pattern, Tuple

import pandas as pd

from bearish.macro.models import PERIODS_PER_YEAR, Frequency, MacroSeries, Observation, Transform


def _quarter_start(year: int, quarter: int) -> datetime.date:
    return datetime.date(year, 3 * (quarter - 1) + 1, 1)


def _semester_start(year: int, semester: int) -> datetime.date:
    return datetime.date(year, 6 * (semester - 1) + 1, 1)


def _week_start(year: int, week: int) -> datetime.date:
    return datetime.date.fromisocalendar(year, week, 1)


# Provider period labels, most specific first. Each builder takes the regex groups.
_PERIOD_PATTERNS: List[Tuple[Pattern[str], Callable[[int, int], datetime.date]]] = [
    (re.compile(r"^(\d{4})-?Q([1-4])$"), _quarter_start),
    (re.compile(r"^(\d{4})-?S([12])$"), _semester_start),
    (re.compile(r"^(\d{4})-?W(\d{2})$"), _week_start),
    (re.compile(r"^(\d{4})-?M?(\d{2})$"), lambda year, month: datetime.date(year, month, 1)),
    (re.compile(r"^(\d{4})()$"), lambda year, _: datetime.date(year, 1, 1)),
]


def parse_period(value: object) -> Optional[datetime.date]:
    """Turn a provider period label into the period's start date.

    Accepts ISO dates, ``YYYY``, ``YYYY-MM``, ``YYYYMM``, ``YYYY-Qn``, ``YYYYQn``,
    ``YYYY-Wnn`` and ``YYYY-Sn`` (semesters); returns None for anything else.
    """
    if isinstance(value, (datetime.datetime, pd.Timestamp)):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    for pattern, build in _PERIOD_PATTERNS:
        if match := pattern.match(text):
            first, second = match.groups()
            return build(int(first), int(second) if second else 0)
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        return None


def apply_transform(values: pd.Series, transform: Transform, frequency: Frequency) -> pd.Series:
    """Apply an ingest transform to a date-indexed, ascending numeric series."""
    values = values.sort_index()
    if transform == "none":
        return values
    if transform == "diff":
        return values.diff()
    periods = PERIODS_PER_YEAR[frequency]
    if transform == "yoy":
        return values.pct_change(periods=periods, fill_method=None) * 100.0
    if transform == "pct_change":
        return values.pct_change(fill_method=None) * 100.0
    raise ValueError(f"Unknown transform: {transform}")


def observations_from_series(
    series: MacroSeries,
    values: pd.Series,
    as_of: datetime.date,
    start: Optional[datetime.date] = None,
) -> List[Observation]:
    """Build observations from a date-indexed numeric series.

    The transform runs on the full history *before* the ``start`` cut so a
    y/y rate at ``start`` still has its base period available. Non-finite
    values are dropped.
    """
    if values.empty:
        return []
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    numeric.index = pd.to_datetime(numeric.index)
    numeric = numeric[~numeric.index.duplicated(keep="last")].dropna()
    if numeric.empty:
        return []
    transformed = apply_transform(numeric, series.transform, series.frequency).dropna()
    if start is not None:
        transformed = transformed[transformed.index >= pd.Timestamp(start)]
    return [
        Observation(series_id=series.series_id, date=pd.Timestamp(index).date(), value=float(value), as_of=as_of)
        for index, value in zip(transformed.index, transformed.to_numpy(), strict=True)
    ]


# How far before the requested start a provider must be asked for data so
# that the transform at ``start`` has its base period available.
_TRANSFORM_LOOKBACK = {
    "none": datetime.timedelta(0),
    "diff": datetime.timedelta(days=100),
    "pct_change": datetime.timedelta(days=100),
    "yoy": datetime.timedelta(days=400),
}


def fetch_start(series: MacroSeries, start: Optional[datetime.date]) -> Optional[datetime.date]:
    """The date to request from the provider for a given stored-data start."""
    if start is None:
        return None
    lookback = _TRANSFORM_LOOKBACK[series.transform]
    if series.frequency == "A" and series.transform != "none":
        lookback = datetime.timedelta(days=800)
    return start - lookback
