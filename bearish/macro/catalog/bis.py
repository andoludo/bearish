"""BIS catalog: policy rates, credit, property prices and effective exchange
rates. Coverage per dataflow was verified against the Data Portal in
October 2026; countries absent from a dataflow are left out."""

from typing import List

from bearish.macro.catalog._builder import for_countries, series
from bearish.macro.countries import priority_countries
from bearish.macro.models import MacroSeries

_POLICY = "WS_CBPOL/1.0/M.{code}"
_CREDIT_GAP = "WS_CREDIT_GAP/1.0/Q.{code}.P.A.C"
_CREDIT_GDP = "WS_TC/2.0/Q.{code}.P.A.M.770.A"
_HOUSE_PRICES = "WS_SPP/1.0/Q.{code}.R.771"
_REER = "WS_EER/1.0/M.R.B.{code}"

# BIS publishes policy rates for the central banks of these economies; the
# euro-area members share the ECB rate, which is stored under EA20.
_POLICY_RATE = {
    "USA",
    "CAN",
    "MEX",
    "BRA",
    "GBR",
    "SWE",
    "DNK",
    "NOR",
    "CHE",
    "RUS",
    "ZAF",
    "JPN",
    "CHN",
    "HKG",
    "KOR",
    "IND",
    "AUS",
    "NZL",
}
_CREDIT = {
    "USA",
    "CAN",
    "MEX",
    "BRA",
    "ARG",
    "GBR",
    "DEU",
    "FRA",
    "ITA",
    "ESP",
    "NLD",
    "BEL",
    "AUT",
    "PRT",
    "FIN",
    "SWE",
    "DNK",
    "NOR",
    "CHE",
    "RUS",
    "ZAF",
    "JPN",
    "CHN",
    "HKG",
    "KOR",
    "IND",
    "SGP",
    "AUS",
    "NZL",
}
_HOUSE = _CREDIT - {"ARG"}
_REER_COUNTRIES = _CREDIT | {"TWN"}


def _subset(codes: set) -> list:  # type: ignore[type-arg]
    return [c for c in priority_countries() if c.iso3 in codes]


SERIES: List[MacroSeries] = [
    *for_countries("POLICY_RATE", _subset(_POLICY_RATE), "BIS", _POLICY, "M", code_attribute="iso2"),
    series("POLICY_RATE", "EA20", "BIS", "WS_CBPOL/1.0/M.XM", "M", entity_type="region"),
    *for_countries("CREDIT_GDP_GAP", _subset(_CREDIT), "BIS", _CREDIT_GAP, "Q", code_attribute="iso2"),
    series("CREDIT_GDP_GAP", "EA20", "BIS", "WS_CREDIT_GAP/1.0/Q.XM.P.A.C", "Q", entity_type="region"),
    *for_countries("CREDIT_GDP", _subset(_CREDIT), "BIS", _CREDIT_GDP, "Q", code_attribute="iso2"),
    series("CREDIT_GDP", "EA20", "BIS", "WS_TC/2.0/Q.XM.P.A.M.770.A", "Q", entity_type="region"),
    *for_countries("HOUSE_PRICE_YOY", _subset(_HOUSE), "BIS", _HOUSE_PRICES, "Q", code_attribute="iso2"),
    series("HOUSE_PRICE_YOY", "EA20", "BIS", "WS_SPP/1.0/Q.XM.R.771", "Q", entity_type="region"),
    *for_countries("REER", _subset(_REER_COUNTRIES), "BIS", _REER, "M", code_attribute="iso2"),
    series("REER", "EA20", "BIS", "WS_EER/1.0/M.R.B.XM", "M", entity_type="region"),
]
