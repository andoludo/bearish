from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from bearish.models.base import DataSourceBase
from bearish.utils.utils import to_float


class CashFlow(DataSourceBase):
    operating_cash_flow: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None, description="Cash flow generated from operating activities"
        ),
    ]
    change_in_operating_liabilities: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Changes in operating liabilities"),
    ]
    change_in_working_capital: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Changes in working capital from operating activities",
        ),
    ]
    change_in_other_working_capital: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Changes in other working capital from operating activities",
        ),
    ]
    change_in_receivables: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Changes in accounts receivable balance"),
    ]
    change_in_inventory: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Changes in inventory levels"),
    ]
    depreciation_amortization_depletion: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Total depreciation, depletion, and amortization expenses",
        ),
    ]
    capital_expenditure: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Capital expenditures for fixed assets"),
    ]
    cash_flow_from_investing_activities: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Cash flow generated or used in investing activities",
        ),
    ]
    financing_cash_flow: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Cash flow generated or used in financing activities",
        ),
    ]
    repurchase_of_capital_stock: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Payments made for repurchase of common stock"),
    ]
    cash_dividends_paid: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Cash dividends paid to shareholders"),
    ]
    common_stock_dividend_paid: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Dividends paid on common stock"),
    ]
    proceeds_from_issuance_of_common_stock: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Proceeds from issuance of common stock"),
    ]
    changes_in_cash: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Net changes in cash and cash equivalents"),
    ]
    net_income_from_continuing_operations: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Net income from continuing operations"),
    ]


class QuarterlyCashFlow(CashFlow): ...
