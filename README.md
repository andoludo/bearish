# 🐻 Bearish

**Bearish** is a package for **querying financial and price data** from various equities across different countries, and **persisting it into a well-structured SQLite database** for further data analysis and stock screening.

---

## 🎯 Use Case

This package is intended for **active retail investors** with a strong passion for **data analysis**, who require well-structured, clean, and large datasets locally to:

- Run **custom technical and fundamental analysis**
- Perform in-depth **data analysis**
- Identify patterns and investment **insights**
- Build **custom screeners**

Bearish is **not designed for real-time trading**, but for extensive analysis of historical and current financial data.

---

## 🌍 Global Scope

Bearish is designed to collect large-scale data from exchanges in different countries. It **fetches data politely** — meaning it does not make large-scale concurrent API calls and instead respects the rate limits and policies of each data provider. So, **patience is required** during large data retrieval.

The data fetched includes:

- Historical **price data**
- Company **fundamentals**
- **Balance sheets**, **income statements**, and more

All data is stored in a **local SQLite database** from which you can query, analyze, and build insights.

---

## 📊 Data Sources

Bearish pulls data from multiple sources:

- [📦 FinanceDatabase](https://github.com/JerBouma/FinanceDatabase) for basic ticker information
- [🌐 InvestPy](https://github.com/alvarobartt/investpy) for country-level equity listings
- [📉 yFinance](https://pypi.org/project/yfinance/) as the primary source of prices and fundamentals
- [🔎 YahooQuery](https://pypi.org/project/yahooquery/) as a fallback for prices and fundamentals
- [📈 Tiingo](https://www.tiingo.com/) for prices (API key required)
- [🏛️ SEC EDGAR](https://www.sec.gov/) for 13F institutional holdings

> Ticker information is **enriched** using additional sources like yFinance, YahooQuery, etc.  
> Bearish is also **extensible** — you can add support for any data source or API.
>
> ℹ️ Support for **Financial Modeling Prep (FMP)** was removed: FMP discontinued
> its legacy API endpoints for subscriptions created after August 31, 2025.

By default, Bearish relies primarily on **yFinance** due to limitations in free-tier APIs of other providers. However, if you have a **premium subscription**, you can use other sources more fully.

---

## 📥 Installation

Install Bearish with pip:

```bash
pip install bearishpy
```

---

## 🚀 Fetch & Store Data

### 🏛️ Country-Level Data

Fetch and store stock data for selected countries:

```bash
bearish run /path/to/sqlite/db Belgium France --api-keys=config.json
```

✅ This command:

- Loads tickers from FinanceDatabase and InvestPy
- Filters relevant equities from the selected countries
- Enriches the data with fundamentals and prices
- Stores everything in your local SQLite database

> ⏱️ This operation can take some time depending on the size of the country’s exchange — data is fetched "politely", not in bulk.

Once your database is populated, future updates are quicker.

![img.png](docs/img/img.png)

---


The `config.json` contains the API keys of the different providers (if needed):

```json
{
  "Tiingo": "your Tiingo API key"
}
```

---

## 🧑‍💼 Analyst data & filings

Alongside statements and prices, Bearish records raw analyst data from
yFinance on every financials run:

- **`pricetarget`** — dated snapshots of analyst price targets
  (mean/high/low/median, number of analysts, recommendation mean/key).
  One row per fetch date, so a history accumulates across runs.
- **`analystrecommendation`** — the provider's recommendation trend
  (strong buy / buy / hold / sell / strong sell counts) per relative period
  bucket (`0m`, `-1m`, …), snapshotted per fetch date.

For US tickers, SEC EDGAR filing metadata can be fetched into the
**`filing`** table (form type, period of report, filed date, accession
number) and the 10-K / 10-Q filing date is copied onto financial statement
rows whose `(symbol, period_end)` matches exactly (`filed_date` column).
8-K current reports are stored too, with their EDGAR **item codes** in
`items` (`2.02` results, `4.01` auditor change, `4.02` restatement, `5.02`
officer departure, `1.03` bankruptcy, ...) and the event date in
`period_end`, so downstream analysis can tell a routine results filing from
a structural red flag without parsing the documents:

```bash
bearish filings /path/to/sqlite/db US --filters NVDA,AAPL
```

Earnings rows (`earningsdate`) also store `is_forward`, a fetch-time flag
marking rows whose earnings date was still in the future when fetched, and
price rows include dividends and stock splits.

---

## 🌐 Macro, commodity & regime data

Beyond tickers, Bearish stores **open macro-economic data keyed by concept
and entity** so that countries and commodities can be compared on the same
footing and later turned into KPIs:

- a **concept** is a normalised meaning (`CPI_YOY`, `POLICY_RATE`, `CLI`,
  `HY_SPREAD`, `COT_NET_SPEC`, …; see `bearish/macro/catalog/concepts.py`);
- an **entity** is an ISO-3 country (`FRA`), a region (`EA20`, `WLD`) or a
  commodity code (`BRENT`, `COPPER`; see `bearish/macro/commodities.py`);
- the **catalog** (`bearish/macro/catalog/`) maps each `concept.entity` to
  exactly one provider series. Providers are keyless open APIs: OECD, FRED,
  IMF, World Bank, BIS, ECB, Eurostat, policy-uncertainty and geopolitical
  risk indices, CFTC positioning, the World Bank Pink Sheet, Ken French
  factors (FRED also accepts an optional `FRED_API_KEY`).

Observations are stored **point-in-time**: every value carries the `as_of`
date on which it was known, and a provider revision is written as a new
vintage instead of overwriting the old one. `macrolatest` is a view of the
newest vintage per `(series_id, date)`; `read_observations(as_of=...)` answers
"what was known on that day", which is what keeps a backtest of
LLM-generated recommendations honest.

```bash
# every priority country (G7 + China + India + the countries supported by the
# equity pipeline), every category
bearish macro /path/to/sqlite/db

# a subset: two countries, only rates and credit, from 2015
bearish macro /path/to/sqlite/db FRA DEU --categories rates --categories credit --start 2015-01-01
```

Three more commands fill the tables around the macro store:

```bash
# commodity reference + futures prices (pricecommodity), World Bank Pink Sheet
# monthly history and CFTC positioning (macroobservation), and each country's
# export/import share per commodity from UN Comtrade (countrycommodityexposure)
bearish commodities /path/to/sqlite/db --year 2024

# SEC Form 4 insider transactions for US filers (insidertransaction)
bearish insiders /path/to/sqlite/db US --filters NVDA,AAPL --since 2025-01-01

# linking tables: country references/aliases (equitycountry view maps
# equity.country to ISO-3), curated sector <-> commodity sensitivities, and ETF
# exposure to countries, regions, commodities and sectors
bearish link /path/to/sqlite/db
```

Institutional ownership comes from two more SEC sources:

```bash
# Form 13F: every institutional manager's quarter-end positions, from the SEC
# bulk data sets (one ~100 MB zip per filing window, all filers at once).
# Per-manager rows go to holding13f for --managers plus the --top-managers
# largest filers; holding13fsummary holds, for EVERY security and quarter,
# the number of holders, total shares/value and the flows against the prior
# quarter (new holders, closed holders, share and value change).
bearish holdings /path/to/sqlite/db --windows 2 --managers 0001067983

# Schedule 13D/13G: beneficial owners crossing 5 % (13D = activists, filed
# within days; 13G = passive), parsed from EDGAR's structured XML (filings
# since December 2024) into ownership13dg.
bearish ownership /path/to/sqlite/db US --filters AAPL,ASPN
```

13F positions are published up to 45 days after quarter end, so treat them as
a lagging, quarterly signal; `holding13f.filed_date` and
`holding13fsummary.latest_filed_date` record when each snapshot became public.

US financial statements are now taken from **SEC XBRL companyfacts** first
(as reported, with the real `filed_date`), falling back to Yahoo for tickers
the SEC does not cover.

Tables: `macroseries` (catalog mirror), `macroobservation`
(`series_id, date, value, as_of`), `macrotracker` (last fetched date per
series, used by `bearish update --macro` to refresh only what is due and to
re-request a revision window). From Python:

```python
from bearish.main import Bearish
from bearish.macro.models import MacroQuery

bearish = Bearish(path="/path/to/sqlite/db")
frame = bearish.read_macro(MacroQuery(entities=["FRA", "USA"], categories=["inflation", "rates"]))
known_then = bearish.read_observations(MacroQuery(concepts=["GDP_YOY"], as_of="2025-06-30"))
```

---

## 🔄 Updating Data

### 💵 Update Prices

To update only the price data:

```bash
bearish prices /path/to/sqlite/db Belgium France --api-keys=config.json
```
![img_2.png](docs/img/img_2.png)
---

### 🧾 Update Financials

To update financial and fundamental data:

```bash
bearish financials /path/to/sqlite/db Belgium France --api-keys=config.json
```
![img_1.png](docs/img/img_1.png)
---

## 🎯 Fetch Specific Tickers

To fetch and store data for specific tickers:

```bash
bearish run /path/to/sqlite/db US --filters NVDA,TSLA,RHM.DE --api-keys=config.json
```

> You must always provide the country where each ticker is traded along with the desired tickers as filters.

---

## 📚 Summary

| Feature | Description |
|--------|-------------|
| 🌍 Country-level support | Fetch equities from any exchange |
| 🧠 Fundamental data | Balance sheets, cash flow, income statements |
| 📉 Price history | Up-to-date historical prices |
| 🗄️ Local database | Data saved in SQLite for offline analysis |
| 🔌 Extensible | Plug in your own APIs or providers |
| 🧪 Designed for analysis | Ideal for custom screeners and research |

---

## 🛠️ Contributing

Contributions are welcome! Feel free to open issues or submit pull requests to improve Bearish.

### Development

The project is managed with [uv](https://github.com/astral-sh/uv):

```bash
uv sync                                      # install dependencies
uv run pytest -m "not network and not lfs"   # offline, deterministic tests
uv run pytest                                # full suite (live APIs + git-lfs test db)
uv run ruff check                            # lint
uv run mypy                                  # type check
```

Database schema changes are managed with **Alembic** (migrations live in
`bearish/database/alembic/versions`):

```bash
uv run python -m bearish.database.scripts.create_revision   # autogenerate a revision
uv run python -m bearish.database.scripts.upgrade           # upgrade a database to head
```

---

## 📄 License

Bearish is released under the **MIT License**.