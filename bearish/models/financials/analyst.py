from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from bearish.models.base import DataSourceBase
from bearish.utils.utils import to_float, to_int


class PriceTarget(DataSourceBase):
    """Snapshot of analyst price targets; `date` is the fetch date, so a
    history accumulates across runs."""

    target_mean: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Mean analyst price target"),
    ]
    target_high: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Highest analyst price target"),
    ]
    target_low: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Lowest analyst price target"),
    ]
    target_median: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(default=None, description="Median analyst price target"),
    ]
    number_of_analysts: Annotated[
        Optional[int],
        BeforeValidator(to_int),
        Field(default=None, description="Number of analyst opinions"),
    ]
    recommendation_mean: Annotated[
        Optional[float],
        BeforeValidator(to_float),
        Field(
            default=None,
            description="Mean recommendation score as provided by the source "
            "(e.g. 1=strong buy .. 5=sell)",
        ),
    ]
    recommendation_key: Annotated[
        Optional[str],
        Field(default=None, description="Recommendation label, e.g. 'buy'"),
    ]


class AnalystRecommendation(DataSourceBase):
    """One row of the provider's recommendation trend; `date` is the fetch
    date and `period` the provider's relative month bucket (e.g. '0m', '-1m')."""

    period: str = Field(description="Relative period bucket, e.g. '0m', '-1m'")
    strong_buy: Annotated[
        Optional[int],
        BeforeValidator(to_int),
        Field(default=None, description="Number of strong-buy ratings"),
    ]
    buy: Annotated[
        Optional[int],
        BeforeValidator(to_int),
        Field(default=None, description="Number of buy ratings"),
    ]
    hold: Annotated[
        Optional[int],
        BeforeValidator(to_int),
        Field(default=None, description="Number of hold ratings"),
    ]
    sell: Annotated[
        Optional[int],
        BeforeValidator(to_int),
        Field(default=None, description="Number of sell ratings"),
    ]
    strong_sell: Annotated[
        Optional[int],
        BeforeValidator(to_int),
        Field(default=None, description="Number of strong-sell ratings"),
    ]
