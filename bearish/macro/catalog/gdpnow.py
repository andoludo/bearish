"""Atlanta Fed GDPNow catalog: the running US current-quarter nowcast."""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.models import MacroSeries

SERIES: List[MacroSeries] = [
    series(
        "GDP_NOWCAST",
        "USA",
        "AtlantaFed",
        "GDP Nowcast",
        "D",
        description="GDPNow real GDP nowcast for the current quarter (% SAAR), by forecast date",
    ),
]
