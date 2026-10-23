"""GDELT catalog: daily conflict counts, Goldstein score and tone for curated
country pairs, plus material-conflict counts for every priority country."""

from typing import List

from bearish.macro.catalog._builder import series
from bearish.macro.countries import priority_countries
from bearish.macro.models import MacroSeries
from bearish.macro.sources.gdelt import METRICS, PAIRS, pair_entity

SERIES: List[MacroSeries] = [
    *[
        series(concept, pair_entity(a, b), "GDELT", f"pair|{a}|{b}|{metric}", "D", entity_type="country_pair")
        for a, b in PAIRS
        for concept, metric in METRICS.items()
    ],
    *[
        series("GDELT_CONFLICT_EVENTS", country.iso3, "GDELT", f"country|{country.iso3}|conflict_events", "D")
        for country in priority_countries()
    ],
]
