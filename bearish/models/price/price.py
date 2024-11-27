from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from bearish.models.base import DataSourceBase
from bearish.utils.utils import to_float



class Price(DataSourceBase):
    open: Annotated[float, BeforeValidator(to_float)]
    high: Annotated[float, BeforeValidator(to_float)]
    low: Annotated[float, BeforeValidator(to_float)]
    close: Annotated[float, BeforeValidator(to_float)]
    volume: Annotated[float, BeforeValidator(to_float)]
    dividends: Annotated[Optional[float], BeforeValidator(to_float), Field(None)]
    stock_splits: Annotated[Optional[float], BeforeValidator(to_float), Field(None)]
