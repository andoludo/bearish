import datetime
from pathlib import Path

import pandas as pd
import pytest
import requests_mock

from bearish.macro.catalog import select_series
from bearish.macro.commodities import commodities_with
from bearish.macro.models import MacroQuery
from bearish.macro.sources.pinksheet import PINK_SHEET_URL, PinkSheetSource, normalise_header, parse_pink_sheet


def test_normalise_header_strips_footnotes_and_whitespace() -> None:
    assert normalise_header("Coal, South African **") == "Coal, South African"
    assert normalise_header("Rice, Thai 5% ") == "Rice, Thai 5%"


def test_parse_pink_sheet(macro_data_dir: Path) -> None:
    frame = parse_pink_sheet((macro_data_dir / "pinksheet" / "cmo_monthly_trimmed.xlsx").read_bytes())
    assert frame.index.min() == pd.Timestamp(2021, 1, 1)
    assert "Crude oil, Brent" in frame.columns
    assert "Coal, South African" in frame.columns
    assert frame["Gold"].notna().all()


def test_catalog_covers_every_commodity_with_a_pink_sheet_series() -> None:
    entries = select_series(sources=["WorldBankPinkSheet"])
    assert {e.entity for e in entries} == {c.code for c in commodities_with("pinksheet_series")}
    assert all(e.concept == "PRICE_M" and e.entity_type == "commodity" and e.frequency == "M" for e in entries)


def test_pink_sheet_source_reads_observations(macro_data_dir: Path) -> None:
    entries = select_series(MacroQuery(entities=["BRENT", "GOLD", "COPPER", "WHEAT", "RICE"]), sources=["WorldBankPinkSheet"])
    source = PinkSheetSource(pause=0)
    with requests_mock.Mocker() as req:
        req.get(PINK_SHEET_URL, content=(macro_data_dir / "pinksheet" / "cmo_monthly_trimmed.xlsx").read_bytes())
        observations = source.read_observations(entries, start=datetime.date(2025, 1, 1))
    assert req.call_count == 1
    assert {o.series_id for o in observations} == {"PRICE_M.BRENT", "PRICE_M.GOLD", "PRICE_M.COPPER", "PRICE_M.WHEAT", "PRICE_M.RICE"}
    assert all(o.date >= datetime.date(2025, 1, 1) for o in observations)
    gold = [o for o in observations if o.series_id == "PRICE_M.GOLD"]
    assert all(o.value > 1000 for o in gold)


def test_pink_sheet_skips_unknown_columns(macro_data_dir: Path) -> None:
    entries = select_series(MacroQuery(entities=["COCOA"]), sources=["WorldBankPinkSheet"])  # not in trimmed fixture
    with requests_mock.Mocker() as req:
        req.get(PINK_SHEET_URL, content=(macro_data_dir / "pinksheet" / "cmo_monthly_trimmed.xlsx").read_bytes())
        assert PinkSheetSource(pause=0).read_observations(entries) == []


@pytest.mark.network
def test_pink_sheet_live() -> None:
    entries = select_series(MacroQuery(entities=["BRENT"]), sources=["WorldBankPinkSheet"])
    observations = PinkSheetSource().read_observations(entries, start=datetime.date.today() - datetime.timedelta(days=400))
    assert observations
