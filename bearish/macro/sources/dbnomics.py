"""DBnomics (aggregator of ~90 statistical providers), keyless JSON API.

URL: ``https://api.db.nomics.world/v22/series?series_ids={id1},{id2}&observations=1``
where a series id is ``{provider}/{dataset}/{series_code}`` -- which is
exactly what the catalog stores as ``source_code``. Every returned document
carries parallel ``period`` / ``period_start_day`` / ``value`` lists. Series
are fetched in batches regardless of provider. DBnomics is the long-tail
fallback for countries the primary providers do not cover, which is why most
entries are marked ``is_proxy`` (ILO modelled estimates, urban-only surveys).
"""

import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import observations_from_series, parse_period
from bearish.utils.utils import batch

logger = logging.getLogger(__name__)

DBNOMICS_SERIES_URL = "https://api.db.nomics.world/v22/series"
MAX_IDS_PER_CALL = 50


def document_id(document: Dict[str, Any]) -> str:
    return f"{document.get('provider_code')}/{document.get('dataset_code')}/{document.get('series_code')}"


def series_from_document(document: Dict[str, Any]) -> pd.Series:
    """Date-indexed values from one DBnomics series document (``NA`` dropped)."""
    starts = document.get("period_start_day") or document.get("period") or []
    values = document.get("value", [])
    points: List[Tuple[datetime.date, float]] = []
    for start, value in zip(starts, values, strict=False):
        period = parse_period(start)
        if period is None or value in (None, "NA"):
            continue
        points.append((period, float(value)))
    if not points:
        return pd.Series(dtype="float64")
    dates, numbers = zip(*points, strict=True)
    return pd.Series(list(numbers), index=pd.to_datetime(list(dates)), dtype="float64")


class DbnomicsSource(AbstractMacroSource):
    __source__ = "DBnomics"

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        observations: List[Observation] = []
        as_of = self.today()
        for chunk in batch(series, MAX_IDS_PER_CALL):
            by_id = {m.source_code: m for m in chunk}
            payload = self._get(DBNOMICS_SERIES_URL, params={"series_ids": ",".join(by_id), "observations": 1}).json()
            seen = set()
            for document in payload.get("series", {}).get("docs", []):
                macro_series = by_id.get(document_id(document))
                if macro_series is None:
                    continue
                seen.add(macro_series.series_id)
                observations.extend(
                    observations_from_series(macro_series, series_from_document(document), as_of, start)
                )
            for macro_series in chunk:
                if macro_series.series_id not in seen:
                    logger.warning(f"DBnomics returned no data for {macro_series.series_id}")
        return observations
