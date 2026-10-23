"""IMF DataMapper (World Economic Outlook and related datasets).

URL: ``https://www.imf.org/external/datamapper/api/v1/{indicator}`` returns
``{"values": {indicator: {ISO3: {"1980": v, ...}}}}`` for every economy and
aggregate at once (the per-country path filter is ignored by the API and long
paths 404), so one request per indicator is made and filtered client-side.
Annual data including WEO forecast years; ``source_code`` is the indicator
code (``NGDP_RPCH``, ``PCPIPCH``, ...). Aggregates use DataMapper's own codes
(``WEOWORLD``, ``EURO``, ``EU``, ``MAE``, ...) mapped to catalog regions.
"""

import datetime
import logging
from collections import defaultdict
from typing import Dict, List, Optional

import pandas as pd

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import observations_from_series

logger = logging.getLogger(__name__)

IMF_DATAMAPPER_URL = "https://www.imf.org/external/datamapper/api/v1/{indicator}"

# Catalog region entity -> DataMapper aggregate code.
REGION_CODES: Dict[str, str] = {
    "WLD": "WEOWORLD",
    "EA20": "EURO",
    "EU27": "EU",
    "G7": "MAE",
    "EM": "OEMDC",
    "DM": "ADVEC",
}


def datamapper_code(entity: str) -> str:
    return REGION_CODES.get(entity, entity)


class ImfSource(AbstractMacroSource):
    __source__ = "IMF"

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        by_indicator: Dict[str, List[MacroSeries]] = defaultdict(list)
        for macro_series in series:
            by_indicator[macro_series.source_code].append(macro_series)

        observations: List[Observation] = []
        as_of = self.today()
        for indicator, members in by_indicator.items():
            payload = self._get(IMF_DATAMAPPER_URL.format(indicator=indicator)).json()
            values = payload.get("values", {}).get(indicator, {})
            for macro_series in members:
                yearly = values.get(datamapper_code(macro_series.entity))
                if not yearly:
                    logger.warning(f"IMF returned no data for {macro_series.series_id}")
                    continue
                frame = pd.Series(
                    list(yearly.values()),
                    index=pd.to_datetime([f"{year}-01-01" for year in yearly]),
                    dtype=float,
                )
                observations.extend(observations_from_series(macro_series, frame, as_of, start))
        return observations
