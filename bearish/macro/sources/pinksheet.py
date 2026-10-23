"""World Bank Commodity Markets Outlook "Pink Sheet": monthly nominal USD
prices for ~70 commodities since 1960, one xlsx download per fetch.

The ``Monthly Prices`` sheet has the commodity names in row 5, the units in
row 6 and one row per month (``1960M01``) from row 7. Catalog ``source_code``
is the column header (``Crude oil, Brent``); headers are normalised by
stripping whitespace and footnote markers (``**``).
"""

import datetime
import io
import logging
import re
from typing import List, Optional

import pandas as pd

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import observations_from_series, parse_period

logger = logging.getLogger(__name__)

PINK_SHEET_URL = (
    "https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/"
    "CMO-Historical-Data-Monthly.xlsx"
)
SHEET_NAME = "Monthly Prices"
HEADER_ROW = 4  # zero-based: commodity names
_FOOTNOTE = re.compile(r"\s*\*+\s*$")


def normalise_header(header: object) -> str:
    return _FOOTNOTE.sub("", str(header)).strip()


def parse_pink_sheet(content: bytes) -> pd.DataFrame:
    """Return a frame indexed by month start with one column per commodity name."""
    frame = pd.read_excel(io.BytesIO(content), sheet_name=SHEET_NAME, header=HEADER_ROW, engine="openpyxl")
    frame = frame.rename(columns={frame.columns[0]: "period"})
    frame.columns = ["period", *[normalise_header(column) for column in frame.columns[1:]]]
    frame["period"] = frame["period"].map(parse_period)
    frame = frame.dropna(subset=["period"]).set_index("period")
    frame.index = pd.to_datetime(frame.index)
    numeric: pd.DataFrame = frame.apply(pd.to_numeric, errors="coerce")
    return numeric


class PinkSheetSource(AbstractMacroSource):
    __source__ = "WorldBankPinkSheet"
    url: str = PINK_SHEET_URL

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        frame = parse_pink_sheet(self._get(self.url).content)
        as_of = self.today()
        observations: List[Observation] = []
        for macro_series in series:
            if macro_series.source_code not in frame.columns:
                logger.warning(f"Pink Sheet has no column '{macro_series.source_code}' for {macro_series.series_id}")
                continue
            observations.extend(observations_from_series(macro_series, frame[macro_series.source_code], as_of, start))
        return observations
