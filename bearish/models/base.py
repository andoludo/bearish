from datetime import datetime
from math import isnan
from typing import Any, Optional, Annotated

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, BeforeValidator

from bearish.models.financials import BaseFinancials


def to_string(value: Any) -> Optional[str]:
    if value is None or (isinstance(value, float) and isnan(value)):
        return None
    return str(value)


class BaseBearishModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class BaseComponent(BaseFinancials):
    symbol: str = Field(
        description="Unique ticker symbol identifying the company on the stock exchange"
    )
    name: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None, description="Full name of the company"),
    ]
    summary: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            None, description="Brief summary of the company's operations and activities"
        ),
    ]
    currency: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            None,
            description="Currency code (e.g., USD, CNY) in which the company's financials are reported",
        ),
    ]
    exchange: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            None,
            description="Stock exchange where the company is listed, represented by its abbreviation",
        ),
    ]
    market: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            None,
            description="Market type or classification for the company's listing, such as 'Main Market'",
        ),
    ]


class Equity(BaseComponent):

    sector: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            None,
            description="Broad sector to which the company belongs, such as 'Real Estate' or 'Technology'",
        ),
    ]
    industry_group: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            None,
            description="Industry group within the sector, providing a more specific categorization",
        ),
    ]
    industry: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            None,
            description="Detailed industry categorization for the company, like 'Real Estate Management & Development'",
        ),
    ]

    country: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None, description="Country where the company's headquarters is located"),
    ]
    state: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            default=None,
            description="State or province where the company's headquarters is located, if applicable",
        ),
    ]
    city: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None, description="City where the company's headquarters is located"),
    ]
    zipcode: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(default=None, description="Postal code for the company's headquarters"),
    ]
    website: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(default=None, description="URL of the company's official website"),
    ]
    market_cap: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            default=None,
            description="Market capitalization category, such as 'Large Cap' or 'Small Cap'",
        ),
    ]
    isin: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            default=None,
            description="International Securities Identification Number (ISIN) for the company's stock",
        ),
    ]
    cusip: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            default=None,
            description="CUSIP identifier for the company's stock (mainly used in the US)",
        ),
    ]
    figi: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            default=None,
            description="Financial Instrument Global Identifier (FIGI) for the company",
        ),
    ]
    composite_figi: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            default=None,
            description="Composite FIGI, a global identifier that aggregates multiple instruments",
        ),
    ]
    shareclass_figi: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            default=None,
            description="FIGI specific to a share class, distinguishing between types of shares",
        ),
    ]


class Crypto(BaseComponent):
    cryptocurrency: Annotated[str, BeforeValidator(to_string)]


class Currency(BaseComponent):
    base_currency: Annotated[str, BeforeValidator(to_string)]
    quote_currency: Annotated[str, BeforeValidator(to_string)]


class Etf(BaseComponent):
    category_group: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(default=None),
    ]
    category: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(default=None),
    ]
    family: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(default=None),
    ]

def to_float(value: Any) -> float:
    return float(value)


def to_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d")
    elif isinstance(value, pd.Timestamp):
        if value.tz is not None:
            value = value.tz_convert(None)
        return value.to_pydatetime()
    elif isinstance(value, datetime):
        return value
    else:
        raise ValueError(f"Invalid datetime value: {value}")



class CandleStick(BaseFinancials):
    open: Annotated[float, BeforeValidator(to_float)]
    high: Annotated[float, BeforeValidator(to_float)]
    low: Annotated[float, BeforeValidator(to_float)]
    close: Annotated[float, BeforeValidator(to_float)]
    volume: Annotated[float, BeforeValidator(to_float)]
    dividends: Annotated[Optional[float], BeforeValidator(to_float), Field(None)]
    stock_splits: Annotated[Optional[float], BeforeValidator(to_float), Field(None)]
