"""Unit tests for utility helpers."""
import datetime

import pytest

from bearish.utils.utils import batch, get_start_date, to_float, to_string


@pytest.mark.parametrize("length", ["1d", "5d", "1mo", "3mo", "6mo"])
def test_get_start_date_supports_every_series_length(length) -> None:
    # regression: month lengths used to crash on int("1mo")
    start = get_start_date(length)
    assert start is not None
    datetime.datetime.strptime(start, "%Y-%m-%d")


def test_get_start_date_max_means_no_start() -> None:
    assert get_start_date("max") is None


def test_batch_splits_evenly_and_keeps_remainder() -> None:
    assert batch([1, 2, 3, 4, 5], size=2) == [[1, 2], [3, 4], [5]]
    assert batch([], size=2) == []


def test_to_float_handles_junk() -> None:
    assert to_float("1.5") == 1.5
    assert to_float("None") is None
    assert to_float(None) is None
    assert to_float("not-a-number") is None


def test_to_string_handles_nan_and_none() -> None:
    assert to_string(float("nan")) is None
    assert to_string(None) is None
    assert to_string(42) == "42"
