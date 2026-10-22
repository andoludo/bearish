"""IMF World Economic Outlook catalog: annual outcomes with forecasts, fiscal
and external balances, for every priority country plus world / euro-area /
EU / G7 / emerging / advanced aggregates."""

from typing import List

from bearish.macro.catalog._builder import for_countries, series
from bearish.macro.countries import priority_countries
from bearish.macro.models import MacroSeries

_INDICATORS = {
    "GDP_FCST": "NGDP_RPCH",
    "INFL_FCST": "PCPIPCH",
    "UNEMP_FCST": "LUR",
    "DEBT_GDP": "GGXWDG_NGDP",
    "DEFICIT_GDP": "GGXCNL_NGDP",
    "CA_GDP": "BCA_NGDPD",
}
_REGIONS = ("WLD", "EA20", "EU27", "G7", "EM", "DM")
# Unemployment aggregates exist only for advanced-economy groupings.
_UNEMPLOYMENT_REGIONS = ("EA20", "G7", "DM")

SERIES: List[MacroSeries] = []
for _concept, _code in _INDICATORS.items():
    SERIES.extend(for_countries(_concept, priority_countries(), "IMF", _code, "A"))
    _regions = _UNEMPLOYMENT_REGIONS if _concept == "UNEMP_FCST" else _REGIONS
    SERIES.extend(series(_concept, region, "IMF", _code, "A", entity_type="region") for region in _regions)
