import contextlib
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Type, Union

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic._internal._model_construction import ModelMetaclass

EXPECTED_DATE_FORMATS = ["%Y%d/%m", "%Y", "%d %b '%y", "H%q '%y", "%m/%d/%Y"]
FINAL_DATE_FORMAT = "%Y-%m-%d"

UNIT_MAPPING = {"K": 1000, "M": 1000000, "B": 1000000000}


class BaseTickerModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


def get_date(date: str) -> str:
    dates = [
        datetime.strptime(date, format).strftime(FINAL_DATE_FORMAT)
        for format in EXPECTED_DATE_FORMATS
        if is_date_format(date, format)
    ]
    if not dates:
        raise ValueError
    return dates[0]


def is_date_format(date: str, format: str) -> bool:
    try:
        datetime.strptime(date, format)
        return True
    except ValueError:
        return False


def all_final_format(data: Dict[str, Any]) -> bool:
    return all(is_date_format(date, FINAL_DATE_FORMAT) for date, _ in data.items())


def clean_value(
    value: Optional[Union[int, float, str]]
) -> Optional[Union[int, float, str]]:
    if value is None:
        return None
    if isinstance(value, str):
        value = (
            value.replace(" ", "")  # TODO: horrible
            .replace("    ", "")
            .replace("%", "")
            .replace("USD", "")
            .replace("EURO", "")
            .replace("EUR", "")
            .strip()
        )
        for unit, float_value in UNIT_MAPPING.items():
            if unit in value:
                value = str(
                    float(value.replace(unit, "")) * float_value
                )  # TODO: horrible
    try:
        return float(value)
    except ValueError:
        return value


def _validate_date(v: Dict[str, Any]) -> Dict[str, Any]:
    if (not v) or all_final_format(v):
        return v
    results = {}
    for date, value in v.items():
        with contextlib.suppress(ValueError):
            results[get_date(date)] = clean_value(value)
    return results


def _indentify_yearly_quarterly(data: Dict[str, Any]) -> Dict[str, Any]:
    for key in data:
        if "quarterly" in key and key.replace("quarterly", "").strip() in data:
            data[key.replace("quarterly", "").strip()] = {
                "yearly": data[key.replace("quarterly", "").strip()],
                "quarterly": data[key],
            }
    return data


def _create_yearly_quarterly(data: Dict[str, Any]) -> Dict[str, Any]:
    if "yearly" not in data and "quarterly" not in data:
        return {"yearly": data, "quarterly": None}
    return data


class Resolution(BaseTickerModel):
    yearly: Optional[Dict[str, Any]] = None
    quarterly: Optional[Dict[str, Any]] = None

    @field_validator(
        "yearly",
        "quarterly",
        mode="before",
    )
    @classmethod
    def date_field(cls, v: Dict[str, Any]) -> Optional[Optional[Dict[str, Any]]]:
        return _validate_date(v)


class IncomeStatement(BaseTickerModel):
    revenue: Optional[Resolution] = Field(
        default=None, validation_alias=AliasChoices("Total Revenue", "Total revenue")
    )
    cost_of_goods_sold: Optional[Resolution] = Field(
        default=None,
        validation_alias=AliasChoices("Cost of Revenue, Total", "Cost of goods sold"),
    )
    gross_profit: Optional[Resolution] = Field(
        default=None, validation_alias=AliasChoices("Gross Profit", "Gross profit")
    )
    total_operating_expenses: Optional[Resolution] = Field(
        default=None,
        validation_alias=AliasChoices(
            "Total Operating Expenses", "Total operating expenses"
        ),
    )
    operating_income: Optional[Resolution] = Field(
        default=None,
        validation_alias=AliasChoices("Operating Income", "Operating income"),
    )
    net_income_before_taxes: Optional[Resolution] = Field(
        default=None,
        validation_alias=AliasChoices("Net Income Before Taxes", "Pretax income"),
    )
    net_income_after_taxes: Optional[Resolution] = Field(
        default=None, validation_alias=AliasChoices("Net Income After Taxes")
    )
    net_income: Optional[Resolution] = Field(
        default=None, validation_alias=AliasChoices("Net Income", "Net income")
    )

    @model_validator(mode="before")
    @classmethod
    def identify_yearly_or_quarterly(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        return _indentify_yearly_quarterly(data)

    @field_validator(
        "revenue",
        "cost_of_goods_sold",
        "gross_profit",
        "total_operating_expenses",
        "operating_income",
        "net_income_before_taxes",
        "net_income_after_taxes",
        "net_income",
        mode="before",
    )
    @classmethod
    def date_field(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            return v
        return _create_yearly_quarterly(v)


class BalanceSheet(BaseTickerModel):
    total_current_assets: Optional[Resolution] = Field(
        default=None, validation_alias=AliasChoices("Total Current Assets")
    )
    total_assets: Optional[Resolution] = Field(
        default=None, validation_alias=AliasChoices("Total Assets", "Total assets")
    )
    total_current_liabilities: Optional[Resolution] = Field(
        default=None, validation_alias=AliasChoices("Total Current Liabilities")
    )
    total_liabilities: Optional[Resolution] = Field(
        default=None,
        validation_alias=AliasChoices("Total Liabilities", "Total liabilities"),
    )
    total_equity: Optional[Resolution] = Field(
        default=None, validation_alias=AliasChoices("Total Equity", "Total equity")
    )

    @model_validator(mode="before")
    @classmethod
    def identify_yearly_or_quarterly(cls, data: Dict[str, Any]) -> Dict[str, Any]:

        return _indentify_yearly_quarterly(data)

    @field_validator(
        "total_current_assets",
        "total_assets",
        "total_current_liabilities",
        "total_liabilities",
        "total_equity",
        mode="before",
    )
    @classmethod
    def date_field(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            return v
        return _create_yearly_quarterly(v)


class CashFlow(BaseTickerModel):
    ...


class Ratios(BaseTickerModel):
    price_earning_ratio: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("P/E Ratio", "P/E")
    )
    earning_per_share: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("EPS")
    )
    earning_per_share_ttm: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("EPS dilTTM")
    )
    earning_per_share_yoy: Optional[str | float] = Field(
        default=None,
        validation_alias=AliasChoices(
            "EPS dil growthTTM YoY", "EPS(TTM) vs TTM 1 Yr. Ago"
        ),
    )
    payout_ratio: Optional[str | float] = Field(
        default=None,
        validation_alias=AliasChoices("Payout Ratio (TTM)", "Div payout ratio %TTM"),
    )
    dividend_yield: Optional[str | float] = Field(
        default=None,
        validation_alias=AliasChoices("Dividend Yield (%)", "Div yield % (indicated)"),
    )

    @field_validator(
        "price_earning_ratio",
        "earning_per_share",
        "payout_ratio",
        "dividend_yield",
        mode="before",
    )
    @classmethod
    def must_be_float(
        cls, v: Optional[Union[str, float, int]]
    ) -> Optional[Union[str, float, int]]:
        if not v:
            return None
        return clean_value(v)


class Valuation(BaseTickerModel):
    market_cap: Optional[float | str] = Field(
        default=None, validation_alias=AliasChoices("Market Cap")
    )
    market_cap_performance_one_year: Optional[float | str] = Field(
        default=None, validation_alias=AliasChoices("Market cap perf %1Y")
    )
    enterprise_value: Optional[float | str] = Field(
        default=None, validation_alias=AliasChoices("EV")
    )

    @field_validator(
        "market_cap",
        "enterprise_value",
        mode="before",
    )
    @classmethod
    def must_be_float(
        cls, v: Optional[Union[str, float, int]]
    ) -> Optional[Union[str, float, int]]:
        if not v:
            return None
        return clean_value(v)


class Performance(BaseTickerModel):
    performance_week: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("1 Week", "Perf %1W")
    )
    performance_month: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("1 Month", "Perf %1M")
    )
    performance_three_months: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("Perf %3M")
    )
    performance_six_months: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("Perf %6M")
    )
    performance_year_to_date: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("YTD", "Perf %YTD")
    )
    performance_one_year: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("1 Year", "Perf %1Y")
    )
    performance_three_years: Optional[str | float] = Field(
        default=None,
        validation_alias=AliasChoices("3 Years", "Div yield % (indicated)"),
    )
    performance_five_years: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("Perf %5Y")
    )
    performance_all_time: Optional[str | float] = Field(
        default=None, validation_alias=AliasChoices("Perf %All Time")
    )


class Fundamental(BaseTickerModel):
    income_statement: IncomeStatement
    balance_sheet: BalanceSheet
    cash_flow: CashFlow
    ratios: Ratios
    valuation: Valuation


class HistoricalData(BaseTickerModel):
    price: Optional[Dict[str, Any]] = Field(
        default=None, validation_alias=AliasChoices("Price")
    )
    open: Optional[Dict[str, Any]] = Field(
        default=None, validation_alias=AliasChoices("Open")
    )
    high: Optional[Dict[str, Any]] = Field(
        default=None, validation_alias=AliasChoices("High")
    )
    low: Optional[Dict[str, Any]] = Field(
        default=None, validation_alias=AliasChoices("Low")
    )
    volume: Optional[Dict[str, Any]] = Field(
        default=None, validation_alias=AliasChoices("Vol.")
    )
    change: Optional[Dict[str, Any]] = Field(
        default=None, validation_alias=AliasChoices("Change %")
    )

    @field_validator(
        "price",
        "open",
        "high",
        "low",
        "volume",
        "change",
        mode="before",
    )
    @classmethod
    def date_field(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not v:
            return None
        return _validate_date(v)


class Ticker(BaseTickerModel):
    name: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("Name", "name")
    )
    symbol: Optional[str] = Field(default=None, validation_alias=AliasChoices("Symbol"))
    source: Optional[Literal["trading", "investing", "yahoo"]] = None
    sector: Optional[str] = Field(default=None, validation_alias=AliasChoices("Sector"))
    reference: Optional[str] = None
    industry: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("Industry")
    )
    exchange: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("Exchange", "exchange")
    )
    fundamental: Fundamental
    historical: Optional[HistoricalData] = None

    @field_validator("reference", mode="before")
    @classmethod
    def reference_validator(cls, value: str) -> str:
        if value and isinstance(value, str):
            return value.split("/")[-1].split("?")[0]
        return value

    @classmethod
    def from_json(
        cls, path: Path, source: Literal["trading", "investing", "yahoo"]
    ) -> List["Ticker"]:
        records = json.loads(Path(path).read_text())
        return [cls.from_record(record, source) for record in records]

    @classmethod
    def from_record(
        cls,
        record: Dict[str, Any] | list[Dict[str, Any]],
        source: Literal["trading", "investing", "yahoo"],
    ) -> "Ticker":
        return cls(**(unflatten_json(cls, _clean(record) | {"source": source})))  # type: ignore


def is_nested(schema: Type[BaseModel]) -> bool:
    return any(
        field.annotation.__name__ in globals()  # type: ignore
        for _, field in schema.model_fields.items()
    )


def merge(
    schema: Type[BaseModel], instance_1: BaseModel, instance_2: BaseModel
) -> None:
    for name, field in schema.model_fields.items():
        if (
            field.annotation.__name__ in globals()  # type: ignore
            and isinstance(field.annotation, ModelMetaclass)
            and issubclass(field.annotation, BaseTickerModel)
        ):
            merge(
                field.annotation, getattr(instance_1, name), getattr(instance_2, name)
            )
        elif not getattr(instance_1, name) and getattr(instance_2, name):
            setattr(instance_1, name, getattr(instance_2, name))
        else:
            pass


def unflatten_json(schema: Type[BaseModel], data: Dict[str, Any]) -> Dict[str, Any]:
    if not is_nested(schema):
        return schema(**data).model_dump()
    copy_data = copy.deepcopy(data)
    original_data = {}
    for name, field in schema.model_fields.items():
        if (
            field.annotation.__name__ in globals()  # type: ignore
            and isinstance(field.annotation, ModelMetaclass)
            and issubclass(field.annotation, BaseTickerModel)
        ):
            original_data[name] = unflatten_json(field.annotation, data)
    copy_data.update(original_data)
    return schema(**copy_data).model_dump()


def _clean(
    data: List[Dict[str, Any]] | Dict[str, Any]
) -> List[Dict[str, Any]] | Dict[str, Any]:
    if isinstance(data, list):
        return [clean_dict(data_) for data_ in data]
    else:
        return clean_dict(data)


def clean_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    cleaned_data = {}
    for name, value in data.items():
        if isinstance(value, dict):
            cleaned_data[str(name)] = clean_dict(value)
        else:
            cleaned_data[str(name)] = value
    return cleaned_data
