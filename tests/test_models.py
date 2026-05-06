"""Tests for the common data model."""
from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from bearish.models import Asset, AssetKind, FinancialStatement, Price


class TestAsset:
    def test_minimal_asset_only_requires_symbol(self) -> None:
        asset = Asset(symbol="AAPL")
        assert asset.symbol == "AAPL"
        assert asset.kind is AssetKind.EQUITY
        assert asset.name is None

    def test_symbol_is_normalised_to_upper_case(self) -> None:
        assert Asset(symbol="aapl").symbol == "AAPL"

    def test_symbol_must_not_be_blank(self) -> None:
        with pytest.raises(ValidationError):
            Asset(symbol="   ")

    def test_assets_are_hashable_by_symbol(self) -> None:
        a = Asset(symbol="AAPL", name="Apple")
        b = Asset(symbol="AAPL", name="Apple Inc.")
        assert hash(a) == hash(b)
        assert {a, b} == {a}


class TestPrice:
    def test_high_must_not_be_below_low(self) -> None:
        with pytest.raises(ValidationError):
            Price(
                symbol="AAPL",
                date=dt.date(2024, 1, 1),
                open=10,
                high=5,
                low=8,
                close=9,
                volume=1,
                source="memory",
            )

    def test_volume_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            Price(
                symbol="AAPL",
                date=dt.date(2024, 1, 1),
                open=10,
                high=11,
                low=9,
                close=10,
                volume=-1,
                source="memory",
            )

    def test_symbol_is_normalised(self, sample_prices: list[Price]) -> None:
        p = Price(
            symbol="aapl",
            date=dt.date(2024, 1, 1),
            open=1,
            high=2,
            low=0.5,
            close=1.5,
            volume=10,
            source="memory",
        )
        assert p.symbol == "AAPL"


class TestFinancialStatement:
    def test_period_must_be_known(self) -> None:
        with pytest.raises(ValidationError):
            FinancialStatement(
                symbol="AAPL",
                period_end=dt.date(2024, 12, 31),
                period="weekly",  # type: ignore[arg-type]
                source="memory",
            )

    def test_optional_metrics_default_to_none(self) -> None:
        st = FinancialStatement(
            symbol="AAPL",
            period_end=dt.date(2024, 12, 31),
            period="annual",
            source="memory",
        )
        assert st.revenue is None
        assert st.net_income is None
