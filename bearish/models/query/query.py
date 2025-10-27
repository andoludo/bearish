from typing import Annotated, List, Any, Callable

from pydantic import BaseModel, model_validator, BeforeValidator, Field

from bearish.models.assets.assets import Assets
from bearish.models.base import BaseAssets, Ticker
from bearish.utils.utils import remove_duplicates, remove_duplicates_string


class BaseAssetQuery(BaseModel):
    @model_validator(mode="after")
    def validate_query(self) -> Any:
        if all(not getattr(self, field) for field in self.model_fields):
            raise ValueError("At least one query parameter must be provided")
        return self


class Symbols(BaseAssets):
    equities: Annotated[
        List[Ticker], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    etfs: Annotated[
        List[Ticker], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    currencies: Annotated[
        List[Ticker], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    cryptos: Annotated[
        List[Ticker], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]
    index: Annotated[
        List[Ticker], BeforeValidator(remove_duplicates), Field(default_factory=list)
    ]

    def filter(self, func: Callable[[Ticker], Any]) -> "Symbols":
        equities = [e for e in self.equities if func(e)]
        etfs = [e for e in self.etfs if func(e)]
        currencies = [e for e in self.currencies if func(e)]
        cryptos = [e for e in self.cryptos if func(e)]
        index = [e for e in self.index if func(e)]
        return Symbols(
            equities=equities,
            etfs=etfs,
            currencies=currencies,
            cryptos=cryptos,
            index=index,
        )

    def equities_symbols(self) -> List[str]:
        return [t.symbol for t in self.equities]

    def etfs_symbols(self) -> List[str]:
        return [t.symbol for t in self.etfs]

    def empty(self) -> bool:
        return not any(
            [
                self.equities,
                self.etfs,
                self.currencies,
                self.cryptos,
                self.index,
            ]
        )

    def all(self) -> List[str]:
        return [
            t.symbol
            for t in self.equities
            + self.etfs
            + self.currencies
            + self.cryptos
            + self.index
        ]


class AssetQuery(BaseAssetQuery):
    countries: Annotated[
        List[str],
        BeforeValidator(remove_duplicates_string),
        Field(default_factory=list),
    ]
    exchanges: Annotated[
        List[str],
        BeforeValidator(remove_duplicates_string),
        Field(default_factory=list),
    ]
    excluded_sources: Annotated[
        List[str],
        BeforeValidator(remove_duplicates_string),
        Field(default_factory=list),
    ]
    symbols: Symbols = Field(default=Symbols())  # type: ignore

    def update_symbols(self, assets: Assets) -> None:
        for field in assets.model_fields:
            if field == "failed_query":
                continue
            symbols = sorted(
                {
                    Ticker(symbol=asset.symbol, exchange=asset.exchange)
                    for asset in getattr(assets, field)
                }
                | set(getattr(self.symbols, field)),
                key=lambda x: x.symbol,
            )
            setattr(
                self.symbols,
                field,
                symbols,
            )
