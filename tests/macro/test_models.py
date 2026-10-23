import datetime

import pandas as pd
import pytest

from bearish.macro.catalog._builder import series
from bearish.macro.models import MacroSeries, Observation
from bearish.macro.transform import apply_transform, fetch_start, observations_from_series, parse_period


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("2026", datetime.date(2026, 1, 1)),
        ("2026-09", datetime.date(2026, 9, 1)),
        ("202609", datetime.date(2026, 9, 1)),
        ("2026M09", datetime.date(2026, 9, 1)),
        ("2026-Q3", datetime.date(2026, 7, 1)),
        ("2026Q1", datetime.date(2026, 1, 1)),
        ("2026-S2", datetime.date(2026, 7, 1)),
        ("2026-09-15", datetime.date(2026, 9, 15)),
        ("2026-09-15T00:00:00", datetime.date(2026, 9, 15)),
        ("2026-W02", datetime.date(2026, 1, 5)),
        (pd.Timestamp("2026-03-02"), datetime.date(2026, 3, 2)),
        ("n/a", None),
    ],
)
def test_parse_period(label, expected) -> None:
    assert parse_period(label) == expected


def test_series_id_is_derived_and_normalised() -> None:
    macro_series = MacroSeries(
        concept=" cpi_yoy ",
        entity="fra",
        entity_type="country",
        category="inflation",
        source="OECD",
        source_code="x",
        frequency="M",
        unit="%",
    )
    assert macro_series.series_id == "CPI_YOY.FRA"
    assert macro_series.concept == "CPI_YOY"


def test_observation_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError):
        Observation(series_id="X.Y", date=datetime.date(2026, 1, 1), value=float("nan"), as_of=datetime.date(2026, 1, 2))


def test_yoy_transform_uses_frequency_periods() -> None:
    index = pd.date_range("2020-01-01", periods=15, freq="MS")
    values = pd.Series(range(100, 115), index=index, dtype=float)
    yoy = apply_transform(values, "yoy", "M")
    assert yoy.iloc[:12].isna().all()
    assert yoy.iloc[12] == pytest.approx(12.0)


def test_observations_from_series_transforms_before_start_cut() -> None:
    macro_series = series("IP_YOY", "FRA", "OECD", "code", "M", transform="yoy")
    index = pd.date_range("2024-01-01", periods=24, freq="MS")
    values = pd.Series([100 + i for i in range(24)], index=index, dtype=float)
    observations = observations_from_series(macro_series, values, datetime.date(2026, 1, 1), start=datetime.date(2025, 6, 1))
    assert observations
    assert min(o.date for o in observations) == datetime.date(2025, 6, 1)
    # y/y for June 2025 = (117 / 105 - 1) * 100
    june = next(o for o in observations if o.date == datetime.date(2025, 6, 1))
    assert june.value == pytest.approx((117 / 105 - 1) * 100)


def test_fetch_start_extends_history_for_transforms() -> None:
    level = series("Y10", "FRA", "OECD", "code", "M")
    yoy = series("IP_YOY", "FRA", "OECD", "code", "M", transform="yoy")
    start = datetime.date(2026, 1, 1)
    assert fetch_start(level, start) == start
    assert fetch_start(yoy, start) < datetime.date(2025, 1, 1)
    assert fetch_start(yoy, None) is None
