import json
from typing import Optional, Annotated, Any, Dict

from pydantic import Field, BeforeValidator, model_validator

from bearish.models.base import DataSourceBase
from bearish.utils.utils import to_string, format_capitalize


class ComponentDescription(DataSourceBase):
    symbol: str = Field(
        description="Unique ticker symbol identifying the company on the stock exchange"
    )
    name: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None, description="Full name of the company"),
    ]
    isin: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            default=None,
            description="International Securities Identification Number (ISIN) for the company's stock",
        ),
    ]


class BaseComponent(ComponentDescription):
    base_symbol: str = Field(
        description="Root symbol, primary ticker, or company identifier."
    )
    modifier: Optional[str] = Field(
        None, description="Suffix, modifier, attribute, or share class indicator."
    )
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
    country: Annotated[
        Optional[str],
        BeforeValidator(format_capitalize),
        Field(None, description="Country where the company's headquarters is located"),
    ]

    @model_validator(mode="before")
    @classmethod
    def _validator(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if "symbol" not in value:
            raise ValueError(
                f"Symbol is required for BaseComponent. Provided data {json.dumps(value, indent=4)}"
            )
        base_symbol, *modifier = value["symbol"].split(".")
        value["base_symbol"] = base_symbol
        value["modifier"] = modifier[0] if modifier else None
        return value
