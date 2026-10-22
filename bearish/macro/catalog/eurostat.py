"""Eurostat catalog: EU sentiment, producer prices, quarterly GDP and the
EU-wide HICP / unemployment aggregates.

OECD owns the monthly unemployment / rates for its members, so Eurostat
contributes the concepts OECD does not harmonise (ESI, PPI, GDP q/q) for EU
priority countries plus the EU27 / EA20 aggregates. Headline and core CPI for
EU countries come from the HICP here rather than from OECD: OECD's national
CPI series stop when a country changes methodology (France ends at 2025-12),
while the HICP is continuous and comparable across the union.
Filters verified against the JSON-stat API in October 2026.
"""

from typing import List

from bearish.macro.catalog._builder import for_countries, series
from bearish.macro.countries import priority_countries
from bearish.macro.models import Frequency, MacroSeries

_ESI = "ei_bssi_m_r2?indic=BS-ESI-I&s_adj=SA&geo={code}"
_PPI = "sts_inppd_m?nace_r2=B-E36&unit=PCH_SM&s_adj=NSA&indic_bt=PRC_PRR_DOM&geo={code}"
_GDP_QOQ = "namq_10_gdp?unit=CLV_PCH_PRE&s_adj=SCA&na_item=B1GQ&geo={code}"
_HICP = "prc_hicp_manr?unit=RCH_A&coicop=CP00&geo={code}"
_HICP_CORE = "prc_hicp_manr?unit=RCH_A&coicop=TOT_X_NRG_FOOD&geo={code}"
_UNEMPLOYMENT = "une_rt_m?unit=PC_ACT&s_adj=SA&age=TOTAL&sex=T&geo={code}"

# Eurostat geo codes for the aggregates bearish stores as regions.
_AGGREGATES = {"EU27": "EU27_2020", "EA20": "EA20"}

_eu_countries = [c for c in priority_countries() if c.eu]


def _aggregate(concept: str, template: str, frequency: Frequency, seasonal_adj: bool = False) -> List[MacroSeries]:
    return [
        series(
            concept,
            entity,
            "Eurostat",
            template.format(code=geo),
            frequency,
            entity_type="region",
            seasonal_adj=seasonal_adj,
        )
        for entity, geo in _AGGREGATES.items()
    ]


SERIES: List[MacroSeries] = [
    *for_countries("ESI", _eu_countries, "Eurostat", _ESI, "M", seasonal_adj=True, code_attribute="eurostat_code"),
    *_aggregate("ESI", _ESI, "M", seasonal_adj=True),
    *for_countries("PPI_YOY", _eu_countries, "Eurostat", _PPI, "M", code_attribute="eurostat_code"),
    *_aggregate("PPI_YOY", _PPI, "M"),
    *for_countries(
        "GDP_QOQ", _eu_countries, "Eurostat", _GDP_QOQ, "Q", seasonal_adj=True, code_attribute="eurostat_code"
    ),
    *_aggregate("GDP_QOQ", _GDP_QOQ, "Q", seasonal_adj=True),
    *for_countries("CPI_YOY", _eu_countries, "Eurostat", _HICP, "M", code_attribute="eurostat_code"),
    *_aggregate("CPI_YOY", _HICP, "M"),
    *for_countries("CORE_CPI_YOY", _eu_countries, "Eurostat", _HICP_CORE, "M", code_attribute="eurostat_code"),
    *_aggregate("CORE_CPI_YOY", _HICP_CORE, "M"),
    # EA20 unemployment is owned by ECB (LFSI); Eurostat supplies the EU27 aggregate.
    series(
        "UNEMP_RATE",
        "EU27",
        "Eurostat",
        _UNEMPLOYMENT.format(code="EU27_2020"),
        "M",
        entity_type="region",
        seasonal_adj=True,
    ),
]
