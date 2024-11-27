from typing import Annotated, List

from pydantic import BaseModel, model_validator, BeforeValidator, Field

from bearish.utils.utils import remove_duplicates


class BaseAssetQuery(BaseModel):
    @model_validator(mode="after")
    def validate_query(self) -> "AssetQuery":
        if all(not getattr(self, field) for field in self.model_fields):
            raise ValueError("At least one query parameter must be provided")
        return self



class AssetQuery(BaseAssetQuery):
    countries: Annotated[
        List[str], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    symbols: Annotated[
        List[str], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    def update_symbols(self, symbols: list[str]) -> None:
        self.symbols = list(set(self.symbols + symbols))
