import datetime
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.catalog import select_series
from bearish.macro.catalog.kenfrench import REGIONAL_ZIPS, US_DAILY_ZIP, US_MOMENTUM_ZIP
from bearish.macro.models import MacroQuery
from bearish.macro.sources.kenfrench import KenFrenchSource, read_factor_zip


@pytest.fixture
def kenfrench_api(macro_data_dir: Path) -> requests_mock.Mocker:
    def serve(request, context):  # type: ignore[no-untyped-def]
        return (macro_data_dir / "kenfrench" / request.url.rsplit("/", 1)[1]).read_bytes()

    with requests_mock.Mocker() as req:
        req.get(re.compile(r"https://mba\.tuck\.dartmouth\.edu/pages/faculty/ken\.french/ftp/.*"), content=serve)
        yield req


def test_read_factor_zip_daily_and_monthly(macro_data_dir: Path) -> None:
    daily = read_factor_zip((macro_data_dir / "kenfrench" / US_DAILY_ZIP).read_bytes())
    assert list(daily.columns) == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
    assert daily.index.is_monotonic_increasing
    assert daily.index[-1] == datetime.datetime(2026, 8, 31)
    monthly = read_factor_zip((macro_data_dir / "kenfrench" / "Europe_5_Factors_CSV.zip").read_bytes())
    assert monthly.index[-1] == datetime.datetime(2026, 8, 1)
    # the trailing annual block must not leak into the data
    assert monthly.index.year.min() > 1900
    assert len(monthly) < 400
    momentum = read_factor_zip((macro_data_dir / "kenfrench" / US_MOMENTUM_ZIP).read_bytes())
    assert list(momentum.columns) == ["Mom"]


def test_kenfrench_source_maps_every_catalog_series(kenfrench_api: requests_mock.Mocker) -> None:
    entries = select_series(sources=["KenFrench"])
    assert len(entries) == 7 + 6 * len(REGIONAL_ZIPS)
    observations = KenFrenchSource(pause=0).read_observations(entries, start=datetime.date(2026, 6, 1))
    assert {o.series_id for o in observations} == {e.series_id for e in entries}
    assert kenfrench_api.call_count == 2 + len(REGIONAL_ZIPS)  # one download per zip
    assert all(o.date >= datetime.date(2026, 6, 1) for o in observations)
    mkt_us = [o for o in observations if o.series_id == "FF_MKT.USA"]
    assert len(mkt_us) > 40  # daily
    mkt_eur = [o for o in observations if o.series_id == "FF_MKT.EUR"]
    assert len(mkt_eur) == 3  # June, July, August
    assert all(abs(o.value) < 30 for o in observations)


def test_kenfrench_catalog_entities_and_frequencies() -> None:
    by_id = {s.series_id: s for s in select_series(MacroQuery(categories=["factor"]))}
    assert by_id["FF_MOM.USA"].frequency == "D"
    assert by_id["FF_HML.EM"].frequency == "M"
    assert by_id["FF_HML.EM"].entity_type == "region"
    assert by_id["FF_HML.JPN"].entity_type == "country"


@pytest.mark.network
def test_kenfrench_live() -> None:
    entries = select_series(MacroQuery(series_ids=["FF_MKT.USA", "FF_MOM.USA"]))
    observations = KenFrenchSource().read_observations(entries, start=datetime.date.today() - datetime.timedelta(days=120))
    assert {o.series_id for o in observations} == {"FF_MKT.USA", "FF_MOM.USA"}
