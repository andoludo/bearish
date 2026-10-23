"""OFAC catalog: monthly new SDN designations for the world and the countries
most exposed to US sanctions.

A country is included only when it is known to ``bearish.macro.countries``
(the catalog test requires it), so adding e.g. IRN there makes its series
appear here without further changes.
"""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.countries import COUNTRIES
from bearish.macro.models import MacroSeries

SANCTIONED = (
    "RUS", "IRN", "CHN", "PRK", "VEN", "BLR", "SYR", "CUB", "MMR", "ARE", "TUR", "LBN", "IRQ", "YEM",
    "MEX", "COL", "HKG", "IND", "UKR", "PAK", "AFG", "NIC",
)  # fmt: skip

_known = {country.iso3 for country in COUNTRIES}

SERIES: List[MacroSeries] = [
    series("SANCTIONS_NEW", "WLD", "OFAC", "WLD", "M", entity_type="global"),
    *[series("SANCTIONS_NEW", iso3, "OFAC", iso3, "M") for iso3 in SANCTIONED if iso3 in _known],
]
