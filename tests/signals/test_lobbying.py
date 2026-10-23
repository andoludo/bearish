import datetime
import json
from pathlib import Path

import pytest
import requests_mock

from bearish.database.crud import BearishDb
from bearish.signals.pipelines.elections import write_lobbying
from bearish.signals.sources.lobbying import (
    LDA_URL,
    fetch_client_filings,
    fetch_lobbying,
    normalize_company_name,
    period_end,
    quarterly_spend,
)

DATA_DIR = Path(__file__).parents[1] / "data" / "signals" / "lobbying"


def _pages() -> list:
    return [json.loads((DATA_DIR / f"lda_nvidia_2025_page{i}.json").read_text()) for i in (1, 2)]


def _mock(req: requests_mock.Mocker) -> None:
    page1, page2 = _pages()
    req.get(LDA_URL, [{"status_code": 429, "headers": {"Retry-After": "0"}}, {"json": page1}])
    req.get(page1["next"], json=page2)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("NVIDIA CORPORATION", "nvidia"),
        ("Nvidia Corp", "nvidia"),
        ("Lockheed Martin Corp.", "lockheed martin"),
        ("AT&T Inc.", "at and t"),
    ],
)
def test_normalize_company_name(name: str, expected: str) -> None:
    assert normalize_company_name(name) == expected


def test_period_end() -> None:
    assert period_end(2025, "third_quarter") == datetime.date(2025, 9, 30)
    assert period_end(2006, "mid_year") == datetime.date(2006, 6, 30)
    assert period_end(2025, "unknown") is None


def test_pagination_and_rate_limit_retry() -> None:
    with requests_mock.Mocker() as req:
        _mock(req)
        filings = fetch_client_filings("nvidia", 2025, pause=0)
    assert len(filings) == 24


def test_quarterly_spend_prefers_in_house_expenses_and_amendments() -> None:
    filings = [f for page in _pages() for f in page["results"]]
    signals = {s.date: s for s in quarterly_spend(filings, "NVDA", "nvidia")}
    # in-house reports (expenses) win over outside firms' income
    assert signals[datetime.date(2025, 3, 31)].value == 940_000
    # Q3 was amended (3A, 1.95M) after the original Q3 (1.9M): the amendment wins, dated when it was posted
    assert signals[datetime.date(2025, 9, 30)].value == 1_950_000
    assert signals[datetime.date(2025, 9, 30)].as_of == datetime.date(2026, 1, 18)
    assert signals[datetime.date(2025, 12, 31)].value == 1_460_000
    assert all(s.signal == "LOBBYING_USD" and s.symbol == "NVDA" for s in signals.values())


def test_outside_firms_are_summed_when_no_in_house_report() -> None:
    filings = [f for page in _pages() for f in page["results"] if f["registrant"]["name"] != "NVIDIA CORPORATION"]
    q3 = {s.date: s.value for s in quarterly_spend(filings, "NVDA", "nvidia")}[datetime.date(2025, 9, 30)]
    assert q3 == 80_000 + 50_000 + 80_000 + 40_000 + 40_000


def test_write_lobbying_uses_equity_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from bearish.signals.pipelines import elections

    db = BearishDb(database_path=tmp_path / "lob.db")
    monkeypatch.setattr(elections, "_equity_names", lambda _db, symbols: {"NVDA": "NVIDIA Corporation"})
    with requests_mock.Mocker() as req:
        _mock(req)
        written = write_lobbying(db, ["NVDA"], [2025], pause=0)
    assert written == 4
    stored = db.read_ticker_signals(symbols=["NVDA"], signals=["LOBBYING_USD"])
    assert {s.date.month for s in stored} == {3, 6, 9, 12}


def test_fetch_lobbying_skips_unknown_names() -> None:
    assert fetch_lobbying(["ZZZZ"], [2025], names={"ZZZZ": "Inc."}, pause=0) == []


@pytest.mark.network
def test_fetch_lobbying_live() -> None:
    signals = fetch_lobbying(
        ["LMT"], [datetime.date.today().year - 1], names={"LMT": "Lockheed Martin Corp"}, pause=1.0
    )
    assert signals and all(s.value > 0 for s in signals)
