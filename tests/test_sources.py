"""Tests for the source abstraction and in-memory implementation."""
from __future__ import annotations

import datetime as dt

import pytest

from bearish.exceptions import SourceError
from bearish.models import Asset, FinancialStatement, Price
from bearish.sources.base import FinancialDataSource
from bearish.sources.memory import InMemorySource


class TestInMemorySource:
    def test_implements_protocol(self) -> None:
        source = InMemorySource(name="memory")
        assert isinstance(source, FinancialDataSource)

    def test_has_a_name(self) -> None:
        assert InMemorySource(name="x").name == "x"

    def test_returns_assets_filtered_by_symbols(self, sample_asset: Asset) -> None:
        source = InMemorySource(name="memory", assets=[sample_asset])
        assert source.fetch_assets(["AAPL"]) == [sample_asset]
        assert source.fetch_assets(["MSFT"]) == []

    def test_no_filter_returns_everything(self, sample_asset: Asset) -> None:
        source = InMemorySource(name="memory", assets=[sample_asset])
        assert source.fetch_assets(None) == [sample_asset]

    def test_fetch_prices_filters_by_date_range(self, sample_prices: list[Price]) -> None:
        source = InMemorySource(name="memory", prices=sample_prices)
        result = source.fetch_prices(
            "AAPL",
            start=dt.date(2024, 1, 2),
            end=dt.date(2024, 1, 2),
        )
        assert len(result) == 1
        assert result[0].date == dt.date(2024, 1, 2)

    def test_fetch_prices_unknown_symbol_is_empty(self) -> None:
        assert InMemorySource(name="memory").fetch_prices("UNKNOWN") == []

    def test_fetch_statements(self, sample_statement: FinancialStatement) -> None:
        source = InMemorySource(name="memory", statements=[sample_statement])
        assert source.fetch_statements("AAPL") == [sample_statement]
        assert source.fetch_statements("MSFT") == []

    def test_failure_mode_raises_source_error(self) -> None:
        source = InMemorySource(name="broken", fail=True)
        with pytest.raises(SourceError):
            source.fetch_prices("AAPL")
        with pytest.raises(SourceError):
            source.fetch_assets(["AAPL"])
        with pytest.raises(SourceError):
            source.fetch_statements("AAPL")
