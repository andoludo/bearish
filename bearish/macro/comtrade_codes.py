"""UN M49 reporter codes used by UN Comtrade, keyed by ISO-3.

Comtrade departs from plain M49 for a few reporters (India reports as 699,
Taiwan as 490 "Other Asia, nes"); those are the codes that return data.
"""

from typing import Dict, Optional

M49_BY_ISO3: Dict[str, int] = {
    "USA": 842,
    "CAN": 124,
    "MEX": 484,
    "BRA": 76,
    "ARG": 32,
    "GBR": 826,
    "DEU": 276,
    "FRA": 251,
    "ITA": 380,
    "ESP": 724,
    "NLD": 528,
    "BEL": 56,
    "AUT": 40,
    "PRT": 620,
    "FIN": 246,
    "IRL": 372,
    "GRC": 300,
    "SWE": 752,
    "DNK": 208,
    "NOR": 578,
    "CHE": 756,
    "POL": 616,
    "RUS": 643,
    "TUR": 792,
    "ZAF": 710,
    "SAU": 682,
    "JPN": 392,
    "CHN": 156,
    "HKG": 344,
    "TWN": 490,
    "KOR": 410,
    "IND": 699,
    "IDN": 360,
    "SGP": 702,
    "AUS": 36,
    "NZL": 554,
}


def m49_for(iso3: str) -> Optional[int]:
    return M49_BY_ISO3.get(iso3.upper())
