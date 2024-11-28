from typing import List

from pydantic import Field

from bearish.models.assets.crypto import Crypto
from bearish.models.assets.currency import Currency
from bearish.models.assets.equity import Equity
from bearish.models.assets.etfs import Etf
from bearish.models.base import BaseAssets


class Assets(BaseAssets):
    equities: List[Equity] = Field(default_factory=list)
    cryptos: List[Crypto] = Field(default_factory=list)
    etfs: List[Etf] = Field(default_factory=list)
    currencies: List[Currency] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            [
                self.equities,
                self.cryptos,
                self.etfs,
                self.currencies,
            ]
        )

    def add(self, assets: "Assets") -> None:
        self.equities.extend(assets.equities)
        self.cryptos.extend(assets.cryptos)
        self.etfs.extend(assets.etfs)
        self.currencies.extend(assets.currencies)
