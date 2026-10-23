import datetime
import json
from pathlib import Path

import pytest
import requests_mock

from bearish.signals.sources.usaspending import (
    RECIPIENT_URL,
    belongs_to,
    company_total,
    core_name,
    fetch_federal_awards,
    normalise_name,
)

DATA = Path(__file__).parents[1] / "data" / "signals" / "usaspending"
D = datetime.date


def _results(name: str) -> list:  # type: ignore[type-arg]
    return json.loads((DATA / f"{name}.json").read_text())["results"]


def test_names_are_normalised() -> None:
    assert normalise_name("Oracle Corp.") == "ORACLE"
    assert normalise_name("Palantir Technologies Inc.") == "PALANTIR TECHNOLOGIES"
    assert normalise_name("Johnson & Johnson") == "JOHNSON AND JOHNSON"
    assert core_name("Palantir Technologies Inc.") == "PALANTIR"
    assert core_name("Lockheed Martin Corporation") == "LOCKHEED MARTIN"


@pytest.mark.parametrize(
    ("recipient", "expected"),
    [
        ("ORACLE AMERICA, INC.", True),
        ("ORACLE HEALTH GOVERNMENT SERVICES, INC.", True),
        ("Oracle Corporation", True),
        ("ORACLE ELEVATOR HOLDCO, INC.", False),
        ("ORACLE SCHOOL DISTRICT", False),
        ("OHC ADVISORS, INC.", False),
    ],
)
def test_recipient_matching(recipient: str, expected: bool) -> None:
    assert belongs_to(recipient, "Oracle Corp") is expected


def test_company_total_keeps_only_the_company() -> None:
    oracle = _results("oracle_2025q2")
    kept = sum(r["amount"] for r in oracle if r["name"].startswith(("ORACLE AMERICA", "ORACLE HEALTH")))
    assert company_total(oracle, "Oracle Corp") == pytest.approx(kept)
    palantir = _results("palantir_2026q1")
    assert company_total(palantir, "Palantir Technologies Inc.") == pytest.approx(sum(r["amount"] for r in palantir))


def test_fetch_federal_awards_one_call_per_quarter() -> None:
    payload = json.loads((DATA / "palantir_2026q1.json").read_text())
    with requests_mock.Mocker() as req:
        req.post(RECIPIENT_URL, json=payload)
        signals = fetch_federal_awards({"PLTR": "Palantir Technologies Inc."}, D(2026, 1, 1), D(2026, 4, 15), pause=0)
    assert req.call_count == 2
    assert req.request_history[0].json()["filters"]["recipient_search_text"] == ["PALANTIR"]
    assert req.request_history[0].json()["filters"]["time_period"] == [
        {"start_date": "2026-01-01", "end_date": "2026-03-31"}
    ]
    assert [(s.symbol, s.signal, s.date) for s in signals] == [
        ("PLTR", "FED_AWARDS_USD", D(2026, 3, 31)),
        ("PLTR", "FED_AWARDS_USD", D(2026, 6, 30)),
    ]
    assert signals[0].value > 5e8


@pytest.mark.network
def test_federal_awards_live() -> None:
    signals = fetch_federal_awards({"PLTR": "Palantir Technologies Inc."}, D(2026, 1, 1), D(2026, 3, 31))
    assert signals and signals[0].value > 0
