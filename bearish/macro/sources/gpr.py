"""Geopolitical Risk index (Caldara & Iacoviello, matteoiacoviello.com).

``data_gpr_export.xls`` has a ``month`` column, the global ``GPR`` index and
one ``GPRC_<ISO3>`` column per country. Catalog ``source_code`` is the
column name. The workbook is a legacy ``.xls`` (read with xlrd); the parser
lets pandas pick the engine from the file content so an ``.xlsx`` copy
works too.
"""

import datetime
import io
import logging
from typing import List, Optional

import pandas as pd

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import observations_from_series

logger = logging.getLogger(__name__)

GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"


def parse_gpr_workbook(content: bytes) -> pd.DataFrame:
    """Return a month-start indexed frame with one numeric column per index."""
    frame = pd.read_excel(io.BytesIO(content))
    frame = frame.dropna(subset=["month"])
    index = pd.to_datetime(frame["month"], errors="coerce")
    values = frame.drop(columns=["month"]).apply(pd.to_numeric, errors="coerce")
    values.index = pd.DatetimeIndex(index)
    return pd.DataFrame(values[values.index.notna()].sort_index())


class GprSource(AbstractMacroSource):
    __source__ = "GPR"

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        frame = parse_gpr_workbook(self._get(GPR_URL).content)
        observations: List[Observation] = []
        as_of = self.today()
        for macro_series in series:
            if macro_series.source_code not in frame.columns:
                logger.warning(f"GPR workbook has no column '{macro_series.source_code}'")
                continue
            observations.extend(observations_from_series(macro_series, frame[macro_series.source_code], as_of, start))
        return observations
