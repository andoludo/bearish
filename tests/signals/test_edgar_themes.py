import datetime
import json
import re
from pathlib import Path
from typing import Dict, Set
from urllib.parse import parse_qs, urlparse

import pytest
import requests_mock
from tenacity import wait_none

from bearish.signals.sources import edgar_themes
from bearish.signals.sources.edgar_themes import (
    EFTS_URL,
    FilingHits,
    fetch_theme_hits,
    fetch_theme_mentions,
    parse_hits,
    quarter_end,
    quarters,
    theme_filings_observation,
    theme_filings_series,
    ticker_signals,
)
from bearish.signals.themes import THEMES

DATA = Path(__file__).parents[1] / "data" / "signals" / "edgar_themes"
D = datetime.date
THEME = THEMES["ai_accelerator"]
_TICKER = re.compile(r"\(([A-Z.,\s-]+)\)\s+\(CIK (\d{10})\)")


def _fixture(name: str) -> Dict:  # type: ignore[type-arg]
    return json.loads((DATA / name).read_text())


class FakeMapper:
    """cik -> tickers built from the display names in the recorded hits (no SEC download)."""

    def __init__(self) -> None:
        mapping: Dict[str, Set[str]] = {}
        for path in DATA.glob("*.json"):
            for hit in json.loads(path.read_text())["hits"]["hits"]:
                for name in hit["_source"]["display_names"]:
                    if match := _TICKER.search(name):
                        tickers = {t.strip() for t in match.group(1).split(",") if t.strip()}
                        mapping.setdefault(match.group(2), set()).update(tickers)
        self.cik_to_tickers = mapping


def _respond(request, context):  # type: ignore[no-untyped-def]
    params = parse_qs(urlparse(request.url).query)
    start, offset = params["startdt"][0], int(params.get("from", ["0"])[0])
    quarter = "2025q1" if start.startswith("2025") else "2024q1"
    path = DATA / f"ai_accelerator_{quarter}_from{offset}.json"
    return json.loads(path.read_text())


@pytest.fixture
def efts() -> requests_mock.Mocker:
    with requests_mock.Mocker() as req:
        req.get(re.compile(re.escape(EFTS_URL) + ".*"), json=_respond)
        yield req


def test_quarters_and_quarter_end() -> None:
    assert quarters(D(2024, 11, 5), D(2025, 4, 10)) == [
        (D(2024, 10, 1), D(2024, 12, 31)),
        (D(2025, 1, 1), D(2025, 3, 31)),
        (D(2025, 4, 1), D(2025, 4, 10)),
    ]
    assert quarter_end(D(2025, 4, 10)) == D(2025, 6, 30)
    assert quarter_end(D(2025, 11, 30)) == D(2025, 12, 31)
    assert quarter_end(D(2024, 2, 29)) == D(2024, 3, 31)


def test_parse_hits_reads_documents() -> None:
    hits, total, lower_bound = parse_hits(_fixture("ai_accelerator_2025q1_from0.json"))
    assert total == 155
    assert not lower_bound
    assert len(hits) == 100
    assert all(len(h.ciks[0]) == 10 for h in hits)


def test_fetch_theme_hits_paginates_and_dedupes_filings(efts: requests_mock.Mocker) -> None:
    hits = fetch_theme_hits(THEME, D(2025, 1, 1), D(2025, 3, 31), pause=0)
    assert efts.call_count == 2
    assert efts.request_history[1].qs["from"] == ["100"]
    assert len(hits.hits) == 155
    assert hits.filings() == len({h.adsh for h in hits.hits})
    assert hits.filings() < 155  # exhibits of the same filing collapse
    assert hits.quarter_end == D(2025, 3, 31)
    assert not hits.truncated
    per_cik = hits.filings_per_cik()
    assert sum(per_cik.values()) >= hits.filings()


def test_ticker_signals_and_market_series(efts: requests_mock.Mocker) -> None:
    hits = fetch_theme_hits(THEME, D(2025, 1, 1), D(2025, 3, 31), pause=0)
    mapper = FakeMapper()
    cik_symbols = {cik: tuple(sorted(t)) for cik, t in mapper.cik_to_tickers.items()}
    signals = ticker_signals(hits, cik_symbols, D(2026, 10, 23), symbols={"AMD", "NOTAFILER"})
    by_symbol = {s.symbol: s for s in signals}
    assert set(by_symbol) == {"AMD", "NOTAFILER"}
    assert by_symbol["AMD"].value >= 1
    assert by_symbol["NOTAFILER"].value == 0  # explicit zero for a requested symbol
    assert by_symbol["AMD"].signal == "THEME_MENTIONS:ai_accelerator"
    assert by_symbol["AMD"].date == D(2025, 3, 31)

    everyone = ticker_signals(hits, cik_symbols, D(2026, 10, 23))
    assert len(everyone) > 20

    observation = theme_filings_observation(THEME, hits, D(2026, 10, 23))
    assert observation.series_id == theme_filings_series(THEME).series_id == "THEME_FILINGS.AI_ACCELERATOR"
    assert observation.date == D(2025, 1, 1)
    assert observation.value == hits.filings()


def test_truncated_quarter_falls_back_to_reported_total() -> None:
    hits = FilingHits(theme="x", quarter_end=D(2025, 3, 31), total_documents=12_345, truncated=True)
    assert hits.filings() == 12_345


def test_fetch_theme_mentions_end_to_end(efts: requests_mock.Mocker) -> None:
    signals, observations = fetch_theme_mentions(
        [THEME], D(2024, 1, 1), D(2024, 3, 31), symbols=["AMD", "NVDA"], pause=0, mapper=FakeMapper()
    )
    assert {s.symbol for s in signals} == {"AMD", "NVDA"}
    assert [o.date for o in observations] == [D(2024, 1, 1)]


def test_hitless_body_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(edgar_themes, "_search", edgar_themes._search.retry_with(wait=wait_none()))
    with requests_mock.Mocker() as req:
        req.get(
            re.compile(re.escape(EFTS_URL) + ".*"),
            [{"json": {"error": "busy"}}, {"json": _fixture("ai_accelerator_2024q1_from0.json")}],
        )
        hits = fetch_theme_hits(THEME, D(2024, 1, 1), D(2024, 3, 31), pause=0)
    assert req.call_count == 2
    assert len(hits.hits) == 85


@pytest.mark.network
def test_fetch_theme_hits_live() -> None:
    hits = fetch_theme_hits(THEMES["hbm"], D(2025, 1, 1), D(2025, 3, 31))
    assert hits.filings() > 0


def test_write_theme_mentions_pipeline(
    efts: requests_mock.Mocker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from bearish.database.crud import BearishDb
    from bearish.macro.models import MacroQuery
    from bearish.signals.pipelines.early_winners import write_theme_mentions

    monkeypatch.setattr(edgar_themes, "StockMapper", FakeMapper)
    db = BearishDb(database_path=tmp_path / "themes.db")
    counts = write_theme_mentions(
        db, symbols=["AMD", "NVDA"], themes=["ai_accelerator"], start=D(2024, 1, 1), end=D(2024, 3, 31)
    )
    assert counts == {"ticker_signals": 2, "observations": 1}
    assert {s.symbol for s in db.read_ticker_signals(signal_prefix="THEME_MENTIONS:")} == {"AMD", "NVDA"}
    assert db.read_observations(MacroQuery(concepts=["THEME_FILINGS"]))[0].date == D(2024, 1, 1)
