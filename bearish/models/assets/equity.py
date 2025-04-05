from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from bearish.models.assets.base import BaseComponent
from bearish.utils.utils import to_string, to_float


class BaseEquity(BaseComponent):
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
    website: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(default=None, description="URL of the company's official website"),
    ]
    market_capitalization: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Market capitalization value",
        ),
    ]

    book_value: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Represents the net value of a company as recorded on "
            "its balance sheet. It reflects the amount shareholders "
            "would theoretically receive if all the company's assets "
            "were sold and all its liabilities were paid off",
        ),
    ]
    price_to_book: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Shares",
        ),
    ]
    trailing_price_to_earnings: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Calculated using a company's earnings over the last 12 months",
        ),
    ]

    dividend_yield: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Calculated using projected earnings for the next 12 months",
        ),
    ]
    dividend_rate: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Calculated using projected earnings for the next 12 months",
        ),
    ]
    trailing_earnings_per_share: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="EPS (Earnings Per Share) is a measure of a company's "
            "profitability on a per-share basis, often used by investors to gauge financial performance",
        ),
    ]
    forward_earnings_per_share: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="EPS (Earnings Per Share) is a measure of a company's "
            "profitability on a per-share basis, often used by investors to gauge financial performance",
        ),
    ]
    return_on_equity: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Indicates how efficiently a company uses shareholder equity to generate profits.",
        ),
    ]
    operating_margins: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Percentage of revenue remaining after operating expenses",
        ),
    ]
    gross_margins: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Percentage of revenue remaining after covering the cost of goods sold (COGS)",
        ),
    ]
    revenue_growth: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="The percentage increase in revenue over a specific period",
        ),
    ]


class Equity(BaseEquity):

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

    market_cap: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            default=None,
            description="Market capitalization category, such as 'Large Cap' or 'Small Cap'",
        ),
    ]

    shares_outstanding: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="The total number of shares that a company has issued to investors, "
            "including those held by insiders",
        ),
    ]
    float_shares: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="The portion of Shares Outstanding that is freely available "
            "for public trading on the open market",
        ),
    ]
    short_shares: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Refers to the number of shares of a company that have been sold "
            "short by investors but not yet repurchased or covered.",
        ),
    ]

    forward_price_to_earnings: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Calculated using projected earnings for the next 12 months",
        ),
    ]
    revenue_per_share: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Indicates how much revenue a company generates for each outstanding share of its stock",
        ),
    ]
    quick_ratio: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="The Quick Ratio measures a company's ability "
            "to pay its short-term liabilities using its most liquid assets, excluding inventory",
        ),
    ]
    current_ratio: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="The Current Ratio measures a company's ability "
            "to pay its short-term liabilities (due within a year) with its total current assets",
        ),
    ]
    earning_growth: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="The rate at which a company's net income increases.",
        ),
    ]
    trailing_peg_ratio: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Combines the P/E ratio with earnings growth to assess valuation in the context of growth",
        ),
    ]
    trailing_price_to_sales: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Measures the stock price relative to revenue per share",
        ),
    ]
    return_on_assets: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Measures how effectively a company uses its assets to generate profit",
        ),
    ]
    short_ratio: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="It provides insight into how heavily shorted "
            "a stock is and the potential for a short squeeze.",
        ),
    ]
    timezone: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            default=None,
            description="The timezone of the exchange where the stock is traded",
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
