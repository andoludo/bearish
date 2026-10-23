"""Economic Policy Uncertainty indices (policyuncertainty.com).

One workbook, ``All_Country_Data.xlsx``, holds the global index
(``GEPU_current`` / ``GEPU_ppp``) and one column per country, with ``Year``
and ``Month`` columns; footnote rows at the bottom have no numeric year.
Catalog ``source_code`` is the column name. The file is downloaded once per
call and every requested column is read from it.
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

EPU_URL = "https://www.policyuncertainty.com/media/All_Country_Data.xlsx"


def parse_epu_workbook(content: bytes) -> pd.DataFrame:
    """Return a month-start indexed frame with one numeric column per index."""
    frame = pd.read_excel(io.BytesIO(content))
    frame = frame[pd.to_numeric(frame["Year"], errors="coerce").notna()]
    frame = frame[pd.to_numeric(frame["Month"], errors="coerce").notna()]
    index = pd.to_datetime({"year": frame["Year"].astype(int), "month": frame["Month"].astype(int), "day": 1})
    values = frame.drop(columns=["Year", "Month"]).apply(pd.to_numeric, errors="coerce")
    values.index = pd.DatetimeIndex(index)
    return pd.DataFrame(values.sort_index())


class EpuSource(AbstractMacroSource):
    __source__ = "EPU"

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        frame = parse_epu_workbook(self._get(EPU_URL).content)
        observations: List[Observation] = []
        as_of = self.today()
        for macro_series in series:
            if macro_series.source_code not in frame.columns:
                logger.warning(f"EPU workbook has no column '{macro_series.source_code}'")
                continue
            observations.extend(observations_from_series(macro_series, frame[macro_series.source_code], as_of, start))
        return observations
