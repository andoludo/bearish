import json
from pathlib import Path

import pytest
import requests_mock

from bearish.macro.commodities import COMMODITIES, commodities_by_code
from bearish.macro.comtrade_codes import M49_BY_ISO3, m49_for
from bearish.macro.countries import COUNTRIES, country_from, priority_countries
from bearish.macro.sources.comtrade import (
    COMTRADE_PREVIEW_URL,
    comtrade_params,
    exposures_from_payload,
    fetch_country_exposures,
    hs_codes,
)


def test_every_priority_country_has_a_reporter_code() -> None:
    assert {c.iso3 for c in priority_countries()} <= set(M49_BY_ISO3)
    assert m49_for("fra") == 251
    assert m49_for("XXX") is None
    assert set(M49_BY_ISO3) <= {c.iso3 for c in COUNTRIES}


def test_params_include_total_and_all_hs_codes() -> None:
    params = comtrade_params(251, 2023, "X", list(COMMODITIES))
    codes = params["cmdCode"].split(",")
    assert codes[0] == "TOTAL"
    assert "2709" in codes and "7108" in codes
    assert len(codes) == 1 + len(hs_codes(list(COMMODITIES)))


def test_exposures_from_payload(macro_data_dir: Path) -> None:
    payload = json.loads((macro_data_dir / "comtrade" / "fra_2023_X.json").read_text())
    france = country_from("FRA")
    assert france is not None
    exposures = exposures_from_payload(payload, france, 2023, "X", list(COMMODITIES))
    by_code = {e.commodity: e for e in exposures}
    assert by_code["WHEAT"].direction == "export"
    assert 0 < by_code["WHEAT"].share < 0.05
    assert sum(e.share for e in exposures) < 1.0
    # copper sums its two HS codes
    copper = commodities_by_code()["COPPER"]
    expected = sum(r["primaryValue"] for r in payload["data"] if r["cmdCode"] in copper.hs_codes)
    assert by_code["COPPER"].value_usd == pytest.approx(expected)
    assert exposures_from_payload({"data": []}, france, 2023, "X", list(COMMODITIES)) == []


def test_fetch_country_exposures_requests_both_flows(macro_data_dir: Path) -> None:
    france = country_from("FRA")
    assert france is not None
    with requests_mock.Mocker() as req:
        req.get(
            COMTRADE_PREVIEW_URL,
            text=lambda request, context: (
                macro_data_dir / "comtrade" / f"fra_2023_{request.qs['flowcode'][0].upper()}.json"
            ).read_text(),
        )
        exposures = fetch_country_exposures([france], 2023, pause=0)
    assert req.call_count == 2
    assert {e.direction for e in exposures} == {"export", "import"}
    assert all(e.country == "FRA" and e.year == 2023 for e in exposures)


def test_fetch_country_exposures_retries_on_throttle(macro_data_dir: Path) -> None:
    france = country_from("FRA")
    assert france is not None
    body = (macro_data_dir / "comtrade" / "fra_2023_X.json").read_text()
    with requests_mock.Mocker() as req:
        req.get(COMTRADE_PREVIEW_URL, [{"status_code": 429}, {"text": body}, {"text": body}])
        from bearish.macro.sources import comtrade

        comtrade._get.retry.wait = lambda *_: 0  # type: ignore[attr-defined]
        exposures = fetch_country_exposures([france], 2023, pause=0)
    assert req.call_count == 3
    assert exposures


@pytest.mark.network
def test_comtrade_live() -> None:
    belgium = country_from("BEL")
    assert belgium is not None
    exposures = fetch_country_exposures([belgium], 2023, pause=6)
    assert {e.direction for e in exposures} == {"export", "import"}
