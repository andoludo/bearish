"""High-level orchestration: pull from sources, normalise, persist.

The service owns *no* domain logic — it depends only on the
:class:`FinancialDataSource` protocol and the :class:`SqliteRepository`,
following the Dependency Inversion Principle. This makes the entire
pipeline trivial to test with :class:`InMemorySource`.

Sources are tried in priority order; on failure or empty result, the
service falls back to the next source. This is the "polite, multi-provider"
behaviour required by the original brief.
"""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable, Iterable, Sequence
from typing import TypeVar

from bearish.exceptions import SourceError
from bearish.models import Asset, FinancialStatement, Price
from bearish.repository import SqliteRepository
from bearish.sources.base import FinancialDataSource

T = TypeVar("T")

logger = logging.getLogger(__name__)


class BearishService:
    """Pull financial data from one or more sources and persist it locally."""

    def __init__(
        self,
        repository: SqliteRepository,
        sources: Sequence[FinancialDataSource],
    ) -> None:
        if not sources:
            raise ValueError("BearishService requires at least one source")
        self.repository = repository
        self._sources: list[FinancialDataSource] = list(sources)

    def sync_assets(self, symbols: Iterable[str] | None = None) -> list[Asset]:
        symbol_list = list(symbols) if symbols is not None else None
        assets = self._first_non_empty(
            lambda src: src.fetch_assets(symbol_list),
            action="fetch_assets",
        )
        self.repository.save_assets(assets)
        return assets

    def sync_prices(
        self,
        symbols: Iterable[str],
        start: dt.date | None = None,
        end: dt.date | None = None,
    ) -> dict[str, list[Price]]:
        result: dict[str, list[Price]] = {}
        for symbol in symbols:
            def call(src: FinancialDataSource, s: str = symbol) -> list[Price]:
                return src.fetch_prices(s, start=start, end=end)

            prices = self._first_non_empty(call, action=f"fetch_prices({symbol})")
            self.repository.save_prices(prices)
            result[symbol.upper()] = prices
        return result

    def sync_statements(
        self, symbols: Iterable[str]
    ) -> dict[str, list[FinancialStatement]]:
        result: dict[str, list[FinancialStatement]] = {}
        for symbol in symbols:
            def call(src: FinancialDataSource, s: str = symbol) -> list[FinancialStatement]:
                return src.fetch_statements(s)

            statements = self._first_non_empty(call, action=f"fetch_statements({symbol})")
            self.repository.save_statements(statements)
            result[symbol.upper()] = statements
        return result

    def sync_all(
        self,
        symbols: Iterable[str],
        start: dt.date | None = None,
        end: dt.date | None = None,
    ) -> None:
        symbol_list = list(symbols)
        self.sync_assets(symbol_list)
        self.sync_prices(symbol_list, start=start, end=end)
        self.sync_statements(symbol_list)

    def _first_non_empty(
        self,
        call: Callable[[FinancialDataSource], list[T]],
        *,
        action: str,
    ) -> list[T]:
        """Try each source until one returns a non-empty list."""
        for source in self._sources:
            try:
                data = call(source)
            except SourceError as exc:
                logger.warning("source %r failed during %s: %s", source.name, action, exc)
                continue
            except Exception as exc:  # defensive: third-party libs raise anything
                logger.warning(
                    "source %r raised unexpectedly during %s: %s",
                    source.name,
                    action,
                    exc,
                )
                continue
            if data:
                return data
        return []
