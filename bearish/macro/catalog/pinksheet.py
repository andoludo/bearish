"""World Bank Pink Sheet catalog: monthly average prices per commodity."""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.commodities import commodities_with
from bearish.macro.models import MacroSeries

SERIES: List[MacroSeries] = [
    series(
        "PRICE_M",
        commodity.code,
        "WorldBankPinkSheet",
        commodity.pinksheet_series or "",
        "M",
        entity_type="commodity",
        unit=commodity.unit,
        description=f"{commodity.name}, monthly average price (World Bank CMO)",
    )
    for commodity in commodities_with("pinksheet_series")
]
