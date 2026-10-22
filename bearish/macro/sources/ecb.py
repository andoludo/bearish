"""ECB Data Portal (SDMX REST, ``csvdata`` output).

Catalog ``source_code`` is ``<flow>/<key>`` exactly as in the portal URL,
e.g. ``YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y``. One request per series:
``https://data-api.ecb.europa.eu/service/data/{flow}/{key}?format=csvdata``.
The CSV carries ``TIME_PERIOD`` (daily ISO date or ``YYYY-MM``) and
``OBS_VALUE`` columns.
"""

import datetime
import io
import logging
from typing import List, Optional

import pandas as pd

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import fetch_start, observations_from_series, parse_period

logger = logging.getLogger(__name__)

ECB_DATA_URL = "https://data-api.ecb.europa.eu/service/data/{flow}/{key}"


def parse_ecb_csv(text: str) -> pd.Series:
    """Return a date-indexed value series from an ECB ``csvdata`` payload."""
    if not text.strip():
        return pd.Series(dtype=float)
    frame = pd.read_csv(io.StringIO(text), dtype=str, usecols=["TIME_PERIOD", "OBS_VALUE"])
    frame["period"] = frame["TIME_PERIOD"].map(parse_period)
    frame = frame.dropna(subset=["period"])
    values = pd.to_numeric(frame["OBS_VALUE"], errors="coerce")
    values.index = pd.to_datetime(frame["period"])
    return values.sort_index()


class EcbSource(AbstractMacroSource):
    __source__ = "ECB"

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        observations: List[Observation] = []
        as_of = self.today()
        for macro_series in series:
            flow, key = macro_series.source_code.split("/", 1)
            params = {"format": "csvdata"}
            request_start = fetch_start(macro_series, start)
            if request_start is not None:
                params["startPeriod"] = request_start.isoformat()
            response = self._get(ECB_DATA_URL.format(flow=flow, key=key), params=params)
            values = parse_ecb_csv(response.text)
            if values.empty:
                logger.warning(f"ECB returned no data for {macro_series.series_id}")
                continue
            observations.extend(observations_from_series(macro_series, values, as_of, start))
        return observations
