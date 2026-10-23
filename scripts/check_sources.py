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


@probe("SEC-XBRL")
def _sec_xbrl() -> str:
    from bearish.models.base import Ticker
    from bearish.sources.sec_xbrl import SecXbrlSource

    financials = SecXbrlSource().read_financials([Ticker(symbol="AAPL", exchange="NMS")])
    assert financials and financials[0].financial_metrics, "no XBRL statements returned"
    latest = financials[0].financial_metrics[-1]
    return f"{len(financials[0].financial_metrics)} annual rows for AAPL, latest filed {latest.filed_date}"


@probe("SEC-Form4")
def _sec_form4() -> str:
    from bearish.sources.sec_insiders import fetch_insider_transactions

    transactions = fetch_insider_transactions(["AAPL"], max_filings=2)
    assert transactions, "no Form 4 transactions parsed"
    return f"{len(transactions)} transaction lines from 2 AAPL filings"


@probe("KenFrench")
def _kenfrench() -> str:
    import datetime

    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.kenfrench import KenFrenchSource

    entries = select_series(MacroQuery(series_ids=["FF_MKT.USA", "FF_MKT.EUR"]))
    observations = KenFrenchSource().read_observations(
        entries, start=datetime.date.today() - datetime.timedelta(days=120)
    )
    assert {o.series_id for o in observations} == {"FF_MKT.USA", "FF_MKT.EUR"}, "missing factor series"
    return f"{len(observations)} factor observations"


@probe("WorldBankPinkSheet")
def _pink_sheet() -> str:
    import datetime

    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.pinksheet import PinkSheetSource

    entries = select_series(MacroQuery(entities=["BRENT", "GOLD", "COPPER"]), sources=["WorldBankPinkSheet"])
    observations = PinkSheetSource().read_observations(
        entries, start=datetime.date.today() - datetime.timedelta(days=400)
    )
    assert {o.series_id for o in observations} == {e.series_id for e in entries}, "missing Pink Sheet series"
    return f"{len(observations)} monthly price observations"


@probe("CFTC")
def _cftc() -> str:
    import datetime

    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.cftc import CftcSource

    entries = select_series(MacroQuery(entities=["WTI", "GOLD"]), sources=["CFTC"])
    observations = CftcSource().read_observations(entries, start=datetime.date.today() - datetime.timedelta(days=60))
    assert {o.series_id for o in observations} == {e.series_id for e in entries}, "missing COT series"
    return f"{len(observations)} weekly positioning observations"


@probe("Comtrade")
def _comtrade() -> str:
    import datetime

    from bearish.macro.countries import country_from
    from bearish.macro.sources.comtrade import fetch_country_exposures

    belgium = country_from("BEL")
    assert belgium is not None
    exposures = fetch_country_exposures([belgium], datetime.date.today().year - 2, pause=6)
    assert {e.direction for e in exposures} == {"export", "import"}, "missing export or import rows"
    return f"{len(exposures)} exposure rows for BEL"


@probe("ECB")
def _ecb() -> str:
    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.ecb import EcbSource

    entries = select_series(MacroQuery(series_ids=["FX_USD.EA20"]))
    observations = EcbSource().read_observations(entries, start=date.today() - timedelta(days=30))
    assert observations, "no observations returned"
    return f"{len(observations)} EUR/USD observations"


@probe("Eurostat")
def _eurostat() -> str:
    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.eurostat import EurostatSource

    entries = select_series(MacroQuery(concepts=["ESI"], entities=["FRA", "EU27"]))
    observations = EurostatSource().read_observations(entries, start=date.today() - timedelta(days=120))
    assert {o.series_id for o in observations} == {"ESI.FRA", "ESI.EU27"}, "missing ESI series"
    return f"{len(observations)} ESI observations"


@probe("EPU")
def _epu() -> str:
    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.epu import EpuSource

    observations = EpuSource().read_observations(
        select_series(MacroQuery(series_ids=["EPU.WLD", "EPU.USA"])), start=date(2025, 1, 1)
    )
    assert {o.series_id for o in observations} == {"EPU.WLD", "EPU.USA"}, "missing EPU series"
    return f"{len(observations)} EPU observations"


@probe("GPR")
def _gpr() -> str:
    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.gpr import GprSource

    observations = GprSource().read_observations(
        select_series(MacroQuery(series_ids=["GPR.WLD", "GPR.USA"])), start=date(2025, 1, 1)
    )
    assert {o.series_id for o in observations} == {"GPR.WLD", "GPR.USA"}, "missing GPR series"
    return f"{len(observations)} GPR observations"


@probe("AtlantaFed-GDPNow")
def _gdpnow() -> str:
    from bearish.macro.catalog import select_series
    from bearish.macro.sources.gdpnow import GdpNowSource

    observations = GdpNowSource().read_observations(
        select_series(sources=["AtlantaFed"]), start=date.today() - timedelta(days=120)
    )
    assert observations, "no nowcast observations returned"
    return f"{len(observations)} nowcast dates, latest {observations[-1].value:.2f}"


@probe("IMF")
def _imf() -> str:

    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.imf import ImfSource

    entries = select_series(MacroQuery(concepts=["GDP_FCST"], entities=["USA", "WLD"]))
    observations = ImfSource().read_observations(entries, start=date(date.today().year - 2, 1, 1))
    assert {o.series_id for o in observations} == {"GDP_FCST.USA", "GDP_FCST.WLD"}, "missing series"
    return f"{len(observations)} WEO observations"


@probe("WorldBank")
def _worldbank() -> str:

    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.worldbank import WorldBankSource

    entries = select_series(MacroQuery(concepts=["TRADE_GDP"], entities=["FRA", "CHN"]))
    observations = WorldBankSource().read_observations(entries, start=date(date.today().year - 5, 1, 1))
    assert {o.series_id for o in observations} == {"TRADE_GDP.FRA", "TRADE_GDP.CHN"}, "missing series"
    return f"{len(observations)} WDI observations"


@probe("BIS")
def _bis() -> str:

    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.bis import BisSource

    entries = select_series(MacroQuery(concepts=["POLICY_RATE", "REER"], entities=["USA", "EA20"]))
    observations = BisSource().read_observations(entries, start=date.today() - timedelta(days=180))
    assert {o.series_id for o in observations} == {s.series_id for s in entries}, "missing series"
    return f"{len(observations)} BIS observations"


@probe("DBnomics")
def _dbnomics() -> str:

    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.dbnomics import DbnomicsSource

    entries = select_series(MacroQuery(concepts=["UNEMP_RATE"], entities=["CHN", "BRA"]), sources=["DBnomics"])
    observations = DbnomicsSource().read_observations(entries, start=date(date.today().year - 3, 1, 1))
    assert {o.series_id for o in observations} == {s.series_id for s in entries}, "missing series"
    return f"{len(observations)} DBnomics observations"


@probe("SEC-13DG")
def _sec_13dg() -> str:
    from bearish.sources.sec_ownership import fetch_ownership

    rows = fetch_ownership(["AAPL"], max_filings=2)
    assert rows, "no Schedule 13D/13G rows parsed"
    return f"{len(rows)} reporting persons from 2 filings for AAPL"


@probe("PortWatch")
def _portwatch() -> str:
    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.portwatch import PortWatchSource

    entries = select_series(MacroQuery(series_ids=["TRANSITS.SUEZ", "TRANSITS_TANKER.HORMUZ"]))
    observations = PortWatchSource().read_observations(entries, start=date.today() - timedelta(days=30))
    assert observations, "no chokepoint transits returned"
    return f"{len(observations)} transit observations, latest {max(o.date for o in observations)}"


@probe("GDELT")
def _gdelt() -> str:
    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.gdelt import GdeltSource

    entries = select_series(MacroQuery(series_ids=["GDELT_CONFLICT_EVENTS.RUS_UKR"]))
    observations = GdeltSource(backfill_days=2).read_observations(entries)
    assert observations, "no GDELT daily file parsed"
    return f"RUS_UKR material-conflict events on {observations[-1].date}: {observations[-1].value:.0f}"


@probe("OFAC")
def _ofac() -> str:
    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.ofac import OfacSource

    entries = select_series(MacroQuery(series_ids=["SANCTIONS_NEW.WLD"]))
    observations = OfacSource().read_observations(entries, start=date.today() - timedelta(days=400))
    assert observations, "no SDN designations parsed"
    return f"{sum(o.value for o in observations):.0f} designations in the last 13 months"


@probe("SIPRI")
def _sipri() -> str:
    from bearish.macro.catalog import select_series
    from bearish.macro.models import MacroQuery
    from bearish.macro.sources.sipri import SipriSource

    entries = select_series(MacroQuery(series_ids=["MILEX_USD.WLD"]))
    observations = SipriSource().read_observations(entries)
    assert observations, "no SIPRI world total parsed"
    return f"world military spending {observations[-1].date.year}: US$ {observations[-1].value / 1e6:.2f} tn"


@probe("EDGAR-themes")
def _edgar_themes() -> str:
    from bearish.signals.sources.edgar_themes import fetch_theme_hits
    from bearish.signals.themes import THEMES

    end = date.today()
    hits = fetch_theme_hits(THEMES["hbm"], end - timedelta(days=90), end)
    assert hits.filings() > 0, "no filings mention the theme"
    return f"{hits.filings()} filings mention HBM in the last 90 days"


@probe("FINRA-short-interest")
def _finra_short_interest() -> str:
    from bearish.signals.sources.finra import fetch_short_interest

    signals = fetch_short_interest(["NVDA"], date.today() - timedelta(days=60))
    assert signals, "no short-interest rows"
    return f"{len(signals)} short-interest signals for NVDA"


@probe("FINRA-short-volume")
def _finra_short_volume() -> str:
    from bearish.signals.sources.finra import fetch_short_volume

    signals = fetch_short_volume(days=7, symbols=["NVDA"])
    assert signals, "no short-volume file in the last 7 days"
    return f"{len(signals)} daily short-volume ratios for NVDA"


@probe("USAspending")
def _usaspending() -> str:
    from bearish.signals.sources.usaspending import fetch_federal_awards

    start = date.today() - timedelta(days=200)
    signals = fetch_federal_awards({"PLTR": "Palantir Technologies Inc."}, start)
    assert signals, "no quarters returned"
    return f"{len(signals)} quarters of awards for PLTR"


@probe("arXiv")
def _arxiv() -> str:
    from bearish.macro.catalog import series_by_id
    from bearish.macro.sources.adoption import ArxivSource

    start = date.today().replace(day=1) - timedelta(days=40)
    observations = ArxivSource().read_observations([series_by_id()["ADOPTION_PAPERS.QUANTUM"]], start=start)
    assert observations, "no arXiv counts"
    return f"{len(observations)} monthly counts, latest {observations[-1].value:.0f} papers"


@probe("Congress-party-divisions")
def _party_divisions() -> str:
    import requests

    from bearish.signals.elections import (
        CONGRESS_CONTROL,
        HOUSE_DIVISIONS_URL,
        SENATE_DIVISIONS_URL,
        parse_house_divisions,
        parse_senate_divisions,
    )

    headers = {"User-Agent": "bearish (https://github.com/andoludo/bearish)"}
    house = parse_house_divisions(requests.get(HOUSE_DIVISIONS_URL, headers=headers, timeout=60).text)
    senate = parse_senate_divisions(requests.get(SENATE_DIVISIONS_URL, headers=headers, timeout=60).text)
    house_diff = [c for c, (h, _) in CONGRESS_CONTROL.items() if house.get(c) != h]
    senate_diff = [c for c, (_, s) in CONGRESS_CONTROL.items() if senate.get(c) != s and c != 107]
    assert not house_diff and not senate_diff, f"curated table differs: house {house_diff}, senate {senate_diff}"
    return f"{len(house)} Congresses parsed, curated table matches"


@probe("FOMC-calendar")
def _fomc() -> str:
    from bearish.signals.fomc import fetch_fomc_meetings

    events = fetch_fomc_meetings(start_year=date.today().year - 1, pause=0.5)
    assert events, "no meetings parsed"
    upcoming = [e for e in events if "upcoming" in e.tag_set()]
    return f"{len(events)} meetings, next {upcoming[0].date if upcoming else 'n/a'}"


@probe("Polymarket")
def _polymarket() -> str:
    from bearish.signals.sources.prediction import ELECTION_QUERIES, fetch_prediction_quotes

    quotes = fetch_prediction_quotes([q for q in ELECTION_QUERIES if q.platform == "Polymarket"][:1], pause=0.5)
    assert quotes, "no Polymarket quotes"
    return f"{len(quotes)} outcome quotes"


@probe("Kalshi")
def _kalshi() -> str:
    from bearish.signals.sources.prediction import ELECTION_QUERIES, fetch_prediction_quotes

    quotes = fetch_prediction_quotes([q for q in ELECTION_QUERIES if q.platform == "Kalshi"], pause=1.0)
    assert quotes, "no Kalshi quotes"
    return f"{len(quotes)} outcome quotes"


@probe("House-PTR")
def _house_ptr() -> str:
    from bearish.signals.sources.congress import fetch_house_trades

    result = fetch_house_trades(date.today().year, max_filings=3, pause=0.5)
    assert result.filings, "no PTR filings listed"
    return f"{result.parsed}/{result.filings} PTRs parsed, {len(result.trades)} trades, {result.scanned} scanned"


@probe("LDA-lobbying")
def _lobbying() -> str:
    from bearish.signals.sources.lobbying import fetch_lobbying

    signals = fetch_lobbying(["LMT"], [date.today().year - 1], names={"LMT": "Lockheed Martin Corp"}, pause=1.0)
    assert signals, "no lobbying quarters"
    return f"{len(signals)} quarters for LMT"


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("SOURCE HEALTH SUMMARY")
    print("=" * 70)
    for source_name, verdict in RESULTS.items():
        print(f"{source_name:30s} {verdict}")
    print("=" * 70)
    print("::SOURCE_HEALTH_JSON::" + json.dumps(RESULTS))
