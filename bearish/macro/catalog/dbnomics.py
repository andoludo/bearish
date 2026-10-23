"""DBnomics catalog: long-tail unemployment coverage for the non-OECD
priority countries.

Only series verified as still updating in October 2026 are listed. The IMF
IFS mirror on DBnomics stopped updating in 2025 and national offices other
than China's NBS carry no fresh labour or price data there, so monthly CPI
and quarterly GDP for HKG/TWN/SGP/ARG/RUS/SAU remain uncovered (the IMF WEO
annual outcomes in the IMF module are the fallback for those).
"""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.models import MacroSeries

# ILO modelled estimates: annual, harmonised across countries, published ahead
# of national releases; ``XA_n`` is ILO's source id per country.
_ILO_MODELLED = {
    "BRA": "XA_2002",
    "IND": "XA_1976",
    "ZAF": "XA_2192",
    "ARG": "XA_1868",
    "RUS": "XA_2110",
    "HKG": "XA_1964",
    "TWN": "XA_8368",
    "SGP": "XA_2120",
}

SERIES: List[MacroSeries] = [
    series(
        "UNEMP_RATE",
        "CHN",
        "DBnomics",
        "NBS/M_A0E01/A0E0101",
        "M",
        is_proxy=True,
        description="Urban surveyed unemployment rate (NBS); urban areas only",
    ),
    *(
        series(
            "UNEMP_RATE",
            iso3,
            "DBnomics",
            f"ILO/UNE_2EAP_SEX_AGE_RT/{iso3}.{source_id}.AGE_YTHADULT_YGE15.SEX_T.A",
            "A",
            is_proxy=True,
            description="Unemployment rate, ILO modelled estimate (annual)",
        )
        for iso3, source_id in _ILO_MODELLED.items()
    ),
]
