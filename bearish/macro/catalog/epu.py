"""Economic Policy Uncertainty catalog: global index plus every priority
country that has a column in ``All_Country_Data.xlsx``."""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.countries import country_from
from bearish.macro.models import MacroSeries

# Column headers as they appear in the workbook (October 2026).
EPU_COUNTRY_COLUMNS = (
    "Australia",
    "Brazil",
    "Canada",
    "Chile",
    "China",
    "France",
    "Germany",
    "Greece",
    "India",
    "Ireland",
    "Italy",
    "Japan",
    "Korea",
    "Mexico",
    "Pakistan",
    "Russia",
    "Spain",
    "Singapore",
    "UK",
    "US",
)

SERIES: List[MacroSeries] = [
    series(
        "EPU",
        "WLD",
        "EPU",
        "GEPU_current",
        "M",
        entity_type="global",
        description="Global economic policy uncertainty index, current-price GDP weights",
    ),
    *[
        series("EPU", country.iso3, "EPU", column, "M")
        for column in EPU_COUNTRY_COLUMNS
        if (country := country_from(column)) is not None
    ],
]
