# 🐻 Bearish

**Bearish** fetches financial data from various sources, normalises it into a
common data model, and persists it in a local SQLite database — ready for
offline screening, backtesting, and analysis.

The package was redesigned around three simple ideas:

1. **One data model** — every source produces the same `Asset`, `Price`, and
   `FinancialStatement` shapes.
2. **Pluggable sources** — anything that satisfies the `FinancialDataSource`
   protocol works.
3. **Plain SQLite** — no ORM, no migrations; just `sqlite3` with idempotent
   upserts.

---

## Architecture (SOLID at a glance)

```
┌──────────┐    ┌─────────────────────┐    ┌──────────────────┐
│   CLI    │ ─► │   BearishService    │ ─► │ SqliteRepository │
└──────────┘    │  (orchestration)    │    └──────────────────┘
                │                     │
                │   uses Protocol     │
                ▼                     ▼
        ┌────────────────────────────────────┐
        │       FinancialDataSource          │  ← Protocol
        ├────────────────────────────────────┤
        │ YFinanceSource │ InMemorySource │…│
        └────────────────────────────────────┘
```

* **S** ingle responsibility — models, sources, repository, service, CLI live
  in dedicated modules.
* **O** pen for extension — add a source by implementing three methods.
* **L** iskov substitution — every source is interchangeable behind the
  protocol.
* **I** nterface segregation — the protocol exposes only the three methods
  the service actually calls.
* **D** ependency inversion — the service depends on the protocol, not on
  any concrete provider.

---

## Install

This project uses [uv](https://github.com/astral-sh/uv) for package management.

```bash
uv sync           # create the virtual env and install dependencies
uv run bearish    # run the CLI
```

To install as a regular package:

```bash
pip install bearishpy
```

---

## Quick start (CLI)

```bash
# Fetch asset metadata
bearish sync-assets ./bearish.db --symbol AAPL --symbol MSFT

# Fetch OHLCV price history
bearish sync-prices ./bearish.db --symbol AAPL --start 2023-01-01

# Fetch financial statements
bearish sync-statements ./bearish.db --symbol AAPL

# All of the above
bearish sync-all ./bearish.db --symbol AAPL
```

---

## Quick start (Python)

```python
from bearish import BearishService, SqliteRepository
from bearish.sources.yfinance_source import YFinanceSource

service = BearishService(
    SqliteRepository("./bearish.db"),
    sources=[YFinanceSource()],
)
service.sync_all(["AAPL", "MSFT"])

assets = service.repository.load_assets()
prices = service.repository.load_prices("AAPL")
```

---

## Adding a new data source

Implement the `FinancialDataSource` protocol:

```python
from bearish import Asset, FinancialStatement, Price

class MySource:
    name = "mysource"

    def fetch_assets(self, symbols=None) -> list[Asset]: ...
    def fetch_prices(self, symbol, start=None, end=None) -> list[Price]: ...
    def fetch_statements(self, symbol) -> list[FinancialStatement]: ...
```

Pass it into `BearishService(sources=[...])`. Sources are tried in order and
the service falls back to the next source on failure or empty result.

---

## Development

```bash
uv sync                    # install deps
uv run pytest              # run the test suite
uv run ruff check bearish  # lint
uv run mypy bearish        # type check
```

The test suite uses an `InMemorySource` and `:memory:` SQLite — it never
touches the network.

---

## License

MIT.
