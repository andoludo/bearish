"""Helpers for writing catalog modules concisely."""

from typing import Iterable, List, Optional

from bearish.macro.catalog.concepts import CONCEPTS
from bearish.macro.countries import Country
from bearish.macro.models import EntityType, Frequency, MacroSeries, MacroSources, Transform


def series(  # noqa: PLR0913
    concept: str,
    entity: str,
    source: MacroSources,
    source_code: str,
    frequency: Frequency,
    entity_type: EntityType = "country",
    transform: Transform = "none",
    seasonal_adj: bool = False,
    is_proxy: bool = False,
    unit: Optional[str] = None,
    description: Optional[str] = None,
) -> MacroSeries:
    """Build a catalog entry, taking category/unit/description from the concept."""
    definition = CONCEPTS[concept]
    return MacroSeries(
        concept=concept,
        entity=entity,
        entity_type=entity_type,
        category=definition.category,
        source=source,
        source_code=source_code,
        frequency=frequency,
        unit=unit or definition.unit,
        transform=transform,
        seasonal_adj=seasonal_adj,
        is_proxy=is_proxy,
        description=description or definition.description,
    )


def for_countries(  # noqa: PLR0913
    concept: str,
    countries: Iterable[Country],
    source: MacroSources,
    source_code_template: str,
    frequency: Frequency,
    transform: Transform = "none",
    seasonal_adj: bool = False,
    is_proxy: bool = False,
    code_attribute: str = "iso3",
) -> List[MacroSeries]:
    """One entry per country, formatting ``source_code_template`` with ``{code}``."""
    return [
        series(
            concept,
            country.iso3,
            source,
            source_code_template.format(code=getattr(country, code_attribute) or country.iso2),
            frequency,
            transform=transform,
            seasonal_adj=seasonal_adj,
            is_proxy=is_proxy,
        )
        for country in countries
    ]
