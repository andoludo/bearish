"""Persistence for reference and linking tables (commodities, country
references, trade exposure, sector sensitivities, ETF exposure) and insider
transactions. All are simple upsert / filtered-read tables."""

from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import Engine, insert
from sqlmodel import Session, SQLModel, col, select

from bearish.database.schemas import (
    CommodityORM,
    CountryAliasORM,
    CountryCommodityExposureORM,
    CountryRefORM,
    EtfExposureORM,
    InsiderTransactionORM,
    SectorCommoditySensitivityORM,
)
from bearish.macro.commodities import Commodity, CountryCommodityExposure
from bearish.macro.links import CountryAlias, CountryRef, EtfExposure, SectorCommoditySensitivity
from bearish.models.sec.insider import InsiderTransaction
from bearish.utils.utils import batch

BATCH_SIZE = 5000
ModelT = TypeVar("ModelT", bound=BaseModel)


def _commodity_row(commodity: Commodity) -> Dict[str, Any]:
    row = commodity.model_dump()
    row["hs_codes"] = ",".join(commodity.hs_codes)
    row["sectors"] = ",".join(commodity.sectors)
    return row


def _commodity_from_row(row: CommodityORM) -> Commodity:
    data = row.model_dump()
    data["hs_codes"] = tuple(code for code in data["hs_codes"].split(",") if code)
    data["sectors"] = tuple(sector for sector in data["sectors"].split(",") if sector)
    return Commodity.model_validate(data)


class ReferenceCrudMixin:
    def _reference_engine(self) -> Engine:
        return self._engine  # type: ignore[attr-defined,no-any-return]

    def _upsert(self, orm: Type[SQLModel], rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        with Session(self._reference_engine()) as session:
            for chunk in batch(rows, BATCH_SIZE):
                session.exec(insert(orm).prefix_with("OR REPLACE"), params=chunk)
            session.commit()

    def _select(self, orm: Type[SQLModel], model: Type[ModelT], **filters: Optional[str]) -> List[ModelT]:
        statement = select(orm)
        for name, value in filters.items():
            if value is not None:
                statement = statement.where(col(getattr(orm, name)) == value)
        with Session(self._reference_engine()) as session:
            return [model.model_validate(row.model_dump()) for row in session.exec(statement).all()]

    # commodities ---------------------------------------------------------

    def _write_commodities(self, commodities: List[Commodity]) -> None:
        self._upsert(CommodityORM, [_commodity_row(c) for c in commodities])

    def _read_commodities(self) -> List[Commodity]:
        with Session(self._reference_engine()) as session:
            return [_commodity_from_row(row) for row in session.exec(select(CommodityORM)).all()]

    def _write_country_exposures(self, exposures: List[CountryCommodityExposure]) -> None:
        self._upsert(CountryCommodityExposureORM, [e.model_dump() for e in exposures])

    def _read_country_exposures(
        self, country: Optional[str] = None, commodity: Optional[str] = None
    ) -> List[CountryCommodityExposure]:
        return self._select(CountryCommodityExposureORM, CountryCommodityExposure, country=country, commodity=commodity)

    # insiders ------------------------------------------------------------

    def _write_insider_transactions(self, transactions: List[InsiderTransaction]) -> None:
        self._upsert(InsiderTransactionORM, [t.model_dump() for t in transactions])

    def _read_insider_transactions(self, symbol: Optional[str] = None) -> List[InsiderTransaction]:
        return self._select(InsiderTransactionORM, InsiderTransaction, symbol=symbol)

    # linking -------------------------------------------------------------

    def _write_country_references(self, refs: List[CountryRef], aliases: List[CountryAlias]) -> None:
        self._upsert(CountryRefORM, [r.model_dump() for r in refs])
        self._upsert(CountryAliasORM, [a.model_dump() for a in aliases])

    def _read_country_references(self) -> List[CountryRef]:
        return self._select(CountryRefORM, CountryRef)

    def _write_sector_sensitivities(self, sensitivities: List[SectorCommoditySensitivity]) -> None:
        self._upsert(SectorCommoditySensitivityORM, [s.model_dump() for s in sensitivities])

    def _read_sector_sensitivities(self, commodity: Optional[str] = None) -> List[SectorCommoditySensitivity]:
        return self._select(SectorCommoditySensitivityORM, SectorCommoditySensitivity, commodity=commodity)

    def _write_etf_exposures(self, exposures: List[EtfExposure]) -> None:
        self._upsert(EtfExposureORM, [e.model_dump() for e in exposures])

    def _read_etf_exposures(self, symbol: Optional[str] = None, entity: Optional[str] = None) -> List[EtfExposure]:
        return self._select(EtfExposureORM, EtfExposure, symbol=symbol, entity=entity)
