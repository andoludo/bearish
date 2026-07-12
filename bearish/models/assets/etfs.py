from typing import Annotated, Optional, Dict

from pydantic import BeforeValidator, Field

from bearish.models.assets.base import BaseComponent
from bearish.utils.utils import to_string, to_float


class Etf(BaseComponent):
    category_group: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(default=None),
    ]
    family: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(default=None),
    ]

    three_year_earnings_growth: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Earnings growth over the past three years."),
    ]
    annual_holdings_turnover: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Percentage of portfolio holdings replaced annually."),
    ]
    annual_report_expense_ratio: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            None,
            description="Annual cost of managing the fund as a percentage of total assets.",
        ),
    ]
    holding_percent: Optional[Dict[str, float]] = Field(
        None, description="Percentage of the ETF allocated to specific holdings."
    )
    median_market_cap: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Median market capitalization of the ETF's holdings."),
    ]
    price_to_book: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Price-to-book ratio of the ETF."),
    ]
    price_to_cashflow: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Price-to-cashflow ratio of the ETF."),
    ]
    price_to_earnings: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Price-to-earnings ratio of the ETF."),
    ]
    price_to_sales: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Price-to-sales ratio of the ETF."),
    ]
    sector_weightings: Optional[Dict[str, float]] = Field(
        None, description="Weightings of the ETF across various sectors."
    )
    total_net_assets: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Total net assets managed by the ETF."),
    ]

    beta_3_year: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Beta value of the ETF over the past three years."),
    ]

    category: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None, description="Category of the ETF (e.g., 'Large Blend')."),
    ]
    fund_family: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None, description="Fund family managing the ETF."),
    ]
    fund_inception_date: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Inception date of the ETF in epoch format."),
    ]
    legal_type: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            None,
            description="Legal classification of the ETF (e.g., 'Exchange Traded Fund').",
        ),
    ]
    long_business_summary: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(
            None, description="Detailed description of the ETF's investment objective."
        ),
    ]
    long_name: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None, description="Full name of the ETF."),
    ]
    nav_price: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Net asset value (NAV) price of the ETF."),
    ]
    quote_type: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None, description="Type of the security (e.g., 'ETF')."),
    ]
    short_name: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None, description="Shortened name of the ETF."),
    ]
    three_year_average_return: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Three-year average return of the ETF."),
    ]
    trailing_annual_dividend_rate: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Annual dividend rate paid by the ETF."),
    ]
    trailing_annual_dividend_yield: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Annual dividend yield of the ETF."),
    ]
    trailing_pe: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Trailing price-to-earnings ratio of the ETF."),
    ]
    yield_: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Yield of the ETF."),
    ]
    ytd_return: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(None, description="Year-to-date return of the ETF."),
    ]
