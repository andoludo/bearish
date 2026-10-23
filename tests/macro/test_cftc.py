import datetime
import json
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series
from bearish.macro.commodities import commodities_with
from bearish.macro.models import MacroQuery
from bearish.macro.sources.cftc import CFTC_LEGACY_FUTURES_URL, CftcSource, derive_fields, split_source_code


def test_split_source_code() -> None:
    assert split_source_code("088691|net_spec") == ("088691", "net_spec")
    with pytest.raises(ValueError):
        split_source_code("088691|bogus")


def test_derive_fields(macro_data_dir: Path) -> None:
    rows = json.loads((macro_data_dir / "cftc" / "gold_088691.json").read_text())
    frame = derive_fields(rows)
    first = frame.iloc[0]
    assert frame.index[0] == datetime.datetime(2024, 1, 2)
    assert first["net_spec"] == 290706 - 83057
    assert first["net_spec_pct_oi"] == pytest.approx((290706 - 83057) / 500364 * 100)
    assert first["open_interest"] == 500364
    assert derive_fields([]).empty


def test_catalog_has_three_series_per_market() -> None:
    entries = select_series(sources=["CFTC"])
    markets = {c.code for c in commodities_with("cftc_market_code")}
    assert {e.entity for e in entries} == markets
    assert len(entries) == 3 * len(markets)


def test_cftc_source_one_request_per_market(macro_data_dir: Path) -> None:
    entries = select_series(MacroQuery(entities=["GOLD"]), sources=["CFTC"])
    assert len(entries) == 3
    source = CftcSource(pause=0)
    with requests_mock.Mocker() as req:
        req.get(CFTC_LEGACY_FUTURES_URL, text=(macro_data_dir / "cftc" / "gold_088691.json").read_text())
        observations = source.read_observations(entries, start=datetime.date(2025, 1, 1))
    assert req.call_count == 1
    assert req.last_request.qs["cftc_contract_market_code"] == ["088691"]
    assert "2025-01-01" in req.last_request.qs["$where"][0]
    assert {o.series_id for o in observations} == {"COT_NET_SPEC.GOLD", "COT_NET_SPEC_PCT_OI.GOLD", "COT_OPEN_INTEREST.GOLD"}
    assert all(o.date >= datetime.date(2025, 1, 1) for o in observations)
    pct = [o.value for o in observations if o.series_id == "COT_NET_SPEC_PCT_OI.GOLD"]
    assert all(-100 <= v <= 100 for v in pct)


def test_cftc_paginates(macro_data_dir: Path) -> None:
    rows = json.loads((macro_data_dir / "cftc" / "gold_088691.json").read_text())
    entries = select_series(MacroQuery(entities=["GOLD"], concepts=["COT_OPEN_INTEREST"]), sources=["CFTC"])
    source = CftcSource(pause=0, page_size=50)
    with requests_mock.Mocker() as req:
        req.get(CFTC_LEGACY_FUTURES_URL, [{"json": rows[:50]}, {"json": rows[50:100]}, {"json": rows[100:]}])
        observations = source.read_observations(entries)
    assert req.call_count == 3
    assert len(observations) == len(rows)


@pytest.mark.network
def test_cftc_live() -> None:
    entries = select_series(MacroQuery(entities=["WTI"]), sources=["CFTC"])
    observations = CftcSource().read_observations(entries, start=datetime.date.today() - datetime.timedelta(days=60))
    assert {o.series_id for o in observations} == {e.series_id for e in entries}
