"""SIPRI catalog: annual military expenditure (constant US$ m.) and its share
of GDP for priority countries, conflict-relevant countries and the world.

Hong Kong is not reported separately (it is part of China). Countries unknown
to ``bearish.macro.countries`` are skipped, so extending that list extends
this catalog.
"""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.countries import COUNTRIES, priority_countries
from bearish.macro.models import MacroSeries

_CONFLICT_RELEVANT = ("ISR", "UKR", "SAU", "TUR", "PAK", "POL", "IDN", "IRN", "PRK", "ARE", "EGY", "PHL")
_known = {country.iso3 for country in COUNTRIES}
_countries = [c.iso3 for c in priority_countries() if c.iso3 != "HKG"] + [
    iso3 for iso3 in _CONFLICT_RELEVANT if iso3 in _known
]

SERIES: List[MacroSeries] = [
    series("MILEX_USD", "WLD", "SIPRI", "constant|WLD", "A", entity_type="global"),
    *[series("MILEX_USD", iso3, "SIPRI", f"constant|{iso3}", "A") for iso3 in _countries],
    *[series("MILEX_GDP", iso3, "SIPRI", f"share_gdp|{iso3}", "A") for iso3 in _countries],
]
