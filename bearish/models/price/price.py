from math import isnan
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from bearish.models.base import DataSourceBase
from bearish.utils.utils import to_float


class Price(DataSourceBase):
    open: Annotated[float, BeforeValidator(to_float), Field(None)]
    high: Annotated[float, BeforeValidator(to_float), Field(None)]
    low: Annotated[float, BeforeValidator(to_float), Field(None)]
    close: Annotated[float, BeforeValidator(to_float)]
    volume: Annotated[float, BeforeValidator(to_float), Field(None)]
    dividends: Annotated[Optional[float], BeforeValidator(to_float), Field(None)]
    stock_splits: Annotated[Optional[float], BeforeValidator(to_float), Field(None)]

    def valid(self) -> bool:
        return not any(
            isnan(field)
            for field in [self.open, self.high, self.low, self.close, self.volume]
        )
