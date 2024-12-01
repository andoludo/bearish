import abc
from pathlib import Path
from typing import List

from pydantic import BaseModel, ConfigDict, validate_call

from bearish.models.assets.assets import Assets
from bearish.models.financials.base import Financials
from bearish.models.price.price import Price
from bearish.models.query.query import AssetQuery


class BearishDbBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    database_path: Path

    @validate_call
    def write_assets(self, assets: Assets) -> None:
        return self._write_assets(assets)

    @validate_call
    def write_series(self, series: List[Price]) -> None:
        return self._write_series(series)

    @validate_call
    def write_financials(self, financials: Financials) -> None:
        return self._write_financials(financials)

    @validate_call
    def read_series(self, query: AssetQuery, months: int = 1) -> List[Price]:
        return self._read_series(query, months)

    @validate_call
    def read_financials(self, query: AssetQuery) -> Financials:
        return self._read_financials(query)

    @validate_call
    def read_assets(self, query: AssetQuery) -> Assets:
        return self._read_assets(query)

    @validate_call
    def read_sources(self) -> List[str]:
        return self._read_sources()

    @validate_call
    def write_source(self, source: str) -> None:
        return self._write_source(source)

    @abc.abstractmethod
    def _write_assets(self, assets: Assets) -> None: ...

    @abc.abstractmethod
    def _write_series(self, series: List[Price]) -> None: ...

    @abc.abstractmethod
    def _write_financials(self, financials: Financials) -> None: ...

    @abc.abstractmethod
    def _read_series(self, query: AssetQuery, months: int = 1) -> List[Price]: ...

    @abc.abstractmethod
    def _read_financials(self, query: AssetQuery) -> Financials: ...

    @abc.abstractmethod
    def _read_assets(self, query: AssetQuery) -> Assets: ...

    @abc.abstractmethod
    def _write_source(self, source: str) -> None: ...

    @abc.abstractmethod
    def _read_sources(self) -> List[str]: ...
