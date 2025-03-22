from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from bearish.models.base import DataSourceBase
from bearish.utils.utils import to_float


class EarningsDate(DataSourceBase):
    eps_estimate: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Estimated EPS"),
    ]
    eps_reported: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Reported EPS"),
    ]
    revenue_estimate: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Estimated Revenue"),
    ]
    revenue_reported: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Reported Revenue"),
    ]
