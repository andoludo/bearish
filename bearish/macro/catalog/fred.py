"""FRED catalog: US market, financial-conditions and activity series.

Concepts shared with OECD for the US (CPI_YOY, UNEMP_RATE, GDP_YOY, IP_YOY,
CLI, confidence) are owned by the OECD module so every country is measured
the same way; FRED supplies what only the US publishes at this depth.
"""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.models import MacroSeries

_US = "USA"

SERIES: List[MacroSeries] = [
    # rates
    series("Y10", _US, "FRED", "DGS10", "D"),
    series("Y2", _US, "FRED", "DGS2", "D"),
    series("Y3M", _US, "FRED", "DTB3", "D"),
    series("CURVE_10_2", _US, "FRED", "T10Y2Y", "D"),
    series("CURVE_10_3M", _US, "FRED", "T10Y3M", "D"),
    series("REAL_Y10", _US, "FRED", "DFII10", "D"),
    series("MORTGAGE_30Y", _US, "FRED", "MORTGAGE30US", "W"),
    series("SOFR", _US, "FRED", "SOFR", "D"),
    # credit / financial conditions
    series("HY_SPREAD", _US, "FRED", "BAMLH0A0HYM2", "D"),
    series("IG_SPREAD", _US, "FRED", "BAMLC0A0CM", "D"),
    series("NFCI", _US, "FRED", "NFCI", "W"),
    series("VIX", _US, "FRED", "VIXCLS", "D"),
    series("RECESSION_PROB", _US, "FRED", "RECPROUSM156N", "M"),
    series("M2_YOY", _US, "FRED", "M2SL", "M", transform="yoy", seasonal_adj=True),
    # inflation
    series("CORE_CPI_YOY", _US, "FRED", "CPILFESL", "M", transform="yoy", seasonal_adj=True),
    series("PPI_YOY", _US, "FRED", "PPIACO", "M", transform="yoy"),
    series("INFL_EXP_5Y5Y", _US, "FRED", "T5YIFR", "D"),
    # labour
    series("PAYROLLS_CHG", _US, "FRED", "PAYEMS", "M", transform="diff", seasonal_adj=True),
    # external
    series("DXY", _US, "FRED", "DTWEXBGS", "D", description="Nominal broad US dollar index"),
]
