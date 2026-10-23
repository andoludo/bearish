import datetime
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.fred import FRED_API_URL, FRED_GRAPH_URL, FredSource, parse_graph_csv


def test_parse_graph_csv_handles_single_and_zipped_exports(macro_data_dir: Path) -> None:
    single = parse_graph_csv((macro_data_dir / "fred" / "T10Y2Y.csv").read_bytes())
    assert list(single.columns) == ["T10Y2Y"]
    mixed = parse_graph_csv((macro_data_dir / "fred" / "fredgraph_mixed.zip").read_bytes())
    assert set(mixed.columns) == {"DGS10", "T10Y2Y", "BAMLH0A0HYM2", "CPILFESL", "PAYEMS"}


def test_fred_graph_path_maps_columns_to_series(macro_data_dir: Path) -> None:
    ids = ["Y10.USA", "CURVE_10_2.USA", "HY_SPREAD.USA", "CORE_CPI_YOY.USA", "PAYROLLS_CHG.USA"]
    wanted = [series_by_id()[i] for i in ids]
    source = FredSource(pause=0)
    with requests_mock.Mocker() as req:
        req.get(FRED_GRAPH_URL, content=(macro_data_dir / "fred" / "fredgraph_mixed.zip").read_bytes())
        observations = source.read_observations(wanted, start=datetime.date(2025, 1, 1))
    by_series = {}
    for observation in observations:
        by_series.setdefault(observation.series_id, []).append(observation)
    assert set(by_series) == set(ids)
    assert all(o.date >= datetime.date(2025, 1, 1) for o in observations)
    core = sorted(by_series["CORE_CPI_YOY.USA"], key=lambda o: o.date)
    assert 1.0 < core[-1].value < 6.0  # a y/y percentage, not an index level
    payrolls = by_series["PAYROLLS_CHG.USA"]
    assert all(abs(o.value) < 1_000 for o in payrolls)  # monthly change in thousands
    assert req.call_count == 1  # five ids, one request


def test_fred_api_path_when_key_is_set() -> None:
    entry = series_by_id()["Y10.USA"]
    source = FredSource(pause=0)
    source.set_api_key("secret")
    try:
        with requests_mock.Mocker() as req:
            req.get(
                FRED_API_URL,
                json={"observations": [{"date": "2026-01-02", "value": "4.1"}, {"date": "2026-01-05", "value": "."}]},
            )
            observations = source.read_observations([entry])
            assert req.last_request.qs["api_key"] == ["secret"]
    finally:
        source.set_api_key(None)
    assert [(o.date, o.value) for o in observations] == [(datetime.date(2026, 1, 2), 4.1)]


def test_fred_ignores_series_from_other_sources() -> None:
    oecd_only = select_series(sources=["OECD"])[:3]
    assert FredSource(pause=0).read_observations(oecd_only) == []


@pytest.mark.network
def test_fred_live() -> None:
    entry = series_by_id()["CURVE_10_2.USA"]
    observations = FredSource().read_observations([entry], start=datetime.date.today() - datetime.timedelta(days=30))
    assert observations
    assert observations[-1].as_of == datetime.date.today()
    assert select_series(MacroQuery(series_ids=["CURVE_10_2.USA"]))
