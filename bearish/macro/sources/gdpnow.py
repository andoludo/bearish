"""Atlanta Fed GDPNow (real-time US GDP nowcast).

The model workbook ``GDPTrackingModelDataAndForecasts.xlsx`` (about 10 MB)
holds the full history of nowcasts by forecast date in the
``TrackingArchives`` sheet (columns ``Forecast Date``, ``Quarter being
forecasted``, ``GDP Nowcast``) for completed quarters, and the current
quarter in ``TrackingHistory`` (forecast dates across the first row, one
labelled row per component, ``GDP Nowcast`` among them). Catalog
``source_code`` is the column label to read (``GDP Nowcast``). Observations
are keyed by forecast date; the quarter being forecast is not stored.
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

GDPNOW_URL = (
    "https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/research-and-data/data/gdpnow/"
    "GDPTrackingModelDataAndForecasts.xlsx"
)
ARCHIVE_SHEET = "TrackingArchives"
CURRENT_SHEET = "TrackingHistory"
FORECAST_DATE = "Forecast Date"


def _archive(workbook: pd.ExcelFile, label: str) -> "pd.Series[float]":
    frame = pd.read_excel(workbook, sheet_name=ARCHIVE_SHEET)
    if FORECAST_DATE not in frame.columns or label not in frame.columns:
        return pd.Series(dtype=float)
    values = pd.to_numeric(frame[label], errors="coerce")
    values.index = pd.DatetimeIndex(pd.to_datetime(frame[FORECAST_DATE], errors="coerce"))
    return pd.Series(values[values.index.notna()], dtype=float)


def _current_quarter(workbook: pd.ExcelFile, label: str) -> "pd.Series[float]":
    frame = pd.read_excel(workbook, sheet_name=CURRENT_SHEET, header=None)
    labels = frame.iloc[:, 1].astype(str).str.strip()
    matches = frame.index[labels == label]
    if matches.empty:
        return pd.Series(dtype=float)
    dates = pd.to_datetime(frame.iloc[0, 2:], errors="coerce")
    values = pd.to_numeric(frame.loc[matches[0]].iloc[2:], errors="coerce")
    values.index = pd.DatetimeIndex(dates)
    return pd.Series(values[values.index.notna()], dtype=float)


def parse_gdpnow_workbook(content: bytes, label: str) -> "pd.Series[float]":
    """Nowcast history (archive + current quarter) indexed by forecast date."""
    with pd.ExcelFile(io.BytesIO(content)) as workbook:
        sheets = set(workbook.sheet_names)
        parts = []
        if ARCHIVE_SHEET in sheets:
            parts.append(_archive(workbook, label))
        if CURRENT_SHEET in sheets:
            parts.append(_current_quarter(workbook, label))
    if not parts:
        return pd.Series(dtype=float)
    combined = pd.concat(parts).astype(float)
    return pd.Series(combined[~combined.index.duplicated(keep="last")].sort_index(), dtype=float)


class GdpNowSource(AbstractMacroSource):
    __source__ = "AtlantaFed"
    timeout: int = 300

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        content = self._get(GDPNOW_URL).content
        observations: List[Observation] = []
        as_of = self.today()
        for macro_series in series:
            values = parse_gdpnow_workbook(content, macro_series.source_code)
            if values.empty:
                logger.warning(f"GDPNow workbook has no '{macro_series.source_code}' data")
                continue
            observations.extend(observations_from_series(macro_series, values, as_of, start))
        return observations
