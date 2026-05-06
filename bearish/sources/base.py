"""The single contract every data source must satisfy.

Designed as a runtime-checkable :class:`Protocol` so that:

* concrete implementations don't need to inherit from a base class
  (favouring composition / structural typing — Dependency Inversion);
* the surface is small (Interface Segregation): three methods, no state.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from bearish.models import Asset, FinancialStatement, Price


@runtime_checkable
class FinancialDataSource(Protocol):
    """A read-only, polite source of financial data."""

    name: str

    def fetch_assets(self, symbols: Iterable[str] | None = None) -> list[Asset]:
        """Return the assets the source knows about, optionally filtered."""

    def fetch_prices(
        self,
        symbol: str,
        start: dt.date | None = None,
        end: dt.date | None = None,
    ) -> list[Price]:
        """Return OHLCV rows for a symbol within an optional date range."""

    def fetch_statements(self, symbol: str) -> list[FinancialStatement]:
        """Return the financial statements the source has for a symbol."""
