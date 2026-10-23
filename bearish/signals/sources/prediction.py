"""Prediction-market probabilities from Polymarket and Kalshi (keyless, read only).

Polymarket (gamma API): an *event* groups markets. Multi-candidate events
(e.g. "Which party will win the House in 2026?") hold one Yes/No market per
candidate; the Yes price is that candidate's implied probability and the
candidate name is ``groupItemTitle``. Single binary events give one Yes
quote. ``outcomes`` / ``outcomePrices`` are JSON-encoded strings.

Kalshi (trade API v2): *series* (e.g. ``CONTROLH``) contain *events*
(``CONTROLH-2026``) whose *markets* are Yes contracts per outcome. Prices
come as dollar strings (``last_price_dollars``) or, on older payloads, cents
(``last_price``); volume is in contracts (``volume_fp``), i.e. USD at $1 face.

A ``PredictionQuery`` selects events by Polymarket slug, Kalshi series
ticker, or keywords (Polymarket search; Kalshi series-title match within a
set of categories), then filters titles with ``include`` / ``exclude``
regexes and a minimum traded volume. Each snapshot is stored with
``as_of = today`` so repeated runs build a probability history.
"""

import datetime
import json
import logging
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from pydantic import BaseModel, ConfigDict, Field

from bearish.signals.models import PredictionPlatform, PredictionQuote

logger = logging.getLogger(__name__)

POLYMARKET_URL = "https://gamma-api.polymarket.com"
KALSHI_URL = "https://api.elections.kalshi.com/trade-api/v2"
HEADERS = {"User-Agent": "bearish (https://github.com/andoludo/bearish)", "Accept": "application/json"}
KALSHI_CATEGORIES = ("Politics", "World", "Elections", "Economics")


class PredictionQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    platform: PredictionPlatform
    category: str
    tags: str = ""
    event_slugs: Tuple[str, ...] = Field(default=(), description="Polymarket event slugs")
    series_tickers: Tuple[str, ...] = Field(default=(), description="Kalshi series tickers")
    keywords: Tuple[str, ...] = Field(default=(), description="Polymarket search terms / Kalshi series title terms")
    include: Optional[str] = Field(default=None, description="Regex an event title must match")
    exclude: Optional[str] = Field(default=None, description="Regex an event title must not match")
    min_volume: float = 10_000.0
    max_events: int = 20


_GEO_EXCLUDE = (
    r"election|mayor|magistrate|seats|league|\bgame\b|\bcup\b|eurovision|parliament|governor|primary|nominee|super bowl"
)

ELECTION_QUERIES: Tuple[PredictionQuery, ...] = (
    PredictionQuery(
        platform="Polymarket",
        category="election",
        tags="midterm,2026",
        event_slugs=(
            "which-party-will-win-the-house-in-2026",
            "which-party-will-win-the-senate-in-2026",
            "balance-of-power-2026-midterms",
        ),
        min_volume=100_000,
    ),
    PredictionQuery(
        platform="Polymarket",
        category="election",
        tags="midterm,2026",
        keywords=("2026 midterms",),
        include=r"2026|midterm",
        exclude=r"turnout|governor",
        min_volume=250_000,
        max_events=10,
    ),
    PredictionQuery(
        platform="Kalshi",
        category="election",
        tags="midterm,2026",
        series_tickers=("CONTROLH", "CONTROLS"),
        include=r"2026",
        min_volume=100_000,
    ),
)

_GEOPOLITICS: Tuple[Tuple[str, str], ...] = (
    ("Taiwan", "conflict,CHN,TWN"),
    ("China invade", "conflict,CHN,TWN"),
    ("Iran", "conflict,IRN"),
    ("Israel", "conflict,ISR"),
    ("ceasefire", "conflict,ceasefire"),
    ("Ukraine", "conflict,UKR,RUS"),
    ("Russia", "conflict,RUS"),
    ("Strait of Hormuz", "conflict,chokepoint,hormuz"),
    ("North Korea", "conflict,PRK"),
    ("sanctions", "sanctions"),
    ("tariff", "trade,tariff"),
)

GEOPOLITICS_QUERIES: Tuple[PredictionQuery, ...] = tuple(
    query
    for keyword, tags in _GEOPOLITICS
    for query in (
        PredictionQuery(
            platform="Polymarket",
            category="geopolitics",
            tags=tags,
            keywords=(keyword,),
            exclude=_GEO_EXCLUDE,
            min_volume=50_000,
            max_events=10,
        ),
        PredictionQuery(
            platform="Kalshi",
            category="geopolitics",
            tags=tags,
            keywords=(keyword,),
            exclude=_GEO_EXCLUDE,
            min_volume=10_000,
            max_events=10,
        ),
    )
)


def _date(value: Any) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _float(value: Any) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _json_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _title_ok(title: str, query: PredictionQuery) -> bool:
    if query.include and not re.search(query.include, title, re.IGNORECASE):
        return False
    return not (query.exclude and re.search(query.exclude, title, re.IGNORECASE))


class PredictionClient(BaseModel):
    """Polite HTTP access to both platforms; one instance per fetch run."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pause: float = 0.5
    timeout: int = 60
    retries: int = 4
    calls: int = 0
    kalshi_series_cache: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """GET with a pause between calls and exponential backoff on HTTP 429."""
        for attempt in range(self.retries + 1):
            if self.calls:
                time.sleep(self.pause)
            self.calls += 1
            response = requests.get(url, params=params, headers=HEADERS, timeout=self.timeout)
            if response.status_code == 429 and attempt < self.retries:  # noqa: PLR2004
                retry_after = _float(response.headers.get("Retry-After"))
                wait = retry_after if retry_after is not None else 2.0 * 2**attempt
                logger.debug(f"Rate limited by {url}; retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        return None

    # Polymarket ------------------------------------------------------------

    def polymarket_events(self, query: PredictionQuery) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for slug in query.event_slugs:
            events.extend(self.get(f"{POLYMARKET_URL}/events", params={"slug": slug}) or [])  # list payload
        for keyword in query.keywords:
            payload = self.get(
                f"{POLYMARKET_URL}/public-search",
                params={"q": keyword, "limit_per_type": max(query.max_events * 2, 10), "events_status": "active"},
            )
            events.extend((payload or {}).get("events") or [])
        return events

    @staticmethod
    def polymarket_quotes(
        events: Iterable[Dict[str, Any]], query: PredictionQuery, as_of: datetime.date
    ) -> List[PredictionQuote]:
        quotes: List[PredictionQuote] = []
        seen: set[str] = set()
        kept = 0
        for event in events:
            title = str(event.get("title") or "")
            volume = _float(event.get("volume")) or 0.0
            if event.get("closed") or not event.get("active", True) or volume < query.min_volume:
                continue
            if not _title_ok(title, query) or event.get("slug") in seen:
                continue
            seen.add(str(event.get("slug")))
            kept += 1
            if kept > query.max_events:
                break
            markets = event.get("markets") or []
            for market in markets:
                prices = [_float(p) for p in _json_list(market.get("outcomePrices"))]
                outcomes = [str(o) for o in _json_list(market.get("outcomes"))]
                if market.get("closed") or not market.get("active", True) or not prices or None in prices:
                    continue
                pairs: List[Tuple[str, float]]
                if outcomes[:2] == ["Yes", "No"]:
                    label = str(market.get("groupItemTitle") or "") if len(markets) > 1 else ""
                    pairs = [(label or "Yes", prices[0] or 0.0)]
                else:
                    pairs = [(name, price or 0.0) for name, price in zip(outcomes, prices, strict=False)]
                for outcome, probability in pairs:
                    if not 0.0 <= probability <= 1.0:
                        continue
                    quotes.append(
                        PredictionQuote(
                            platform="Polymarket",
                            market_id=str(market.get("id")),
                            outcome=outcome,
                            as_of=as_of,
                            question=str(market.get("question") or title),
                            category=query.category,
                            probability=probability,
                            volume_usd=_float(market.get("volume")),
                            end_date=_date(market.get("endDate") or event.get("endDate")),
                            url=f"https://polymarket.com/event/{event.get('slug')}",
                            tags=query.tags,
                        )
                    )
        return quotes

    # Kalshi ----------------------------------------------------------------

    def kalshi_series_matching(self, keywords: Sequence[str], query: PredictionQuery) -> List[str]:
        tickers: List[str] = []
        for category in KALSHI_CATEGORIES:
            if category not in self.kalshi_series_cache:
                payload = self.get(f"{KALSHI_URL}/series", params={"category": category})
                self.kalshi_series_cache[category] = (payload or {}).get("series") or []
            for series in self.kalshi_series_cache[category]:
                title = str(series.get("title") or "")
                matched = any(re.search(rf"\b{re.escape(k)}", title, re.IGNORECASE) for k in keywords)
                if matched and _title_ok(title, query):
                    tickers.append(str(series["ticker"]))
        return list(dict.fromkeys(tickers))[: query.max_events]

    def kalshi_events(self, query: PredictionQuery) -> List[Dict[str, Any]]:
        tickers = list(query.series_tickers)
        if query.keywords:
            tickers += self.kalshi_series_matching(query.keywords, query)
        events: List[Dict[str, Any]] = []
        for ticker in dict.fromkeys(tickers):
            try:
                payload = self.get(
                    f"{KALSHI_URL}/events",
                    params={"series_ticker": ticker, "status": "open", "with_nested_markets": "true", "limit": 50},
                )
            except requests.RequestException as e:
                logger.warning(f"Kalshi series {ticker} failed: {e}")
                continue
            events.extend((payload or {}).get("events") or [])
        return events

    @staticmethod
    def _kalshi_price(market: Dict[str, Any]) -> Optional[float]:
        for field in ("last_price_dollars", "yes_bid_dollars"):
            price = _float(market.get(field))
            if price is not None and price > 0:
                return price
        cents = _float(market.get("last_price")) or _float(market.get("yes_bid"))
        return cents / 100.0 if cents is not None else None

    @classmethod
    def kalshi_quotes(
        cls, events: Iterable[Dict[str, Any]], query: PredictionQuery, as_of: datetime.date
    ) -> List[PredictionQuote]:
        quotes: List[PredictionQuote] = []
        kept = 0
        for event in events:
            label = " ".join(str(event.get(k) or "") for k in ("title", "sub_title", "event_ticker"))
            markets = [m for m in event.get("markets") or [] if m.get("status") in ("active", "open")]
            volume = sum((_float(m.get("volume_fp")) or _float(m.get("volume")) or 0.0) for m in markets)
            if not markets or volume < query.min_volume or not _title_ok(label, query):
                continue
            kept += 1
            if kept > query.max_events:
                break
            for market in markets:
                probability = cls._kalshi_price(market)
                if probability is None or not 0.0 <= probability <= 1.0:
                    continue
                quotes.append(
                    PredictionQuote(
                        platform="Kalshi",
                        market_id=str(market.get("ticker")),
                        outcome=str(market.get("yes_sub_title") or market.get("title") or "Yes"),
                        as_of=as_of,
                        question=str(market.get("title") or event.get("title")),
                        category=query.category,
                        probability=probability,
                        volume_usd=_float(market.get("volume_fp")) or _float(market.get("volume")),
                        end_date=_date(market.get("close_time")),
                        url=f"https://kalshi.com/markets/{str(event.get('series_ticker') or '').lower()}",
                        tags=query.tags,
                    )
                )
        return quotes


def fetch_prediction_quotes(
    queries: Sequence[PredictionQuery] = ELECTION_QUERIES + GEOPOLITICS_QUERIES,
    pause: float = 1.0,
    as_of: Optional[datetime.date] = None,
) -> List[PredictionQuote]:
    """Current implied probabilities for every market the queries select (one row per outcome)."""
    as_of = as_of or datetime.date.today()
    client = PredictionClient(pause=pause)
    quotes: Dict[Tuple[str, str, str], PredictionQuote] = {}
    for query in queries:
        try:
            if query.platform == "Polymarket":
                rows = client.polymarket_quotes(client.polymarket_events(query), query, as_of)
            else:
                rows = client.kalshi_quotes(client.kalshi_events(query), query, as_of)
        except requests.RequestException as e:
            logger.warning(
                f"{query.platform} query {query.keywords or query.event_slugs or query.series_tickers} failed: {e}"
            )
            continue
        for row in rows:
            quotes.setdefault((row.platform, row.market_id, row.outcome), row)
    return list(quotes.values())
