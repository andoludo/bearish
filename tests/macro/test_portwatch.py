import datetime
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.portwatch import (
    CHOKEPOINTS,
    FIELDS,
    PORTWATCH_URL,
    PortWatchSource,
    build_where,
    split_source_code,
)


@pytest.fixture
def portwatch_api(macro_data_dir: Path) -> requests_mock.Mocker:
    pages = {
        "0": (macro_data_dir / "portwatch" / "page_0.json").read_text(),
        "1000": (macro_data_dir / "portwatch" / "page_1000.json").read_text(),
    }

    def respond(request, context):  # type: ignore[no-untyped-def]
        offset = parse_qs(urlparse(request.url).query).get("resultOffset", ["0"])[0]
        return pages[offset]

    with requests_mock.Mocker() as req:
        req.get(PORTWATCH_URL, text=respond)
        yield req


def test_catalog_covers_every_chokepoint_and_field() -> None:
    entries = select_series(sources=["PortWatch"])
    assert len(entries) == len(CHOKEPOINTS) * len(FIELDS)
    hormuz = series_by_id()["TRANSITS_TANKER.HORMUZ"]
    assert hormuz.entity_type == "chokepoint"
    assert hormuz.frequency == "D"
    assert split_source_code(hormuz.source_code) == ("chokepoint6", "n_tanker")
    assert {"SUEZ", "BAB_EL_MANDEB", "TAIWAN_STRAIT", "PANAMA", "MALACCA"} <= {e.entity for e in entries}


def test_build_where_uses_date_literal() -> None:
    where = build_where({"chokepoint6", "chokepoint1"}, datetime.date(2026, 1, 1))
    assert where == "portid IN ('chokepoint1','chokepoint6') AND date >= DATE '2026-01-01'"
    assert build_where({"chokepoint6"}, None) == "portid IN ('chokepoint6')"


def test_portwatch_paginates_and_maps_chokepoints(portwatch_api: requests_mock.Mocker, macro_data_dir: Path) -> None:
    entries = select_series(MacroQuery(entities=["SUEZ", "BAB_EL_MANDEB", "HORMUZ"]), sources=["PortWatch"])
    assert len(entries) == 12
    observations = PortWatchSource(pause=0).read_observations(entries, start=datetime.date(2025, 6, 1))

    assert portwatch_api.call_count == 2  # one page beyond the 1000-row limit
    first_query = parse_qs(urlparse(portwatch_api.request_history[0].url).query)
    assert "chokepoint6" in first_query["where"][0]
    assert {"n_total", "n_tanker", "n_container", "capacity"} <= set(first_query["outFields"][0].split(","))

    by_series = {}
    for observation in observations:
        by_series.setdefault(observation.series_id, {})[observation.date] = observation.value
    assert set(by_series) == {e.series_id for e in entries}
    # The fixture covers 2025-06-01 .. 2026-10-18 daily for each chokepoint.
    assert min(by_series["TRANSITS.SUEZ"]) == datetime.date(2025, 6, 1)
    assert max(by_series["TRANSITS.HORMUZ"]) == datetime.date(2026, 10, 18)

    raw = json.loads((macro_data_dir / "portwatch" / "page_0.json").read_text())["features"]
    first_hormuz = next(f["attributes"] for f in raw if f["attributes"]["portid"] == "chokepoint6")
    day = datetime.date.fromisoformat(first_hormuz["date"])
    assert by_series["TRANSITS.HORMUZ"][day] == first_hormuz["n_total"]
    assert by_series["TRANSITS_TANKER.HORMUZ"][day] == first_hormuz["n_tanker"]
    assert by_series["CAPACITY_TONNES.HORMUZ"][day] == first_hormuz["capacity"]
    assert all(by_series["TRANSITS.SUEZ"][d] >= by_series["TRANSITS_TANKER.SUEZ"][d] for d in by_series["TRANSITS.SUEZ"])


def test_portwatch_ignores_other_sources() -> None:
    assert PortWatchSource(pause=0).read_observations(select_series(sources=["FRED"])[:2]) == []


@pytest.mark.network
def test_portwatch_live() -> None:
    entries = select_series(MacroQuery(series_ids=["TRANSITS.SUEZ", "TRANSITS_TANKER.HORMUZ"]))
    observations = PortWatchSource().read_observations(entries, start=datetime.date.today() - datetime.timedelta(days=30))
    assert {o.series_id for o in observations} == {"TRANSITS.SUEZ", "TRANSITS_TANKER.HORMUZ"}
