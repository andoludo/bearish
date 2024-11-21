from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import List, TYPE_CHECKING, Optional, cast

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, Engine, insert
from sqlmodel import Session, select

from bearish.database.schemas import (
    EquityORM,
    CurrencyORM,
    CryptoORM,
    EtfORM,
    FinancialMetricsORM,
    CashFlowORM,
    BalanceSheetORM,
    CandleStickORM,
)
from bearish.database.scripts.upgrade import upgrade
from bearish.database.settings import DATABASE_PATH


from bearish.models.base import Equity, Currency, CandleStick
from bearish.models.financials import FinancialMetrics, CashFlow, BalanceSheet
from bearish.sources.base import Assets, Financials
from bearish.database import schemas

if TYPE_CHECKING:
    from bearish.equities import Equity, DailyOhlcv, EquityQuery
    from bearish.main import AssetQuery


class BearishDb(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    database_path: Optional[str] = Field(None)

    @cached_property
    def _engine(self) -> Engine:
        self.database_path = self.database_path or DATABASE_PATH
        database_url = f"sqlite:///{Path(self.database_path)}"
        upgrade(database_url)
        engine = create_engine(database_url)
        return engine

    def write_assets(self, assets: Assets) -> None:
        with Session(self._engine) as session:
            objects_orm = (
                [EquityORM(**object.model_dump()) for object in assets.equities]
                + [CurrencyORM(**object.model_dump()) for object in assets.currencies]
                + [CryptoORM(**object.model_dump()) for object in assets.cryptos]
                + [EtfORM(**object.model_dump()) for object in assets.etfs]
            )

            session.add_all(objects_orm)
            session.commit()

    def write_series(self, series: List["CandleStick"]) -> None:
        with Session(self._engine) as session:
            stmt = (
                insert(CandleStickORM)
                .values([serie.model_dump() for serie in series])
            )
            session.exec(stmt)
            session.commit()

    def write_financials(self, financials: Financials) -> None:
        self._write_series(financials.financial_metrics, FinancialMetricsORM)
        self._write_series(financials.cash_flows, CashFlowORM)
        self._write_series(financials.balance_sheets, BalanceSheetORM)

    def _write_series(self, series: list, table: schemas.BaseTable):
        with Session(self._engine) as session:
            stmt = (
                insert(table)
                .prefix_with("OR IGNORE")
                .values([serie.model_dump() for serie in series])
            )
            session.exec(stmt)
            session.commit()

    def read_series(
        self, query: "AssetQuery", months: int = 1
    ) -> List["DailyOhlcv"]:
        end_date = datetime.now()
        start_date = end_date - relativedelta(month=months)
        with Session(self._engine) as session:
            query_ = select(CandleStickORM)
            query_ = query_.where(
                CandleStickORM.symbol.in_(query.symbols)
            ).where(CandleStickORM.date.between(start_date, end_date))
            series = session.exec(query_).all()
            return [CandleStick.model_validate(serie) for serie in series]

    def read_financials(self, query: "AssetQuery") -> Financials:
        with Session(self._engine) as session:
            financial_metrics = self._read_asset_type(
                session, FinancialMetrics, FinancialMetricsORM, query
            )
            cash_flows = self._read_asset_type(session, CashFlow, CashFlowORM, query)
            balance_sheets = self._read_asset_type(
                session, BalanceSheet, BalanceSheetORM, query
            )
            return Financials(
                financial_metrics=financial_metrics,
                cash_flows=cash_flows,
                balance_sheets=balance_sheets,
            )

    def read_assets(self, query: "AssetQuery") -> Assets:
        with Session(self._engine) as session:
            from bearish.models.base import CandleStick, Currency, Crypto, Etf, Equity

            equities = self._read_asset_type(session, Equity, EquityORM, query)
            currencies = self._read_asset_type(session, Currency, CurrencyORM, query)
            cryptos = self._read_asset_type(session, Crypto, CryptoORM, query)
            etfs = self._read_asset_type(session, Etf, EtfORM, query)
            return Assets(
                equities=equities, currencies=currencies, cryptos=cryptos, etfs=etfs
            )

    def _read_asset_type(
        self, session, table: schemas.BaseTable, orm_table, query: "AssetQuery"
    ) -> List:
        if query.symbols:
            query_ = select(orm_table).where(orm_table.symbol.in_(query.symbols))
        else:
            query_ = select(orm_table)
            if query.countries:
                query_ = query_.where(orm_table.country.in_(query.countries))
            if query.exchanges:
                query_ = query_.where(orm_table.exchange.in_(query.exchanges))
            if query.markets:
                query_ = query_.where(orm_table.market.in_(query.markets))
        assets = session.exec(query_).all()
        return [table.model_validate(asset) for asset in assets]
