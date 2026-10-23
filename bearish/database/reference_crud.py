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
    EquitySnapshotORM,
    EtfExposureORM,
    EtfSnapshotORM,
    Holding13FORM,
    Holding13FSummaryORM,
    InsiderTransactionORM,
    Ownership13DGORM,
    SectorAliasORM,
    SectorCommoditySensitivityORM,
)
from bearish.macro.commodities import Commodity, CountryCommodityExposure
from bearish.macro.links import CountryAlias, CountryRef, EtfExposure, SectorCommoditySensitivity
from bearish.macro.sectors import SectorAlias
from bearish.models.assets.snapshots import EquitySnapshot, EtfSnapshot, Snapshots
from bearish.models.sec.holdings import Holding13F, Holding13FSummary, Ownership13DG
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

    # snapshots -----------------------------------------------------------

    def _write_snapshots(self, snapshots: Snapshots) -> None:
        self._upsert(EquitySnapshotORM, [s.model_dump() for s in snapshots.equities])
        self._upsert(EtfSnapshotORM, [s.model_dump() for s in snapshots.etfs])

    def _read_equity_snapshots(self, symbol: Optional[str] = None) -> List[EquitySnapshot]:
        return self._select(EquitySnapshotORM, EquitySnapshot, symbol=symbol)

    def _read_etf_snapshots(self, symbol: Optional[str] = None) -> List[EtfSnapshot]:
        return self._select(EtfSnapshotORM, EtfSnapshot, symbol=symbol)

    # insiders ------------------------------------------------------------

    def _write_insider_transactions(self, transactions: List[InsiderTransaction]) -> None:
        self._upsert(InsiderTransactionORM, [t.model_dump() for t in transactions])

    def _read_insider_transactions(self, symbol: Optional[str] = None) -> List[InsiderTransaction]:
        return self._select(InsiderTransactionORM, InsiderTransaction, symbol=symbol)

    def _write_holdings13f(self, holdings: List[Holding13F]) -> None:
        self._upsert(Holding13FORM, [h.model_dump() for h in holdings])

    def _read_holdings13f(self, symbol: Optional[str] = None, manager_cik: Optional[str] = None) -> List[Holding13F]:
        return self._select(Holding13FORM, Holding13F, symbol=symbol, manager_cik=manager_cik)

    def _write_holdings13f_summary(self, summaries: List[Holding13FSummary]) -> None:
        self._upsert(Holding13FSummaryORM, [s.model_dump() for s in summaries])

    def _read_holdings13f_summary(
        self, symbol: Optional[str] = None, cusip: Optional[str] = None
    ) -> List[Holding13FSummary]:
        return self._select(Holding13FSummaryORM, Holding13FSummary, symbol=symbol, cusip=cusip)

    def _write_ownership13dg(self, rows: List[Ownership13DG]) -> None:
        self._upsert(Ownership13DGORM, [r.model_dump() for r in rows])

    def _read_ownership13dg(self, symbol: Optional[str] = None) -> List[Ownership13DG]:
        return self._select(Ownership13DGORM, Ownership13DG, symbol=symbol)

    # linking -------------------------------------------------------------

    def _write_country_references(self, refs: List[CountryRef], aliases: List[CountryAlias]) -> None:
        self._upsert(CountryRefORM, [r.model_dump() for r in refs])
        self._upsert(CountryAliasORM, [a.model_dump() for a in aliases])

    def _read_country_references(self) -> List[CountryRef]:
        return self._select(CountryRefORM, CountryRef)

    def _write_sector_aliases(self, aliases: List[SectorAlias]) -> None:
        self._upsert(SectorAliasORM, [a.model_dump() for a in aliases])

    def _read_sector_aliases(self, level: Optional[str] = None) -> List[SectorAlias]:
        return self._select(SectorAliasORM, SectorAlias, level=level)

    def _write_sector_sensitivities(self, sensitivities: List[SectorCommoditySensitivity]) -> None:
        self._upsert(SectorCommoditySensitivityORM, [s.model_dump() for s in sensitivities])

    def _read_sector_sensitivities(self, commodity: Optional[str] = None) -> List[SectorCommoditySensitivity]:
        return self._select(SectorCommoditySensitivityORM, SectorCommoditySensitivity, commodity=commodity)

    def _write_etf_exposures(self, exposures: List[EtfExposure]) -> None:
        self._upsert(EtfExposureORM, [e.model_dump() for e in exposures])

    def _read_etf_exposures(self, symbol: Optional[str] = None, entity: Optional[str] = None) -> List[EtfExposure]:
        return self._select(EtfExposureORM, EtfExposure, symbol=symbol, entity=entity)
