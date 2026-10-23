"""IMF PortWatch catalog: daily vessel transits and capacity for every chokepoint."""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.models import MacroSeries
from bearish.macro.sources.portwatch import CHOKEPOINTS, FIELDS

SERIES: List[MacroSeries] = [
    series(concept, code, "PortWatch", f"{port_id}|{field}", "D", entity_type="chokepoint")
    for port_id, code in CHOKEPOINTS.items()
    for concept, field in FIELDS.items()
]
