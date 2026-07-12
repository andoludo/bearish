from typing import List

from pydantic import Field, BaseModel

from bearish.exceptions import TickerNotFoundError
from bearish.models.assets.crypto import Crypto
from bearish.models.assets.currency import Currency
from bearish.models.assets.equity import Equity
from bearish.models.assets.etfs import Etf
from bearish.models.assets.index import Index
from bearish.models.base import BaseAssets, Ticker


class FailedQueryAssets(BaseModel):
    symbols: List[Ticker] = Field(default_factory=list)


class Assets(BaseAssets):
    equities: List[Equity] = Field(default_factory=list)
    cryptos: List[Crypto] = Field(default_factory=list)
    etfs: List[Etf] = Field(default_factory=list)
    currencies: List[Currency] = Field(default_factory=list)
    index: List[Index] = Field(default_factory=list)
    failed_query: FailedQueryAssets = Field(default_factory=FailedQueryAssets)

    def get_one_equity(self) -> Equity:
        if not self.equities:
            raise TickerNotFoundError("No equities found")
        return self.equities[0]

    def is_empty(self) -> bool:
        return not any(
            [self.equities, self.cryptos, self.etfs, self.currencies, self.index]
        )

    def add(self, assets: "Assets") -> None:
        self.equities.extend(assets.equities)
        self.cryptos.extend(assets.cryptos)
        self.etfs.extend(assets.etfs)
        self.currencies.extend(assets.currencies)
        self.index.extend(assets.index)

    def symbols(self) -> List[Ticker]:
        return [
            Ticker(symbol=asset.symbol, source=asset.source, exchange=asset.exchange)
            for asset in self.equities
            + self.cryptos
            + self.etfs
            + self.currencies
            + self.index
        ]
