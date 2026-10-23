"""Kenneth R. French Data Library: factor returns (market, size, value,
profitability, investment, momentum) for the US and regional portfolios.

Each file is a zipped CSV with a free-text preamble, a header line starting
with a comma, one block of periodic data ending at the first blank line, and
(for monthly files) a trailing annual block that is ignored. Catalog
``source_code`` is ``<zip file name>|<column>``.
"""

import datetime
import io
import logging
import zipfile
from collections import defaultdict
from typing import Dict, List, Optional

import pandas as pd

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import observations_from_series

logger = logging.getLogger(__name__)

KEN_FRENCH_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{zip_name}"
MISSING_VALUES = (-99.99, -999.0)


def parse_factor_csv(text: str) -> pd.DataFrame:
    """First data block of a Ken French CSV as a date-indexed frame (percent returns)."""
    lines = text.splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith(",")), None)
    if header_index is None:
        return pd.DataFrame()
    block: List[str] = []
    for line in lines[header_index + 1 :]:
        if not line.strip():
            break
        block.append(line)
    columns = [column.strip() for column in lines[header_index].split(",")]
    frame = pd.read_csv(io.StringIO("\n".join(block)), header=None, names=columns, dtype=str, skipinitialspace=True)
    labels = frame.iloc[:, 0].str.strip()
    index = pd.to_datetime(labels, format="%Y%m%d" if labels.str.len().iloc[0] == 8 else "%Y%m")  # noqa: PLR2004
    values = frame.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
    values.index = pd.DatetimeIndex(index)
    cleaned: pd.DataFrame = values.replace(list(MISSING_VALUES), float("nan"))
    return cleaned


def read_factor_zip(content: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        name = next(member for member in archive.namelist() if member.lower().endswith(".csv"))
        return parse_factor_csv(archive.read(name).decode("latin1"))


class KenFrenchSource(AbstractMacroSource):
    __source__ = "KenFrench"

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        by_zip: Dict[str, List[MacroSeries]] = defaultdict(list)
        for macro_series in series:
            zip_name, _ = macro_series.source_code.split("|", 1)
            by_zip[zip_name].append(macro_series)

        observations: List[Observation] = []
        as_of = self.today()
        for zip_name, members in by_zip.items():
            frame = read_factor_zip(self._get(KEN_FRENCH_URL.format(zip_name=zip_name)).content)
            for macro_series in members:
                column = macro_series.source_code.split("|", 1)[1]
                if column not in frame.columns:
                    logger.warning(f"Ken French file {zip_name} has no column {column}")
                    continue
                observations.extend(observations_from_series(macro_series, frame[column], as_of, start))
        return observations
