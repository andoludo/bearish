"""CFTC catalog: weekly speculative positioning per futures market."""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.commodities import commodities_with
from bearish.macro.models import MacroSeries

_FIELDS = {
    "COT_NET_SPEC": "net_spec",
    "COT_NET_SPEC_PCT_OI": "net_spec_pct_oi",
    "COT_OPEN_INTEREST": "open_interest",
}

SERIES: List[MacroSeries] = [
    series(
        concept,
        commodity.code,
        "CFTC",
        f"{commodity.cftc_market_code}|{field}",
        "W",
        entity_type="commodity",
        description=f"{commodity.name}: {concept.replace('_', ' ').lower()} (CFTC legacy futures-only)",
    )
    for commodity in commodities_with("cftc_market_code")
    for concept, field in _FIELDS.items()
]
