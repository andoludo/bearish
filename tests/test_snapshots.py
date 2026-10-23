import datetime
from pathlib import Path

from bearish.database.crud import BearishDb
from bearish.models.assets.assets import Assets
from bearish.models.assets.equity import Equity
from bearish.models.assets.etfs import Etf
from bearish.models.assets.snapshots import EquitySnapshot, EtfSnapshot, Snapshots

AS_OF = datetime.date(2026, 10, 23)


def _equity(**values: object) -> Equity:
    return Equity.model_validate({"symbol": "NVDA", "source": "Yfinance", "name": "NVIDIA", **values})


def _etf(**values: object) -> Etf:
    return Etf.model_validate({"symbol": "SPY", "source": "Yfinance", "name": "SPDR S&P 500", **values})


def test_snapshots_only_for_assets_with_values() -> None:
    assets = Assets(
        equities=[_equity(), _equity(short_shares=1_000.0, market_capitalization=2e12)],
        etfs=[_etf(), _etf(total_net_assets=5e11, nav_price=600.0, holding_percent={"AAPL": 0.07})],
    )
    snapshots = Snapshots.from_assets(assets, AS_OF)
    assert len(snapshots.equities) == 1
    assert len(snapshots.etfs) == 1
    equity = snapshots.equities[0]
    assert (equity.symbol, equity.source, equity.as_of) == ("NVDA", "Yfinance", AS_OF)
    assert equity.short_shares == 1_000.0
    assert equity.market_capitalization == 2e12
    assert equity.price_to_book is None
    etf = snapshots.etfs[0]
    assert etf.total_net_assets == 5e11
    assert etf.holding_percent == {"AAPL": 0.07}


def test_base_ticker_sources_produce_no_snapshots() -> None:
    base_only = Assets(equities=[_equity(sector="Technology", country="United states")], etfs=[_etf(category="Large Blend")])
    assert Snapshots.from_assets(base_only, AS_OF).is_empty()


def test_snapshot_defaults_to_today() -> None:
    assert EquitySnapshot.from_equity(_equity(short_shares=1.0)).as_of == datetime.date.today()
    assert EtfSnapshot.from_etf(_etf(nav_price=1.0)).as_of == datetime.date.today()


def test_snapshots_roundtrip_and_upsert(tmp_path: Path) -> None:
    db = BearishDb(database_path=tmp_path / "s.db")
    first = Snapshots(
        equities=[EquitySnapshot(symbol="NVDA", source="Yfinance", as_of=AS_OF, short_shares=100.0)],
        etfs=[EtfSnapshot(symbol="SPY", source="Yfinance", as_of=AS_OF, total_net_assets=1.0, sector_weightings={"technology": 0.3})],
    )
    db.write_snapshots(first)
    # same day again: the row is replaced, not duplicated
    db.write_snapshots(
        Snapshots(equities=[EquitySnapshot(symbol="NVDA", source="Yfinance", as_of=AS_OF, short_shares=120.0)])
    )
    # next day: a new row, so a history accumulates
    next_day = AS_OF + datetime.timedelta(days=1)
    db.write_snapshots(
        Snapshots(equities=[EquitySnapshot(symbol="NVDA", source="Yfinance", as_of=next_day, short_shares=130.0)])
    )

    equities = sorted(db.read_equity_snapshots("NVDA"), key=lambda s: s.as_of)
    assert [(s.as_of, s.short_shares) for s in equities] == [(AS_OF, 120.0), (next_day, 130.0)]
    assert db.read_equity_snapshots("MSFT") == []
    etfs = db.read_etf_snapshots("SPY")
    assert len(etfs) == 1
    assert etfs[0].sector_weightings == {"technology": 0.3}
    assert etfs[0].total_net_assets == 1.0
