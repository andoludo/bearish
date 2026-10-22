"""OECD Data Explorer (SDMX REST, CSV output).

Catalog ``source_code`` is ``<dataflow>/<key>`` exactly as it appears in the
Data Explorer URL, with the series' own country code in the REF_AREA slot,
e.g. ``OECD.SDD.STES,DSD_STES@DF_CLI,/FRA.M.LI...AA...H``. Series that differ
only by country are merged into one request (``FRA+DEU+...``) because the
public API is rate limited per IP.
"""

import datetime
import io
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import pandas as pd

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import fetch_start, observations_from_series, parse_period

logger = logging.getLogger(__name__)

OECD_DATA_URL = "https://sdmx.oecd.org/public/rest/data/{flow}/{key}"
REF_AREA_PLACEHOLDER = "{ref_area}"


def split_source_code(source_code: str, entity: str) -> Tuple[str, str]:
    """Return ``(flow, key_template)`` where the entity slot is a placeholder."""
    flow, key = source_code.split("/", 1)
    dimensions = key.split(".")
    try:
        position = dimensions.index(entity)
    except ValueError as e:
        raise ValueError(f"OECD key '{key}' does not contain its entity '{entity}'") from e
    dimensions[position] = REF_AREA_PLACEHOLDER
    return flow, ".".join(dimensions)


def parse_sdmx_csv(text: str) -> pd.DataFrame:
    """Return a frame indexed by (REF_AREA, period start) with an OBS_VALUE column."""
    frame = pd.read_csv(io.StringIO(text), dtype=str)
    if frame.empty or "OBS_VALUE" not in frame.columns:
        return pd.DataFrame(columns=["OBS_VALUE"])
    frame["period"] = frame["TIME_PERIOD"].map(parse_period)
    frame = frame.dropna(subset=["period", "OBS_VALUE"])
    frame["OBS_VALUE"] = pd.to_numeric(frame["OBS_VALUE"], errors="coerce")
    return frame.set_index(["REF_AREA", "period"])[["OBS_VALUE"]].sort_index()


class OecdSource(AbstractMacroSource):
    __source__ = "OECD"
    pause: float = 2.0
    max_areas_per_call: int = 30

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        groups: Dict[Tuple[str, str], List[MacroSeries]] = defaultdict(list)
        for macro_series in series:
            groups[split_source_code(macro_series.source_code, macro_series.entity)].append(macro_series)

        observations: List[Observation] = []
        as_of = self.today()
        for (flow, key_template), members in groups.items():
            request_start = min(fetch_start(m, start) or datetime.date.min for m in members)
            for offset in range(0, len(members), self.max_areas_per_call):
                chunk = members[offset : offset + self.max_areas_per_call]
                frame = self._fetch(flow, key_template, [m.entity for m in chunk], request_start)
                for macro_series in chunk:
                    if macro_series.entity not in frame.index.get_level_values(0):
                        logger.warning(f"OECD returned no data for {macro_series.series_id}")
                        continue
                    values = frame.loc[macro_series.entity]["OBS_VALUE"]
                    observations.extend(observations_from_series(macro_series, values, as_of, start))
        return observations

    def _fetch(self, flow: str, key_template: str, areas: List[str], start: datetime.date) -> pd.DataFrame:
        key = key_template.replace(REF_AREA_PLACEHOLDER, "+".join(areas))
        params = {"format": "csvfilewithlabels"}
        if start != datetime.date.min:
            params["startPeriod"] = start.isoformat()
        response = self._get(OECD_DATA_URL.format(flow=flow, key=key), params=params)
        if response.text.startswith("NoRecordsFound"):
            return pd.DataFrame(columns=["OBS_VALUE"])
        return parse_sdmx_csv(response.text)
