"""The macro catalog: every series bearish knows how to fetch.

Each provider contributes a module in this package exposing a module-level
``SERIES: list[MacroSeries]``. Modules are discovered automatically so adding
a provider never means editing a central registry.
"""

import importlib
import pkgutil
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

from bearish.macro.catalog.concepts import CONCEPTS, ConceptDefinition
from bearish.macro.models import MacroQuery, MacroSeries, MacroSources

__all__ = ["CONCEPTS", "ConceptDefinition", "catalog", "select_series", "series_by_id"]


@lru_cache(maxsize=1)
def catalog() -> Tuple[MacroSeries, ...]:
    """All catalog entries, provider modules loaded lazily on first use."""
    entries: List[MacroSeries] = []
    package = importlib.import_module(__name__)
    for module_info in pkgutil.iter_modules(package.__path__):
        if module_info.name.startswith("_") or module_info.name == "concepts":
            continue
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        entries.extend(getattr(module, "SERIES", []))
    return tuple(entries)


@lru_cache(maxsize=1)
def series_by_id() -> Dict[str, MacroSeries]:
    return {series.series_id: series for series in catalog()}


def select_series(
    query: Optional[MacroQuery] = None,
    sources: Optional[Sequence[MacroSources]] = None,
) -> List[MacroSeries]:
    """Filter the catalog; an empty query returns everything."""
    query = query or MacroQuery()
    wanted_sources = set(sources or query.sources)
    selected = []
    for series in catalog():
        if query.series_ids and series.series_id not in query.series_ids:
            continue
        if query.concepts and series.concept not in query.concepts:
            continue
        if query.entities and series.entity not in query.entities:
            continue
        if query.categories and series.category not in query.categories:
            continue
        if wanted_sources and series.source not in wanted_sources:
            continue
        selected.append(series)
    return selected
