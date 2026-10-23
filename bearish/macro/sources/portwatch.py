"""IMF PortWatch daily chokepoint transits (ArcGIS FeatureServer).

``Daily_Chokepoints_Data`` holds one row per chokepoint and day since
2019-01-01 with vessel counts by type (``n_total``, ``n_tanker``,
``n_container``, ...) and deadweight capacity (``capacity``). Catalog
``source_code`` is ``<portid>|<field>``, e.g. ``chokepoint6|n_tanker`` for
tankers through the Strait of Hormuz. One paginated query per call covers
every requested chokepoint and field.
"""

import datetime
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import observations_from_series

logger = logging.getLogger(__name__)

PORTWATCH_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query"
)
PAGE_SIZE = 1000  # the layer's maxRecordCount

# PortWatch ``portid`` -> bearish chokepoint entity code (names as of October 2026).
CHOKEPOINTS: Dict[str, str] = {
    "chokepoint1": "SUEZ",
    "chokepoint2": "PANAMA",
    "chokepoint3": "BOSPORUS",
    "chokepoint4": "BAB_EL_MANDEB",
    "chokepoint5": "MALACCA",
    "chokepoint6": "HORMUZ",
    "chokepoint7": "CAPE_OF_GOOD_HOPE",
    "chokepoint8": "GIBRALTAR",
    "chokepoint9": "DOVER",
    "chokepoint10": "ORESUND",
    "chokepoint11": "TAIWAN_STRAIT",
    "chokepoint12": "KOREA_STRAIT",
    "chokepoint13": "TSUGARU",
    "chokepoint14": "LUZON",
    "chokepoint15": "LOMBOK",
    "chokepoint16": "OMBAI",
    "chokepoint17": "BOHAI",
    "chokepoint18": "TORRES",
    "chokepoint19": "SUNDA",
    "chokepoint20": "MAKASSAR",
    "chokepoint21": "MAGELLAN",
    "chokepoint22": "YUCATAN",
    "chokepoint23": "WINDWARD",
    "chokepoint24": "MONA",
    "chokepoint25": "BALABAC",
    "chokepoint26": "BERING",
    "chokepoint27": "MINDORO",
    "chokepoint28": "KERCH",
}

# concept -> PortWatch field
FIELDS: Dict[str, str] = {
    "TRANSITS": "n_total",
    "TRANSITS_TANKER": "n_tanker",
    "TRANSITS_CONTAINER": "n_container",
    "CAPACITY_TONNES": "capacity",
}


def split_source_code(source_code: str) -> Tuple[str, str]:
    port_id, field = source_code.split("|", 1)
    return port_id, field


def build_where(port_ids: Set[str], start: Optional[datetime.date]) -> str:
    ports = ",".join(f"'{port_id}'" for port_id in sorted(port_ids))
    where = f"portid IN ({ports})"
    if start is not None:
        where += f" AND date >= DATE '{start.isoformat()}'"
    return where


def features_to_frame(features: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = [feature["attributes"] for feature in features]
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


class PortWatchSource(AbstractMacroSource):
    __source__ = "PortWatch"
    pause: float = 0.5
    max_pages: int = 500

    def _fetch(self, port_ids: Set[str], fields: Set[str], start: Optional[datetime.date]) -> pd.DataFrame:
        frames: List[pd.DataFrame] = []
        offset = 0
        for _ in range(self.max_pages):
            payload = self._get(
                PORTWATCH_URL,
                params={
                    "where": build_where(port_ids, start),
                    "outFields": ",".join(sorted({"date", "portid", *fields})),
                    "orderByFields": "date,portid",
                    "resultOffset": offset,
                    "resultRecordCount": PAGE_SIZE,
                    "returnGeometry": "false",
                    "f": "json",
                },
            ).json()
            if "error" in payload:
                raise ValueError(f"PortWatch query failed: {payload['error']}")
            features = payload.get("features", [])
            frames.append(features_to_frame(features))
            if not payload.get("exceededTransferLimit") or not features:
                break
            offset += len(features)
        frames = [frame for frame in frames if not frame.empty]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        wanted: Dict[str, List[Tuple[str, MacroSeries]]] = defaultdict(list)
        for macro_series in series:
            port_id, field = split_source_code(macro_series.source_code)
            wanted[port_id].append((field, macro_series))
        fields = {field for members in wanted.values() for field, _ in members}
        frame = self._fetch(set(wanted), fields, start)
        if frame.empty:
            return []
        as_of = self.today()
        observations: List[Observation] = []
        for port_id, members in wanted.items():
            port = frame[frame["portid"] == port_id].set_index("date").sort_index()
            if port.empty:
                logger.warning(f"PortWatch returned no rows for {port_id}")
                continue
            for field, macro_series in members:
                if field not in port.columns:
                    logger.warning(f"PortWatch has no field '{field}'")
                    continue
                observations.extend(observations_from_series(macro_series, port[field], as_of, start))
        return observations
