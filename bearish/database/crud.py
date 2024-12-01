from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import List, TYPE_CHECKING, Type, Union, Any

from dateutil.relativedelta import relativedelta  # type: ignore
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Engine, insert
from sqlmodel import Session, select
from sqlmodel.main import SQLModel

from bearish.database.schemas import (
    EquityORM,
    CurrencyORM,
    CryptoORM,
    EtfORM,
    FinancialMetricsORM,
    CashFlowORM,
    BalanceSheetORM,
    PriceORM,
    SourcesORM,
)
from bearish.database.scripts.upgrade import upgrade
from bearish.interface.interface import BearishDbBase
from bearish.models.financials.balance_sheet import BalanceSheet

from bearish.models.financials.base import Financials
from bearish.models.assets.assets import Assets
from bearish.models.financials.cash_flow import CashFlow
from bearish.models.financials.metrics import FinancialMetrics
from bearish.models.price.price import Price

if TYPE_CHECKING:
    from bearish.models.query.query import AssetQuery


class BearishDb(BearishDbBase):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    database_path: Path

    @cached_property
    def _engine(self) -> Engine:
        database_url = f"sqlite:///{Path(self.database_path)}"
        upgrade(database_url)
        engine = create_engine(database_url)
        return engine

    def model_post_init(self, __context: Any) -> None:  # noqa: ANN401
        self._engine  # noqa: B018

    def _write_assets(self, assets: Assets) -> None:
        with Session(self._engine) as session:
            objects_orm = (
                [EquityORM(**object.model_dump()) for object in assets.equities]
                + [CurrencyORM(**object.model_dump()) for object in assets.currencies]
                + [CryptoORM(**object.model_dump()) for object in assets.cryptos]
                + [EtfORM(**object.model_dump()) for object in assets.etfs]
            )

            session.add_all(objects_orm)
            session.commit()

    def _write_series(self, series: List["Price"]) -> None:
        with Session(self._engine) as session:
            stmt = (
                insert(PriceORM)
                .prefix_with("OR REPLACE")
                .values([serie.model_dump() for serie in series])
            )

            session.exec(stmt)  # type: ignore
            session.commit()

    def _write_financials(self, financials: Financials) -> None:
        self._write_financials_series(financials.financial_metrics, FinancialMetricsORM)
        self._write_financials_series(financials.cash_flows, CashFlowORM)
        self._write_financials_series(financials.balance_sheets, BalanceSheetORM)

    def _write_financials_series(
        self,
        series: Union[List[CashFlow], List[FinancialMetrics], List[BalanceSheet]],
        table: Type[SQLModel],
    ) -> None:
        if not series:
            return None
        with Session(self._engine) as session:
            stmt = (
                insert(table)
                .prefix_with("OR REPLACE")
                .values([serie.model_dump() for serie in series])
            )
            session.exec(stmt)  # type: ignore
            session.commit()

    def _read_series(self, query: "AssetQuery", months: int = 1) -> List[Price]:
        end_date = datetime.now()
        start_date = end_date - relativedelta(month=months)
        with Session(self._engine) as session:
            query_ = select(PriceORM)
            query_ = query_.where(PriceORM.symbol.in_(query.symbols.all())).where(  # type: ignore
                PriceORM.date.between(start_date, end_date)  # type: ignore
            )
            series = session.exec(query_).all()
            return [Price.model_validate(serie) for serie in series]

    def _read_financials(self, query: "AssetQuery") -> Financials:
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

    def _read_assets(self, query: "AssetQuery") -> Assets:
        with Session(self._engine) as session:
            from bearish.models.assets.equity import Equity
            from bearish.models.assets.crypto import Crypto
            from bearish.models.assets.currency import Currency
            from bearish.models.assets.etfs import Etf

            equities = self._read_asset_type(session, Equity, EquityORM, query)
            currencies = self._read_asset_type(session, Currency, CurrencyORM, query)
            cryptos = self._read_asset_type(session, Crypto, CryptoORM, query)
            etfs = self._read_asset_type(session, Etf, EtfORM, query)
            return Assets(
                equities=equities, currencies=currencies, cryptos=cryptos, etfs=etfs
            )

    def _read_asset_type(
        self,
        session: Session,
        table: Type[BaseModel],
        orm_table: Type[
            Union[
                EquityORM,
                CurrencyORM,
                CryptoORM,
                EtfORM,
                BalanceSheetORM,
                CashFlowORM,
                FinancialMetricsORM,
            ]
        ],
        query: "AssetQuery",
    ) -> List[BaseModel]:
        if query.symbols.all():
            query_ = select(orm_table).where(orm_table.symbol.in_(query.symbols.all()))  # type: ignore
        else:
            query_ = select(orm_table)
            if query.countries:
                query_ = query_.where(orm_table.country.in_(query.countries))  # type: ignore

        assets = session.exec(query_).all()
        return [table.model_validate(asset) for asset in assets]

    def _read_sources(self) -> List[str]:
        with Session(self._engine) as session:
            query_ = select(SourcesORM).distinct()
            sources = session.exec(query_).all()
            return [source.source for source in sources]

    def _write_source(self, source: str) -> None:
        with Session(self._engine) as session:
            stmt = (
                insert(SourcesORM)
                .prefix_with("OR REPLACE")
                .values([{"source": source}])
            )

            session.exec(stmt)  # type: ignore
            session.commit()
