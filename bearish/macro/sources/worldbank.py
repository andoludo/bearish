"""World Bank Indicators API (World Development Indicators).

URL: ``https://api.worldbank.org/v2/country/{iso2;iso2;...}/indicator/{code}``
with ``format=json``; the response is ``[header, rows]`` where the header
carries ``pages`` for pagination and each row has ``countryiso3code``,
``date`` (year) and ``value``. Annual data; ``source_code`` is the WDI
indicator code (``NY.GDP.PCAP.CD``, ...). One paginated request per indicator
covers every requested country.
"""

import datetime
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

import pandas as pd

from bearish.macro.countries import country_from
from bearish.macro.models import MacroSeries, Observation
from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.transform import fetch_start, observations_from_series

logger = logging.getLogger(__name__)

WORLD_BANK_URL = "https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}"
PER_PAGE = 1000
# A successful response is ``[header, rows]``; errors come back as a one-element list.
PAYLOAD_PARTS = 2


def _iso2(entity: str) -> str:
    country = country_from(entity)
    return country.iso2 if country else entity


class WorldBankSource(AbstractMacroSource):
    __source__ = "WorldBank"

    def _read_observations(self, series: List[MacroSeries], start: Optional[datetime.date]) -> List[Observation]:
        by_indicator: Dict[str, List[MacroSeries]] = defaultdict(list)
        for macro_series in series:
            by_indicator[macro_series.source_code].append(macro_series)

        observations: List[Observation] = []
        as_of = self.today()
        for indicator, members in by_indicator.items():
            request_start = min(fetch_start(m, start) or datetime.date.min for m in members)
            rows = self._fetch_all_pages(indicator, [_iso2(m.entity) for m in members], request_start)
            frame = pd.DataFrame(rows)
            if frame.empty:
                logger.warning(f"World Bank returned no data for {indicator}")
                continue
            frame = frame.dropna(subset=["value"])
            frame["period"] = pd.to_datetime(frame["date"].astype(str) + "-01-01")
            for macro_series in members:
                subset = frame[frame["countryiso3code"] == macro_series.entity]
                if subset.empty:
                    logger.warning(f"World Bank returned no data for {macro_series.series_id}")
                    continue
                values = pd.Series(subset["value"].to_numpy(dtype=float), index=subset["period"])
                observations.extend(observations_from_series(macro_series, values, as_of, start))
        return observations

    def _fetch_all_pages(self, indicator: str, iso2_codes: List[str], start: datetime.date) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"format": "json", "per_page": PER_PAGE}
        if start != datetime.date.min:
            params["date"] = f"{start.year}:{self.today().year}"
        url = WORLD_BANK_URL.format(countries=";".join(iso2_codes), indicator=indicator)
        rows: List[Dict[str, Any]] = []
        page, pages = 1, 1
        while page <= pages:
            payload = self._get(url, params={**params, "page": page}).json()
            if not isinstance(payload, list) or len(payload) < PAYLOAD_PARTS or payload[1] is None:
                logger.warning(f"World Bank returned an unexpected payload for {indicator}: {str(payload)[:200]}")
                break
            header, page_rows = payload[0], payload[1]
            pages = int(header.get("pages", 1))
            rows.extend(page_rows)
            page += 1
        return rows
