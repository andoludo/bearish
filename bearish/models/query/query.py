from typing import Annotated, List, Any

from pydantic import BaseModel, model_validator, BeforeValidator, Field

from bearish.models.assets.assets import Assets
from bearish.models.base import BaseAssets
from bearish.utils.utils import remove_duplicates


class BaseAssetQuery(BaseModel):
    @model_validator(mode="after")
    def validate_query(self) -> Any:  # noqa: ANN401
        if all(not getattr(self, field) for field in self.model_fields):
            raise ValueError("At least one query parameter must be provided")
        return self


class Symbols(BaseAssets):
    equities: Annotated[
        List[str], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    etfs: Annotated[
        List[str], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    currencies: Annotated[
        List[str], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    cryptos: Annotated[
        List[str], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]

    def empty(self) -> bool:
        return not any(
            [
                self.equities,
                self.etfs,
                self.currencies,
                self.cryptos,
            ]
        )

    def all(self) -> List[str]:
        return self.equities + self.etfs + self.currencies + self.cryptos


class AssetQuery(BaseAssetQuery):
    countries: Annotated[
        List[str], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    exchanges: Annotated[
        List[str], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    symbols: Symbols = Field(default=Symbols())  # type: ignore

    def update_symbols(self, assets: Assets) -> None:
        for field in assets.model_fields:
            symbols = sorted(
                {asset.symbol for asset in getattr(assets, field)}
                | set(getattr(self.symbols, field))
            )
            setattr(
                self.symbols,
                field,
                symbols,
            )
