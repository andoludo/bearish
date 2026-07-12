from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from bearish.models.base import DataSourceBase
from bearish.utils.utils import to_float


class BalanceSheet(DataSourceBase):
    treasury_stock: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Shares held in the company's treasury"),
    ]

    common_stock_shares_outstanding: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Number of common shares outstanding"),
    ]

    common_stock: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Value of common stock issued"),
    ]

    short_long_term_debt_total: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Total short and long-term debt"),
    ]

    capital_lease_obligations: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Obligations under capital leases"),
    ]

    total_shareholder_equity: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Total equity held by shareholders"),
    ]

    retained_earnings: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Accumulated retained earnings"),
    ]

    total_liabilities: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Total liabilities, net of minority interest"),
    ]

    total_non_current_liabilities: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Total non-current liabilities"),
    ]

    other_non_current_liabilities: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Other non-current liabilities"),
    ]

    long_term_debt: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Long-term debt obligations"),
    ]

    total_current_liabilities: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Total current liabilities"),
    ]

    other_current_liabilities: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Other current liabilities"),
    ]

    current_debt: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Current debt obligations"),
    ]

    current_accounts_payable: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Accounts payable amount"),
    ]

    total_assets: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Total assets held by the company"),
    ]

    total_non_current_assets: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Total non-current assets"),
    ]

    other_non_current_assets: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Other non-current assets"),
    ]

    accumulated_depreciation_amortization_ppe: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Accumulated depreciation and amortization for property, plant, and equipment",
        ),
    ]

    property_plant_equipment: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Gross property, plant, and equipment"),
    ]

    total_current_assets: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Total current assets"),
    ]

    other_current_assets: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Other current assets"),
    ]

    inventory: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Inventory held by the company"),
    ]

    current_net_receivables: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Net receivables amount"),
    ]

    cash_and_short_term_investments: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Cash and short-term investments"),
    ]

    cash_and_cash_equivalents_at_carrying_value: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Cash and cash equivalents at carrying value"),
    ]


class QuarterlyBalanceSheet(BalanceSheet): ...
