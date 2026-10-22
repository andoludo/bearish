"""BIS Data Portal (SDMX 2.1 REST, CSV output).

URL: ``https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/{version}/{key}``
with ``format=csv``. Catalog ``source_code`` is ``{flow}/{version}/{key}``
with the series' own BIS area code in the key, e.g.
``WS_CBPOL/1.0/M.US`` or ``WS_TC/2.0/Q.FR.P.A.M.770.A``. BIS uses ISO-2
country codes and ``XM`` for the euro area. Series that differ only by area
are merged into one request (``M.US+FR+...``) and split back on the area
column (``REF_AREA`` or ``BORROWERS_CTY`` depending on the dataflow).
"""

import datetime
import io
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import pandas as pd

from bearish.macro.countries import country_from
from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import fetch_start, observations_from_series, parse_period

logger = logging.getLogger(__name__)

BIS_DATA_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/{version}/{key}"
AREA_PLACEHOLDER = "{area}"
AREA_COLUMNS = ("REF_AREA", "BORROWERS_CTY")
EURO_AREA = "XM"


def bis_area(entity: str) -> str:
    """BIS area code for a catalog entity (ISO-2, ``XM`` for the euro area)."""
    if entity == "EA20":
        return EURO_AREA
    country = country_from(entity)
    return country.iso2 if country else entity


def split_source_code(source_code: str, area: str) -> Tuple[str, str, str]:
    """Return ``(flow, version, key_template)`` with the area slot as a placeholder."""
    flow, version, key = source_code.split("/", 2)
    dimensions = key.split(".")
    try:
        position = dimensions.index(area)
    except ValueError as e:
        raise ValueError(f"BIS key '{key}' does not contain its area '{area}'") from e
    dimensions[position] = AREA_PLACEHOLDER
    return flow, version, ".".join(dimensions)


def parse_bis_csv(text: str) -> pd.DataFrame:
    """Return a frame indexed by (area, period start) with an OBS_VALUE column."""
    frame = pd.read_csv(io.StringIO(text), dtype=str)
    if frame.empty or "OBS_VALUE" not in frame.columns:
        return pd.DataFrame(columns=["OBS_VALUE"])
    area_column = next((column for column in AREA_COLUMNS if column in frame.columns), None)
    if area_column is None:
        raise ValueError(f"BIS CSV has no area column among {AREA_COLUMNS}")
    frame["period"] = frame["TIME_PERIOD"].map(parse_period)
    frame = frame.dropna(subset=["period", "OBS_VALUE"])
    frame["OBS_VALUE"] = pd.to_numeric(frame["OBS_VALUE"], errors="coerce")
    frame = frame.rename(columns={area_column: "area"})
    return frame.set_index(["area", "period"])[["OBS_VALUE"]].sort_index()


class BisSource(AbstractMacroSource):
    __source__ = "BIS"
    pause: float = 2.0

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        groups: Dict[Tuple[str, str, str], List[MacroSeries]] = defaultdict(list)
        for macro_series in series:
            groups[split_source_code(macro_series.source_code, bis_area(macro_series.entity))].append(macro_series)

        observations: List[Observation] = []
        as_of = self.today()
        for (flow, version, key_template), members in groups.items():
            request_start = min(fetch_start(m, start) or datetime.date.min for m in members)
            areas = [bis_area(m.entity) for m in members]
            frame = self._fetch(flow, version, key_template, areas, request_start)
            known_areas = set(frame.index.get_level_values(0)) if not frame.empty else set()
            for macro_series, area in zip(members, areas, strict=True):
                if area not in known_areas:
                    logger.warning(f"BIS returned no data for {macro_series.series_id}")
                    continue
                values = frame.loc[area]["OBS_VALUE"]
                observations.extend(observations_from_series(macro_series, values, as_of, start))
        return observations

    def _fetch(
        self, flow: str, version: str, key_template: str, areas: List[str], start: datetime.date
    ) -> pd.DataFrame:
        key = key_template.replace(AREA_PLACEHOLDER, "+".join(dict.fromkeys(areas)))
        params = {"format": "csv"}
        if start != datetime.date.min:
            params["startPeriod"] = start.isoformat()
        response = self._get(BIS_DATA_URL.format(flow=flow, version=version, key=key), params=params)
        if not response.text.strip():
            return pd.DataFrame(columns=["OBS_VALUE"])
        return parse_bis_csv(response.text)
