"""Daily FX rates against the US dollar, for cross-currency comparison.

Every asset table carries a ``currency``; to compare a Belgian, a Japanese
and a US stock on one footing the prices have to be converted. Bearish keeps
the raw Yahoo Finance daily quotes of ``USD<CCY>=X`` pairs (units of ``CCY``
per one US dollar) in ``pricecurrency``; any cross rate is a ratio of two
USD pairs, which is downstream work. The ``fxrate`` view exposes
``(date, base, quote, rate)``.
"""

import logging
from typing import TYPE_CHECKING, Iterable, List, Optional

from bearish.database.schemas import PriceCurrencyORM
from bearish.interface.interface import BearishDbBase
from bearish.models.base import Ticker
from bearish.types import SeriesLength

if TYPE_CHECKING:
    from bearish.main import Bearish

logger = logging.getLogger(__name__)

PIVOT_CURRENCY = "USD"
# Always fetched, whatever the database holds: the funding currencies most
# portfolios are measured in plus the large markets.
CORE_CURRENCIES = ("EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "HKD", "SEK", "NOK", "DKK", "INR", "KRW", "BRL")
ASSET_TABLES = ("equity", "etf", "index")
ISO_CODE_LENGTH = 3


def fx_symbol(quote: str, base: str = PIVOT_CURRENCY) -> str:
    """Yahoo Finance symbol of the pair quoting ``quote`` units per one ``base`` (``USDJPY=X``)."""
    return f"{base.upper()}{quote.upper()}=X"


def normalise_currency(value: Optional[str]) -> Optional[str]:
    """ISO-4217 code in upper case, with Yahoo's minor-unit codes mapped to their currency."""
    if not value:
        return None
    code = value.strip().upper()
    minor_units = {"GBP": "GBP", "GBX": "GBP", "ZAC": "ZAR", "ILA": "ILS"}
    code = minor_units.get(code, code)
    return code if len(code) == ISO_CODE_LENGTH and code.isalpha() else None


def currencies_in_use(db: BearishDbBase) -> List[str]:
    """Distinct ISO currencies of the stored equities, ETFs and indices plus the core set."""
    found = set(CORE_CURRENCIES)
    for table in ASSET_TABLES:
        frame = db.read_query(f'SELECT DISTINCT currency FROM "{table}" WHERE currency IS NOT NULL')
        for value in frame["currency"].tolist():
            code = normalise_currency(value)
            if code:
                found.add(code)
    found.discard(PIVOT_CURRENCY)
    return sorted(found)


def fx_tickers(currencies: Iterable[str]) -> List[Ticker]:
    return [Ticker(symbol=fx_symbol(currency)) for currency in sorted(set(currencies)) if currency != PIVOT_CURRENCY]


def write_fx_prices(
    bearish: "Bearish", series_length: SeriesLength = "max", currencies: Optional[List[str]] = None
) -> List[str]:
    """Fetch the USD pairs into ``pricecurrency``; returns the symbols requested."""
    codes = currencies if currencies is not None else currencies_in_use(bearish._bearish_db)
    tickers = fx_tickers(codes)
    logger.info(f"Fetching {len(tickers)} FX pairs against {PIVOT_CURRENCY}")
    bearish.write_many_series(tickers, series_length, apply_filter=False, table=PriceCurrencyORM, track=False)
    return [ticker.symbol for ticker in tickers]
