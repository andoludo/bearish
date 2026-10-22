"""Provider implementations for the macro catalog."""

from typing import List

from bearish.macro.sources.base import AbstractMacroSource
from bearish.macro.sources.fred import FredSource
from bearish.macro.sources.kenfrench import KenFrenchSource
from bearish.macro.sources.oecd import OecdSource

__all__ = ["AbstractMacroSource", "FredSource", "KenFrenchSource", "OecdSource", "default_macro_sources"]


def default_macro_sources() -> List[AbstractMacroSource]:
    """Every provider with catalog entries, in a sensible fetch order."""
    return [FredSource(), OecdSource(), KenFrenchSource()]
