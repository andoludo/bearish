"""UN Comtrade (public preview endpoint, keyless): which commodities a
country's exports and imports depend on.

For each country and flow one request fetches the total trade value plus the
value of every HS-4 code referenced by the commodity reference list; the
share of each commodity is its value over the total. The preview endpoint is
throttled aggressively, hence the long default pause and the 429 retry.
"""

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from bearish.macro.commodities import COMMODITIES, Commodity, CountryCommodityExposure
from bearish.macro.comtrade_codes import m49_for
from bearish.macro.countries import Country
from bearish.macro.sources.base import USER_AGENT

logger = logging.getLogger(__name__)

COMTRADE_PREVIEW_URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
FLOWS = {"X": "export", "M": "import"}
TOTAL = "TOTAL"
HTTP_TOO_MANY_REQUESTS = 429


class ComtradeThrottledError(Exception):
    """Raised on HTTP 429 so tenacity can back off and retry."""


def hs_codes(commodities: List[Commodity]) -> List[str]:
    return sorted({code for commodity in commodities for code in commodity.hs_codes})


def comtrade_params(reporter: int, year: int, flow: str, commodities: List[Commodity]) -> Dict[str, str]:
    return {
        "reporterCode": str(reporter),
        "period": str(year),
        "partnerCode": "0",
        "cmdCode": ",".join([TOTAL, *hs_codes(commodities)]),
        "flowCode": flow,
    }


def exposures_from_payload(
    payload: Dict[str, Any],
    country: Country,
    year: int,
    flow: str,
    commodities: List[Commodity],
) -> List[CountryCommodityExposure]:
    """Turn one Comtrade response into exposure rows for every commodity with a value."""
    value_by_code: Dict[str, float] = defaultdict(float)
    for row in payload.get("data", []):
        value = row.get("primaryValue")
        if value is None:
            continue
        value_by_code[str(row["cmdCode"])] += float(value)
    total = value_by_code.get(TOTAL, 0.0)
    if total <= 0:
        logger.warning(f"Comtrade: no total {FLOWS[flow]} value for {country.iso3} {year}")
        return []
    exposures = []
    for commodity in commodities:
        value = sum(value_by_code.get(code, 0.0) for code in commodity.hs_codes)
        if value <= 0:
            continue
        exposures.append(
            CountryCommodityExposure(
                country=country.iso3,
                commodity=commodity.code,
                direction=FLOWS[flow],
                year=year,
                value_usd=value,
                share=value / total,
            )
        )
    return exposures


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=10, min=10, max=120),
    retry=retry_if_exception_type((ComtradeThrottledError, requests.ConnectionError, requests.Timeout)),
)
def _get(params: Dict[str, str], timeout: int) -> Dict[str, Any]:
    response = requests.get(COMTRADE_PREVIEW_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    if response.status_code == HTTP_TOO_MANY_REQUESTS:
        raise ComtradeThrottledError(f"Comtrade throttled request {params}")
    response.raise_for_status()
    payload: Dict[str, Any] = response.json()
    return payload


def fetch_country_exposures(
    countries: List[Country],
    year: int,
    pause: float = 6.0,
    commodities: Optional[List[Commodity]] = None,
    timeout: int = 60,
) -> List[CountryCommodityExposure]:
    """Export and import exposure of each country to every commodity with HS codes.

    Countries without a known Comtrade reporter code are skipped; a failed
    request is logged and skipped so one reporter cannot abort the run.
    """
    commodities = [c for c in (commodities or list(COMMODITIES)) if c.hs_codes]
    exposures: List[CountryCommodityExposure] = []
    first = True
    for country in countries:
        reporter = m49_for(country.iso3)
        if reporter is None:
            logger.debug(f"No Comtrade reporter code for {country.iso3}; skipping")
            continue
        for flow in FLOWS:
            if not first:
                time.sleep(pause)
            first = False
            try:
                payload = _get(comtrade_params(reporter, year, flow, commodities), timeout)
            except Exception as e:  # keep going: one reporter must not stop the run
                logger.error(f"Comtrade {country.iso3} {flow} {year}: {e}")
                continue
            exposures.extend(exposures_from_payload(payload, country, year, flow, commodities))
    return exposures
