"""FRED (Federal Reserve Bank of St. Louis).

Two access paths:

* With an API key (``FRED_API_KEY`` or ``{"FRED": "..."}`` in the key file)
  the official JSON API is used, one call per series.
* Without a key the public ``fredgraph.csv`` export is used, which accepts
  several series ids per call. It is the same data without vintage metadata.
"""

import datetime
import io
import logging
import zipfile
from typing import Any, Dict, List, Optional

import pandas as pd

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import fetch_start, observations_from_series
from bearish.utils.utils import batch

logger = logging.getLogger(__name__)

FRED_GRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"


def graph_params(series_ids: List[str], start: Optional[datetime.date] = None) -> Dict[str, str]:
    params = {"id": ",".join(series_ids)}
    if start is not None:
        params["cosd"] = start.isoformat()
    return params


def _read_one_csv(content: bytes) -> pd.DataFrame:
    frame = pd.read_csv(io.BytesIO(content), na_values=["."])
    date_column = next(column for column in frame.columns if column.lower() in {"observation_date", "date"})
    return frame.set_index(pd.to_datetime(frame[date_column])).drop(columns=[date_column])


def parse_graph_csv(content: bytes) -> pd.DataFrame:
    """Parse a fredgraph export.

    When the requested ids mix frequencies FRED answers with a zip holding
    one CSV per frequency (``daily.csv``, ``monthly.csv``, ...); the frames
    are joined on date so every id ends up as one column.
    """
    if content[:2] != b"PK":
        return _read_one_csv(content)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        frames = [_read_one_csv(archive.read(name)) for name in archive.namelist() if name.endswith(".csv")]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, axis=1, sort=True)


class FredSource(AbstractMacroSource):
    __source__ = "FRED"
    batch_size: int = 10

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        if self.__api_key__:
            return self._read_api(series, start)
        return self._read_graph(series, start)

    def _read_graph(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        observations: List[Observation] = []
        as_of = self.today()
        request_start = min((fetch_start(s, start) or datetime.date.min for s in series), default=None)
        for chunk in batch(series, self.batch_size):
            ids = [s.source_code for s in chunk]
            response = self._get(
                FRED_GRAPH_URL,
                params=graph_params(ids, None if request_start in (None, datetime.date.min) else request_start),
            )
            frame = parse_graph_csv(response.content)
            for macro_series in chunk:
                if macro_series.source_code not in frame.columns:
                    logger.warning(f"FRED returned no column for {macro_series.source_code}")
                    continue
                observations.extend(
                    observations_from_series(macro_series, frame[macro_series.source_code], as_of, start)
                )
        return observations

    def _read_api(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        observations: List[Observation] = []
        as_of = self.today()
        for macro_series in series:
            params: Dict[str, Any] = {
                "series_id": macro_series.source_code,
                "api_key": self.__api_key__,
                "file_type": "json",
            }
            request_start = fetch_start(macro_series, start)
            if request_start is not None:
                params["observation_start"] = request_start.isoformat()
            payload = self._get(FRED_API_URL, params=params).json()
            rows = payload.get("observations", [])
            if not rows:
                continue
            values = pd.Series(
                [row["value"] for row in rows],
                index=pd.to_datetime([row["date"] for row in rows]),
            )
            observations.extend(observations_from_series(macro_series, values, as_of, start))
        return observations
