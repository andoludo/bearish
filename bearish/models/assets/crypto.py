from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from bearish.models.assets.base import BaseComponent
from bearish.utils.utils import to_string


class Crypto(BaseComponent):
    cryptocurrency: Annotated[
        Optional[str],
        BeforeValidator(to_string),
        Field(None, description="Name of the cryptocurrency"),
    ]
