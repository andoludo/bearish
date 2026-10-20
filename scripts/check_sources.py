"""Probe every data source against its live API and print a PASS/FAIL summary.

Run in an environment with direct internet access (e.g. a CI runner):

    uv run python scripts/check_sources.py

Key-based sources (Tiingo) are only probed when their API key is present
in the environment (TIINGO_API_KEY); otherwise they are SKIPPED.
The script always exits 0 — it reports, the caller decides.
"""

import json
import os
import traceback
from datetime import date, timedelta
from typing import Callable, Dict

RESULTS: Dict[str, str] = {}


def probe(name: str, condition: bool = True) -> Callable[[Callable[[], str]], None]:
    def runner(func: Callable[[], str]) -> None:
        if not condition:
            RESULTS[name] = "SKIP (no API key)"
            return
        try:
            detail = func()
            RESULTS[name] = f"PASS ({detail})"
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            RESULTS[name] = f"FAIL ({type(exc).__name__}: {exc})"

    return runner


@probe("FinanceDatabase")
def _finance_database() -> str:
    import requests

    from bearish.sources.financedatabase import RAW_EQUITIES_DATA_URL

    response = requests.head(RAW_EQUITIES_DATA_URL, timeout=30, allow_redirects=True)
    response.raise_for_status()
    return f"equities dataset reachable, HTTP {response.status_code}"


@probe("InvestPy")
def _investpy() -> str:
    import requests

    from bearish.sources.investpy import RAW_EQUITIES_INVESTSPY_DATA_URL

    response = requests.head(
        RAW_EQUITIES_INVESTSPY_DATA_URL, timeout=30, allow_redirects=True
    )
    response.raise_for_status()
    return f"equities dataset reachable, HTTP {response.status_code}"


@probe("Yfinance-prices")
def _yfinance_prices() -> str:
    from bearish.sources.yfinance import yFinanceSource

    prices = yFinanceSource()._read_series(["AAPL"], "5d")
    assert prices, "no prices returned"
    return f"{len(prices)} price rows for AAPL"


@probe("Yfinance-financials")
def _yfinance_financials() -> str:
    from bearish.sources.yfinance import yFinanceSource

    financials = yFinanceSource()._read_financials(["AAPL"])
    assert financials and not financials[0].is_empty(), "no financials returned"
    return f"{len(financials[0].financial_metrics)} metric rows for AAPL"


@probe("Yfinance-assets")
def _yfinance_assets() -> str:
    from bearish.models.base import Ticker
    from bearish.models.query.query import AssetQuery, Symbols
    from bearish.sources.yfinance import yFinanceSource

    assets = yFinanceSource()._read_assets(
        AssetQuery(symbols=Symbols(equities=[Ticker(symbol="AAPL")]))
    )
    assert not assets.is_empty(), "no assets returned"
    return f"{len(assets.equities)} equities for AAPL"


@probe("YahooQuery-prices")
def _yahooquery_prices() -> str:
    from bearish.sources.yahooquery import YahooQuerySource

    prices = YahooQuerySource()._read_series(["AAPL"], "5d")
    assert prices, "no prices returned"
    return f"{len(prices)} price rows for AAPL"


@probe("YahooQuery-financials")
def _yahooquery_financials() -> str:
    from bearish.sources.yahooquery import YahooQuerySource

    financials = YahooQuerySource()._read_financials(["AAPL"])
    assert financials and not financials[0].is_empty(), "no financials returned"
    return "financials returned for AAPL"


@probe("Tiingo", condition=bool(os.environ.get("TIINGO_API_KEY")))
def _tiingo() -> str:
    from bearish.models.base import Ticker
    from bearish.sources.tiingo import TiingoSource

    source = TiingoSource()
    source.set_api_key(os.environ["TIINGO_API_KEY"])
    prices = source.read_series([Ticker(symbol="AAPL", exchange="NASDAQ")], "5d")
    assert prices, "no prices returned"
    return f"{len(prices)} price rows for AAPL"


@probe("SEC")
def _sec() -> str:
    from datetime import datetime

    from bearish.models.sec.sec import Secs

    secs = Secs.from_sec_13f_hr(
        "0001067983", date_=datetime.strptime("2024-10-01", "%Y-%m-%d").date()
    )
    assert secs.secs, "no filings parsed"
    return f"{len(secs.secs)} filings parsed"


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("SOURCE HEALTH SUMMARY")
    print("=" * 70)
    for source_name, verdict in RESULTS.items():
        print(f"{source_name:30s} {verdict}")
    print("=" * 70)
    print("::SOURCE_HEALTH_JSON::" + json.dumps(RESULTS))
