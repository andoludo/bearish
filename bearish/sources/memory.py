"""An in-memory source — useful for tests and as a reference implementation."""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass, field

from bearish.exceptions import SourceError
from bearish.models import Asset, FinancialStatement, Price


@dataclass
class InMemorySource:
    name: str
    assets: list[Asset] = field(default_factory=list)
    prices: list[Price] = field(default_factory=list)
    statements: list[FinancialStatement] = field(default_factory=list)
    fail: bool = False

    def fetch_assets(self, symbols: Iterable[str] | None = None) -> list[Asset]:
        self._maybe_fail()
        if symbols is None:
            return list(self.assets)
        wanted = {s.upper() for s in symbols}
        return [a for a in self.assets if a.symbol in wanted]

    def fetch_prices(
        self,
        symbol: str,
        start: dt.date | None = None,
        end: dt.date | None = None,
    ) -> list[Price]:
        self._maybe_fail()
        symbol = symbol.upper()
        return [
            p
            for p in self.prices
            if p.symbol == symbol
            and (start is None or p.date >= start)
            and (end is None or p.date <= end)
        ]

    def fetch_statements(self, symbol: str) -> list[FinancialStatement]:
        self._maybe_fail()
        symbol = symbol.upper()
        return [s for s in self.statements if s.symbol == symbol]

    def _maybe_fail(self) -> None:
        if self.fail:
            raise SourceError(f"source {self.name!r} is configured to fail")
