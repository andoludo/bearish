from typing import Tuple

from pydantic import BaseModel, ConfigDict


class Locator(BaseModel):
    by: str
    value: str
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def to_tuple(self) -> Tuple[str, str]:
        return (self.by, self.value)

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Locator):
            raise NotImplementedError
        return self.value == other.value
