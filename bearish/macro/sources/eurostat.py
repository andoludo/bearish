"""Eurostat dissemination API (JSON-stat 2.0).

Catalog ``source_code`` is ``<dataset>?<dimension>=<code>&...&geo=<code>``,
e.g. ``ei_bssi_m_r2?indic=BS-ESI-I&s_adj=SA&geo=FR``. Series that differ only
by ``geo`` are merged into one request (``geo=FR&geo=DE&...``) against
``https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}``
and split back using the JSON-stat dimension indexes.
"""

import datetime
import logging
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl

import pandas as pd

from bearish.macro.models import Frequency, MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import fetch_start, observations_from_series, parse_period

logger = logging.getLogger(__name__)

EUROSTAT_DATA_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
GEO_PLACEHOLDER = "{geo}"


def split_source_code(source_code: str) -> Tuple[str, Tuple[Tuple[str, str], ...], str]:
    """Return ``(dataset, fixed filters, geo)`` from a catalog source code."""
    dataset, _, query = source_code.partition("?")
    params = parse_qsl(query, keep_blank_values=False)
    geo = next((value for key, value in params if key == "geo"), None)
    if geo is None:
        raise ValueError(f"Eurostat source code '{source_code}' has no geo filter")
    fixed = tuple(sorted((key, value) for key, value in params if key != "geo"))
    return dataset, fixed, geo


def _category_codes(dimension: Dict[str, Any]) -> List[str]:
    index = dimension["category"]["index"]
    if isinstance(index, dict):
        return [code for code, _ in sorted(index.items(), key=lambda item: item[1])]
    return list(index)


def parse_jsonstat(payload: Dict[str, Any]) -> pd.DataFrame:
    """Flatten a JSON-stat dataset into a (geo, period) indexed ``value`` frame."""
    if "value" not in payload or not payload["value"]:
        return pd.DataFrame(columns=["value"])
    dims: List[str] = payload["id"]
    sizes: List[int] = payload["size"]
    codes = {dim: _category_codes(payload["dimension"][dim]) for dim in dims}
    strides = [math.prod(sizes[i + 1 :]) for i in range(len(sizes))]
    geo_pos, time_pos = dims.index("geo"), dims.index("time")
    rows = []
    for flat_key, value in payload["value"].items():
        if value is None:
            continue
        flat = int(flat_key)
        geo = codes["geo"][(flat // strides[geo_pos]) % sizes[geo_pos]]
        period = parse_period(codes["time"][(flat // strides[time_pos]) % sizes[time_pos]])
        if period is None:
            continue
        rows.append((geo, period, float(value)))
    frame = pd.DataFrame(rows, columns=["geo", "period", "value"])
    return frame.set_index(["geo", "period"]).sort_index()


def since_label(start: datetime.date, frequency: Frequency) -> str:
    if frequency == "Q":
        return f"{start.year}-Q{(start.month - 1) // 3 + 1}"
    if frequency == "A":
        return str(start.year)
    return start.strftime("%Y-%m")


class EurostatSource(AbstractMacroSource):
    __source__ = "Eurostat"
    max_geos_per_call: int = 30

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        groups: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], List[Tuple[str, MacroSeries]]] = defaultdict(list)
        for macro_series in series:
            dataset, fixed, geo = split_source_code(macro_series.source_code)
            groups[(dataset, fixed)].append((geo, macro_series))

        observations: List[Observation] = []
        as_of = self.today()
        for (dataset, fixed), members in groups.items():
            request_start = min(fetch_start(m, start) or datetime.date.min for _, m in members)
            for offset in range(0, len(members), self.max_geos_per_call):
                chunk = members[offset : offset + self.max_geos_per_call]
                frame = self._fetch(dataset, fixed, [geo for geo, _ in chunk], request_start, chunk[0][1].frequency)
                for geo, macro_series in chunk:
                    if geo not in frame.index.get_level_values(0):
                        logger.warning(f"Eurostat returned no data for {macro_series.series_id}")
                        continue
                    values = frame.loc[geo]["value"]
                    values.index = pd.to_datetime(values.index)
                    observations.extend(observations_from_series(macro_series, values, as_of, start))
        return observations

    def _fetch(
        self,
        dataset: str,
        fixed: Tuple[Tuple[str, str], ...],
        geos: List[str],
        start: datetime.date,
        frequency: Frequency,
    ) -> pd.DataFrame:
        params: List[Tuple[str, str]] = [("format", "JSON"), ("lang", "EN"), *fixed]
        params.extend(("geo", geo) for geo in geos)
        if start != datetime.date.min:
            params.append(("sinceTimePeriod", since_label(start, frequency)))
        response = self._get(EUROSTAT_DATA_URL.format(dataset=dataset), params=dict(_multi(params)))
        payload = response.json()
        if "error" in payload:
            logger.warning(f"Eurostat error for {dataset}: {payload['error']}")
            return pd.DataFrame(columns=["value"])
        return parse_jsonstat(payload)


def _multi(params: List[Tuple[str, str]]) -> List[Tuple[str, Any]]:
    """Collapse repeated keys into lists so ``requests`` encodes ``geo=FR&geo=DE``."""
    merged: Dict[str, Any] = {}
    for key, value in params:
        if key in merged:
            existing = merged[key] if isinstance(merged[key], list) else [merged[key]]
            merged[key] = [*existing, value]
        else:
            merged[key] = value
    return list(merged.items())
