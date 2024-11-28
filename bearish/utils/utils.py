from datetime import datetime
from math import isnan
from typing import Any, Optional

import pandas as pd


def to_float(value: Any) -> Optional[float]:  # noqa: ANN401
    if value == "None":
        return None
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return float(value)


def to_datetime(value: Any) -> datetime:  # noqa: ANN401
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d")
    elif isinstance(value, pd.Timestamp):
        if value.tz is not None:
            value = value.tz_convert(None)
        return value.to_pydatetime()
    elif isinstance(value, datetime):
        return value
    else:
        raise ValueError(f"Invalid datetime value: {value}")


def to_string(value: Any) -> Optional[str]:  # noqa: ANN401
    if value is None or (isinstance(value, float) and isnan(value)):
        return None
    if value == "None":
        return None
    return str(value)


def format_capitalize(value: Any) -> Optional[str]:  # noqa: ANN401
    country = to_string(value)
    if country is None:
        return None
    return country.capitalize()


def remove_duplicates(value: list[str]) -> list[str]:
    if not value:
        return []
    return list(set(value))
