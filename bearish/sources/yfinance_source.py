"""yfinance-backed implementation of :class:`FinancialDataSource`.

The translation from yfinance's ``DataFrame`` outputs to the common data
model is the only thing this module is responsible for — fetching is
delegated to yfinance, persistence to the repository.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
from collections.abc import Iterable
from typing import Any

from bearish.exceptions import SourceError
from bearish.models import Asset, AssetKind, FinancialStatement, Price

logger = logging.getLogger(__name__)

_QUOTE_TYPE_TO_KIND = {
    "EQUITY": AssetKind.EQUITY,
    "ETF": AssetKind.ETF,
    "INDEX": AssetKind.INDEX,
    "CRYPTOCURRENCY": AssetKind.CRYPTO,
    "CURRENCY": AssetKind.CURRENCY,
}

_REVENUE_KEYS = ("Total Revenue", "TotalRevenue", "Revenue")
_NET_INCOME_KEYS = ("Net Income", "NetIncome", "Net Income Common Stockholders")
_TOTAL_ASSETS_KEYS = ("Total Assets", "TotalAssets")
_TOTAL_LIAB_KEYS = (
    "Total Liab",
    "Total Liabilities",
    "TotalLiabilitiesNetMinorityInterest",
)
_OPERATING_CASH_FLOW_KEYS = (
    "Operating Cash Flow",
    "OperatingCashFlow",
    "Total Cash From Operating Activities",
)


class YFinanceSource:
    name = "yfinance"

    def fetch_assets(self, symbols: Iterable[str] | None = None) -> list[Asset]:
        if not symbols:
            return []
        import yfinance  # imported lazily so tests can stub it out

        assets: list[Asset] = []
        for raw in symbols:
            symbol = raw.upper()
            try:
                info = yfinance.Ticker(symbol).info or {}
            except Exception as exc:
                raise SourceError(f"yfinance failed for {symbol!r}: {exc}") from exc

            quote_type = (info.get("quoteType") or "").upper()
            assets.append(
                Asset(
                    symbol=symbol,
                    name=info.get("shortName") or info.get("longName"),
                    exchange=info.get("exchange"),
                    country=info.get("country"),
                    currency=info.get("currency"),
                    kind=_QUOTE_TYPE_TO_KIND.get(quote_type, AssetKind.EQUITY),
                    sector=info.get("sector"),
                    industry=info.get("industry"),
                )
            )
        return assets

    def fetch_prices(
        self,
        symbol: str,
        start: dt.date | None = None,
        end: dt.date | None = None,
    ) -> list[Price]:
        import yfinance

        symbol = symbol.upper()
        try:
            history = yfinance.Ticker(symbol).history(
                start=start,
                end=end,
                period=None if (start or end) else "max",
                auto_adjust=False,
            )
        except Exception as exc:
            raise SourceError(f"yfinance history failed for {symbol!r}: {exc}") from exc

        prices: list[Price] = []
        for ts, row in history.iterrows():
            try:
                values = (row["Open"], row["High"], row["Low"], row["Close"], row["Volume"])
            except KeyError:
                continue
            if any(_is_nan(v) for v in values):
                continue
            prices.append(
                Price(
                    symbol=symbol,
                    date=_to_date(ts),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                    source=self.name,
                )
            )
        return prices

    def fetch_statements(self, symbol: str) -> list[FinancialStatement]:
        import yfinance

        symbol = symbol.upper()
        try:
            ticker = yfinance.Ticker(symbol)
            financials = ticker.financials
            balance = ticker.balance_sheet
            cashflow = ticker.cashflow
        except Exception as exc:
            raise SourceError(
                f"yfinance statements failed for {symbol!r}: {exc}"
            ) from exc

        period_ends = sorted(set(financials.columns) | set(balance.columns) | set(cashflow.columns))
        statements: list[FinancialStatement] = []
        for period_end in period_ends:
            statements.append(
                FinancialStatement(
                    symbol=symbol,
                    period_end=_to_date(period_end),
                    period="annual",
                    source=self.name,
                    revenue=_first(financials, period_end, _REVENUE_KEYS),
                    net_income=_first(financials, period_end, _NET_INCOME_KEYS),
                    total_assets=_first(balance, period_end, _TOTAL_ASSETS_KEYS),
                    total_liabilities=_first(balance, period_end, _TOTAL_LIAB_KEYS),
                    operating_cash_flow=_first(
                        cashflow, period_end, _OPERATING_CASH_FLOW_KEYS
                    ),
                )
            )
        return statements


def _is_nan(value: Any) -> bool:
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _to_date(ts: Any) -> dt.date:
    if isinstance(ts, dt.date):
        return ts
    if hasattr(ts, "date"):
        result = ts.date()
        if isinstance(result, dt.date):
            return result
    return dt.date.fromisoformat(str(ts)[:10])


def _first(df: Any, column: Any, keys: tuple[str, ...]) -> float | None:
    if df is None or column not in getattr(df, "columns", []):
        return None
    series = df[column]
    for key in keys:
        if key in series.index:
            value = series[key]
            if _is_nan(value):
                return None
            return float(value)
    return None
