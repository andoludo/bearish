"""Geopolitical Risk catalog: global index plus every priority country with
a ``GPRC_<ISO3>`` column in the export."""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.countries import priority_countries
from bearish.macro.models import MacroSeries

# Country columns present in data_gpr_export.xls (October 2026).
GPR_COUNTRIES = frozenset(
    {
        "ARG", "AUS", "BEL", "BRA", "CAN", "CHE", "CHL", "CHN", "COL", "DEU", "DNK", "EGY", "ESP", "FIN",
        "FRA", "GBR", "HKG", "HUN", "IDN", "IND", "ISR", "ITA", "JPN", "KOR", "MEX", "MYS", "NLD", "NOR",
        "PER", "PHL", "POL", "PRT", "RUS", "SAU", "SWE", "THA", "TUN", "TUR", "TWN", "UKR", "USA", "VEN",
        "VNM", "ZAF",
    }
)  # fmt: skip

SERIES: List[MacroSeries] = [
    series("GPR", "WLD", "GPR", "GPR", "M", entity_type="global", description="Global geopolitical risk index"),
    *[
        series("GPR", country.iso3, "GPR", f"GPRC_{country.iso3}", "M")
        for country in priority_countries()
        if country.iso3 in GPR_COUNTRIES
    ],
]
