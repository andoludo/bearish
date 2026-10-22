"""World Bank WDI catalog: structural annual indicators for every priority
country (Taiwan is not covered by the World Bank)."""

from typing import List

from bearish.macro.catalog._builder import for_countries
from bearish.macro.countries import priority_countries
from bearish.macro.models import MacroSeries

_countries = [c for c in priority_countries() if c.iso3 != "TWN"]

SERIES: List[MacroSeries] = [
    *for_countries("GDP_PER_CAPITA", _countries, "WorldBank", "NY.GDP.PCAP.CD", "A"),
    *for_countries("TRADE_GDP", _countries, "WorldBank", "NE.TRD.GNFS.ZS", "A"),
    *for_countries("RESERVES", _countries, "WorldBank", "FI.RES.TOTL.CD", "A"),
]
