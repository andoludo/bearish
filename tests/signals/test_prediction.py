import datetime
import json
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.signals.sources.prediction import (
    ELECTION_QUERIES,
    GEOPOLITICS_QUERIES,
    KALSHI_URL,
    POLYMARKET_URL,
    PredictionClient,
    PredictionQuery,
    fetch_prediction_quotes,
)

DATA_DIR = Path(__file__).parents[1] / "data" / "signals" / "prediction"
TODAY = datetime.date(2026, 10, 23)


def _load(name: str) -> object:
    return json.loads((DATA_DIR / name).read_text())


def test_polymarket_multi_candidate_event_gives_one_quote_per_candidate() -> None:
    query = ELECTION_QUERIES[0]
    quotes = PredictionClient.polymarket_quotes(_load("polymarket_event_house.json"), query, TODAY)  # type: ignore[arg-type]
    by_outcome = {q.outcome: q for q in quotes}
    assert set(by_outcome) == {"Democratic Party", "Republican Party"}  # inactive placeholder markets dropped
    assert by_outcome["Democratic Party"].probability == pytest.approx(0.915)
    assert by_outcome["Democratic Party"].category == "election"
    assert by_outcome["Democratic Party"].tags == "midterm,2026"
    assert by_outcome["Democratic Party"].url.endswith("which-party-will-win-the-house-in-2026")
    assert by_outcome["Democratic Party"].end_date == datetime.date(2026, 11, 4)


def test_polymarket_search_filters_titles_and_volume() -> None:
    query = PredictionQuery(
        platform="Polymarket",
        category="geopolitics",
        tags="conflict,CHN,TWN",
        keywords=("Taiwan",),
        exclude=r"election|mayor|magistrate",
        min_volume=100_000,
    )
    events = _load("polymarket_search_taiwan.json")["events"]  # type: ignore[index]
    quotes = PredictionClient.polymarket_quotes(events, query, TODAY)
    questions = {q.question for q in quotes}
    assert "China x Taiwan military clash before 2027?" in questions
    assert not any(re.search("Mayor|Election", q) for q in questions)
    assert all(q.outcome == "Yes" for q in quotes)  # single binary markets
    assert all(0 <= q.probability <= 1 for q in quotes)


def test_kalshi_quotes_use_dollar_prices_and_title_filter() -> None:
    query = ELECTION_QUERIES[2]
    quotes = PredictionClient.kalshi_quotes(_load("kalshi_events_controlh.json")["events"], query, TODAY)  # type: ignore[index]
    by_id = {q.market_id: q for q in quotes}
    assert set(by_id) == {"CONTROLH-2026-D", "CONTROLH-2026-R"}  # 2028 event filtered by include=2026
    assert by_id["CONTROLH-2026-D"].probability == pytest.approx(0.914)
    assert by_id["CONTROLH-2026-D"].outcome == "Democratic Party"
    assert by_id["CONTROLH-2026-D"].volume_usd == pytest.approx(21565799.37)


def test_fetch_prediction_quotes_end_to_end_with_rate_limit_retry() -> None:
    queries = [
        ELECTION_QUERIES[0],
        PredictionQuery(
            platform="Kalshi", category="geopolitics", tags="conflict,hormuz", keywords=("Hormuz",), min_volume=1_000
        ),
    ]
    with requests_mock.Mocker() as req:
        req.get(f"{POLYMARKET_URL}/events", json=_load("polymarket_event_house.json"))
        req.get(f"{KALSHI_URL}/series", json=_load("kalshi_series_politics.json"))
        req.get(
            f"{KALSHI_URL}/events",
            [{"status_code": 429, "headers": {"Retry-After": "0"}}, {"json": _load("kalshi_events_hormuz.json")}],
        )
        quotes = fetch_prediction_quotes(queries, pause=0, as_of=TODAY)
    platforms = {q.platform for q in quotes}
    assert platforms == {"Polymarket", "Kalshi"}
    hormuz = [q for q in quotes if q.platform == "Kalshi"]
    assert hormuz and all(q.tags == "conflict,hormuz" and q.as_of == TODAY for q in hormuz)
    assert len({(q.platform, q.market_id, q.outcome) for q in quotes}) == len(quotes)


def test_default_query_sets() -> None:
    assert {q.platform for q in ELECTION_QUERIES} == {"Polymarket", "Kalshi"}
    keywords = {k for q in GEOPOLITICS_QUERIES for k in q.keywords}
    assert {"Taiwan", "Iran", "Strait of Hormuz", "North Korea", "tariff"} <= keywords


@pytest.mark.network
def test_prediction_quotes_live() -> None:
    quotes = fetch_prediction_quotes(ELECTION_QUERIES[:1], pause=0.5)
    assert any("House" in q.question for q in quotes)
