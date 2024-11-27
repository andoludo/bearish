from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from bearish.models.assets.base import BaseComponent
from bearish.utils.utils import to_string


class Currency(BaseComponent):
    base_currency: Annotated[
        Optional[str], BeforeValidator(to_string), Field(default=None)
    ]
    quote_currency: Annotated[
        Optional[str], BeforeValidator(to_string), Field(default=None)
    ]
