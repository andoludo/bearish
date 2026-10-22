"""ECB catalog: euro-area aggregates the ECB publishes itself.

Entity ``EA20`` (euro area, changing composition). Prices for the euro area
come from Eurostat, the policy rate from BIS, so this module is limited to
money, the AAA yield curve, the exchange rate and unemployment.
"""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.models import MacroSeries

_EA = "EA20"

SERIES: List[MacroSeries] = [
    series(
        "M2_YOY",
        _EA,
        "ECB",
        "BSI/M.U2.Y.V.M30.X.I.U2.2300.Z01.A",
        "M",
        entity_type="region",
        seasonal_adj=True,
        is_proxy=True,
        description="Monetary aggregate M3, annual growth rate (proxy for broad money growth)",
    ),
    series(
        "Y10",
        _EA,
        "ECB",
        "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
        "D",
        entity_type="region",
        description="Euro area AAA government bond yield curve, 10-year spot rate",
    ),
    series(
        "Y2",
        _EA,
        "ECB",
        "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y",
        "D",
        entity_type="region",
        description="Euro area AAA government bond yield curve, 2-year spot rate",
    ),
    series(
        "FX_USD",
        _EA,
        "ECB",
        "EXR/D.USD.EUR.SP00.A",
        "D",
        entity_type="region",
        unit="USD per EUR",
        description="ECB reference rate, US dollars per euro (inverse of the usual per-USD quote)",
    ),
    series(
        "UNEMP_RATE",
        _EA,
        "ECB",
        "LFSI/M.I9.S.UNEHRT.TOTAL0.15_74.T",
        "M",
        entity_type="region",
        seasonal_adj=True,
        description="Euro area unemployment rate, 15-74, seasonally adjusted",
    ),
]
