import datetime
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests_mock

from bearish.macro.catalog import select_series, series_by_id
from bearish.macro.models import MacroQuery
from bearish.macro.sources.adoption import (
    ARXIV_URL,
    ArxivSource,
    EdgarThemeSource,
    month_end,
    month_starts,
    parse_total_results,
)
from bearish.signals.sources.edgar_themes import EFTS_URL

DATA = Path(__file__).parents[1] / "data"
D = datetime.date
FEED = (DATA / "macro" / "adoption" / "arxiv_quantum_202601.xml").read_text()


class FixedDayArxiv(ArxivSource):
    @staticmethod
    def today() -> datetime.date:
        return D(2026, 2, 15)


class FixedDayEdgar(EdgarThemeSource):
    @staticmethod
    def today() -> datetime.date:
        return D(2025, 3, 31)


def test_month_helpers_and_count_parsing() -> None:
    assert month_starts(D(2025, 11, 20), D(2026, 2, 1)) == [
        D(2025, 11, 1),
        D(2025, 12, 1),
        D(2026, 1, 1),
        D(2026, 2, 1),
    ]
    assert month_end(D(2024, 2, 1)) == D(2024, 2, 29)
    assert parse_total_results(FEED) == 246
    with pytest.raises(ValueError):
        parse_total_results("<feed/>")


def test_catalog_has_adoption_series() -> None:
    papers = select_series(MacroQuery(concepts=["ADOPTION_PAPERS"]))
    assert {s.entity for s in papers} >= {"QUANTUM", "HBM", "AI_ACCELERATOR"}
    assert "ADOPTION_PAPERS.GLP1" not in series_by_id()  # no arXiv phrases for GLP-1
    filings = select_series(MacroQuery(concepts=["THEME_FILINGS"]))
    assert len(filings) == 12
    assert all(s.entity_type == "theme" and s.source == "EDGAR" for s in filings)


def test_arxiv_source_one_call_per_month() -> None:
    entry = series_by_id()["ADOPTION_PAPERS.QUANTUM"]
    with requests_mock.Mocker() as req:
        req.get(re.compile(re.escape(ARXIV_URL) + ".*"), text=FEED)
        observations = FixedDayArxiv(pause=0).read_observations([entry], start=D(2026, 1, 1))
    assert req.call_count == 2
    query = req.request_history[0].qs["search_query"][0]
    assert 'abs:"quantum computing"' in query
    assert "submitteddate:[202601010000 to 202601312359]" in query  # requests_mock lower-cases query values
    assert [(o.date, o.value) for o in observations] == [(D(2026, 1, 1), 246.0), (D(2026, 2, 1), 246.0)]


def test_edgar_theme_source_counts_filings_per_quarter() -> None:
    entry = series_by_id()["THEME_FILINGS.AI_ACCELERATOR"]

    def respond(request, context):  # type: ignore[no-untyped-def]
        offset = int(parse_qs(urlparse(request.url).query).get("from", ["0"])[0])
        return json.loads((DATA / "signals" / "edgar_themes" / f"ai_accelerator_2025q1_from{offset}.json").read_text())

    with requests_mock.Mocker() as req:
        req.get(re.compile(re.escape(EFTS_URL) + ".*"), json=respond)
        observations = FixedDayEdgar(pause=0).read_observations([entry], start=D(2025, 1, 1))
    assert len(observations) == 1
    assert observations[0].date == D(2025, 1, 1)
    assert 50 < observations[0].value < 155


@pytest.mark.network
def test_arxiv_live() -> None:
    entry = series_by_id()["ADOPTION_PAPERS.QUANTUM"]
    first = datetime.date.today().replace(day=1) - datetime.timedelta(days=40)
    observations = ArxivSource().read_observations([entry], start=first)
    assert observations and observations[0].value > 0
