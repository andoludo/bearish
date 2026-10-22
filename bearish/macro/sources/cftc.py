"""CFTC Commitments of Traders, "Legacy - Futures Only" report via the
Socrata open-data API (keyless). One request per futures market returns the
weekly history; three derived series are published per market.

Catalog ``source_code`` is ``<cftc_contract_market_code>|<field>`` where
field is one of ``net_spec`` (non-commercial long minus short),
``net_spec_pct_oi`` (the same as a percentage of open interest) or
``open_interest``.
"""

import datetime
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import observations_from_series

logger = logging.getLogger(__name__)

CFTC_LEGACY_FUTURES_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
FIELDS = ("net_spec", "net_spec_pct_oi", "open_interest")
_COLUMNS = (
    "report_date_as_yyyy_mm_dd",
    "noncomm_positions_long_all",
    "noncomm_positions_short_all",
    "open_interest_all",
)


def split_source_code(source_code: str) -> Tuple[str, str]:
    market_code, field = source_code.split("|", 1)
    if field not in FIELDS:
        raise ValueError(f"Unknown CFTC field '{field}' (expected one of {FIELDS})")
    return market_code, field


def derive_fields(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """Weekly frame indexed by report date with one column per derived field."""
    if not rows:
        return pd.DataFrame(columns=list(FIELDS))
    frame = pd.DataFrame(rows)
    for column in _COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame.index = pd.to_datetime(frame[_COLUMNS[0]]).dt.normalize()
    net = frame["noncomm_positions_long_all"] - frame["noncomm_positions_short_all"]
    open_interest = frame["open_interest_all"].replace(0, float("nan"))
    derived = pd.DataFrame(
        {"net_spec": net, "net_spec_pct_oi": net / open_interest * 100.0, "open_interest": frame["open_interest_all"]}
    )
    return derived[~derived.index.duplicated(keep="last")].sort_index()


class CftcSource(AbstractMacroSource):
    __source__ = "CFTC"
    page_size: int = 5000

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        by_market: Dict[str, List[MacroSeries]] = defaultdict(list)
        for macro_series in series:
            market_code, _ = split_source_code(macro_series.source_code)
            by_market[market_code].append(macro_series)

        as_of = self.today()
        observations: List[Observation] = []
        for market_code, members in by_market.items():
            frame = derive_fields(self._fetch_market(market_code, start))
            if frame.empty:
                logger.warning(f"CFTC returned no rows for market {market_code}")
                continue
            for macro_series in members:
                _, field = split_source_code(macro_series.source_code)
                observations.extend(observations_from_series(macro_series, frame[field], as_of, start))
        return observations

    def _fetch_market(self, market_code: str, start: Optional[datetime.date]) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {
            "cftc_contract_market_code": market_code,
            "$select": ",".join(_COLUMNS),
            "$order": "report_date_as_yyyy_mm_dd",
            "$limit": str(self.page_size),
        }
        if start is not None:
            params["$where"] = f"report_date_as_yyyy_mm_dd >= '{start.isoformat()}T00:00:00'"
        rows: List[Dict[str, Any]] = []
        offset = 0
        while True:
            page = self._get(CFTC_LEGACY_FUTURES_URL, params={**params, "$offset": str(offset)}).json()
            rows.extend(page)
            if len(page) < self.page_size:
                return rows
            offset += self.page_size
