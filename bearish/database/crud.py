from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import List, TYPE_CHECKING, Optional

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, Engine, insert
from sqlmodel import Session, select

from bearish.database.schemas import EquityORM, DailyOhlcvORM, FinancialsORM
from bearish.database.scripts.upgrade import upgrade
from bearish.database.settings import DATABASE_PATH
from bearish.financials import Financials
from bearish.equities import DailyOhlcv
from bearish.models.base import Equity

if TYPE_CHECKING:
    from bearish.equities import Equity, DailyOhlcv, EquityQuery


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

    def write_equities(self, equities: List["Equity"]) -> None:
        with Session(self._engine) as session:
            equities_orm = [EquityORM.model_validate(equity) for equity in equities]
            session.add_all(equities_orm)
            session.commit()

    def write_series(self, series: List["DailyOhlcv"]) -> None:
        with Session(self._engine) as session:
            stmt = (
                insert(DailyOhlcvORM)
                .prefix_with("OR IGNORE")
                .values([serie.model_dump() for serie in series])
            )
            session.exec(stmt)
            session.commit()

    def write_financials(self, series: List["Financials"]) -> None:
        with Session(self._engine) as session:
            stmt = (
                insert(FinancialsORM)
                .prefix_with("OR IGNORE")
                .values([serie.model_dump() for serie in series])
            )
            session.exec(stmt)
            session.commit()

    def read_series(
        self, equities: List["Equity"], months: int = 1
    ) -> List["DailyOhlcv"]:
        end_date = datetime.now()
        start_date = end_date - relativedelta(month=months)
        with Session(self._engine) as session:
            query_ = select(DailyOhlcvORM)
            query_ = query_.where(
                DailyOhlcvORM.symbol.in_([equity.symbol for equity in equities])
            ).where(DailyOhlcvORM.date.between(start_date, end_date))
            series = session.exec(query_).all()
            return [DailyOhlcv.model_validate(serie) for serie in series]

    def read_financials(
        self, equities: List["Equity"]
    ) -> List["Financials"]:
        with Session(self._engine) as session:
            query_ = select(FinancialsORM)
            query_ = query_.where(
                FinancialsORM.symbol.in_([equity.symbol for equity in equities])
            )
            financials = session.exec(query_).all()
            return [Financials.model_validate(financial) for financial in financials]

    def read_equities(self, query: "EquityQuery") -> List["Equity"]:
        from bearish.equities import Equity

        with Session(self._engine) as session:
            if query.symbols:
                query_ = select(EquityORM).where(EquityORM.symbol.in_(query.symbols))
            else:
                query_ = select(EquityORM)
                if query.countries:
                    query_ = query_.where(EquityORM.country.in_(query.countries))
                if query.exchanges:
                    query_ = query_.where(EquityORM.exchange.in_(query.exchanges))
                if query.markets:
                    query_ = query_.where(EquityORM.market.in_(query.markets))
            equities = session.exec(query_).all()
            return [Equity.model_validate(equity) for equity in equities]
