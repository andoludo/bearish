import functools
import logging
import time
from datetime import datetime, timedelta
from math import isnan
from typing import Any, Optional, List, Dict, Callable

import pandas as pd

from bearish.models.base import Ticker
from bearish.types import SeriesLength

logger = logging.getLogger(__name__)


def to_float(value: Any) -> Optional[float]:
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


def to_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d")
    elif isinstance(value, pd.Timestamp):
        if value.tz is not None:
            value = value.tz_convert(None)
        return value.to_pydatetime()  # type: ignore
    elif isinstance(value, datetime):
        return value
    else:
        raise ValueError(f"Invalid datetime value: {value}")


def to_string(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and isnan(value)):
        return None
    if value == "None":
        return None
    return str(value)


def format_capitalize(value: Any) -> Optional[str]:
    country = to_string(value)
    if country is None:
        return None
    return country.capitalize()


def remove_duplicates(value: list[Ticker]) -> list[Ticker]:
    if not value:
        return []
    tickers = [Ticker.model_validate(t) for t in value]
    return list({t.symbol: t for t in tickers}.values())


def remove_duplicates_string(value: list[str]) -> list[str]:
    if not value:
        return []
    return list(set(value))


def get_start_date(type: SeriesLength) -> Optional[str]:
    from_ = None
    if type != "max":
        past_date = datetime.today() - timedelta(days=int(type.replace("d", "")))
        from_ = str(past_date.strftime("%Y-%m-%d"))
    return from_


def to_dataframe(datas: List[Any]) -> pd.DataFrame:
    data = pd.DataFrame.from_records([p.model_dump() for p in datas])
    if data.empty:
        return data
    data = data.set_index("date", inplace=False)
    data = data.sort_index(inplace=False)

    data.index = pd.to_datetime(data.index, utc=True)
    data = data[~data.index.duplicated(keep="first")]
    return data


def batch(objects: List[Any], size: int) -> List[List[Any]]:
    return [objects[i : i + size] for i in range(0, len(objects), size)]


def safe_get(data: Dict[str, Any], attribute: str) -> Dict[str, Any]:
    if not isinstance(data, dict):
        logger.warning(
            f"Expected a dictionary, got {type(data)} instead with value {data}"
        )
        return {}
    value = data.get(attribute, {})
    return value if isinstance(value, dict) else {}


def observability(func: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            start = time.perf_counter()
            result = func(*args, **kwargs)
            time_elapsed = time.perf_counter() - start
            logger.debug("=========================================================")
            logger.debug(f"Function {func.__name__} took {time_elapsed:.2f} seconds")
            logger.debug("=========================================================")
            return result
        except Exception as e:
            logger.error(e, exc_info=True, stack_info=True)
            raise e

    return wrapper
