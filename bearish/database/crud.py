import logging
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import List, TYPE_CHECKING, Type, Union, Any, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Engine, create_engine, insert
from sqlmodel import Session, select
from sqlmodel.main import SQLModel

from bearish.analysis.analysis import Analysis
from bearish.analysis.view import View
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
    TrackerORM,
    EarningsDateORM,
    AnalysisORM,
    ViewORM,
    QuarterlyFinancialMetricsORM,
    QuarterlyCashFlowORM,
    QuarterlyBalanceSheetORM,
)
from bearish.database.scripts.upgrade import upgrade
from bearish.exchanges.exchanges import ExchangeQuery
from bearish.interface.interface import BearishDbBase
from bearish.models.assets.assets import Assets
from bearish.models.base import Tracker, TrackerQuery, Ticker
from bearish.models.financials.balance_sheet import BalanceSheet, QuarterlyBalanceSheet
from bearish.models.financials.base import Financials
from bearish.models.financials.cash_flow import CashFlow, QuarterlyCashFlow
from bearish.models.financials.earnings_date import EarningsDate
from bearish.models.financials.metrics import (
    FinancialMetrics,
    QuarterlyFinancialMetrics,
)
from bearish.models.price.price import Price

if TYPE_CHECKING:
    from bearish.models.query.query import AssetQuery

logger = logging.getLogger(__name__)


class BearishDb(BearishDbBase):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    database_path: Path

    @cached_property
    def _engine(self) -> Engine:
        database_url = f"sqlite:///{Path(self.database_path)}"
        upgrade(database_url)
        engine = create_engine(database_url)
        return engine

    def model_post_init(self, __context: Any) -> None:
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
        self._write_financials_series(financials.earnings_date, EarningsDateORM)
        self._write_financials_series(
            financials.quarterly_financial_metrics, QuarterlyFinancialMetricsORM
        )
        self._write_financials_series(
            financials.quarterly_cash_flows, QuarterlyCashFlowORM
        )
        self._write_financials_series(
            financials.quarterly_balance_sheets, QuarterlyBalanceSheetORM
        )

    def _write_financials_series(
        self,
        series: Union[
            List[CashFlow],
            List[FinancialMetrics],
            List[BalanceSheet],
            List[EarningsDate],
            List[QuarterlyCashFlow],
            List[QuarterlyFinancialMetrics],
            List[QuarterlyBalanceSheet],
        ],
        table: Type[SQLModel],
    ) -> None:
        if not series:
            logger.warning(f"No data found for '{[serie.symbol for serie in series]}'")
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
        start_date = end_date - pd.Timedelta(days=months * 31)
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
            quarterly_financial_metrics = self._read_asset_type(
                session, QuarterlyFinancialMetrics, QuarterlyFinancialMetricsORM, query
            )
            quarterly_cash_flows = self._read_asset_type(
                session, QuarterlyCashFlow, QuarterlyCashFlowORM, query
            )
            quarterly_balance_sheets = self._read_asset_type(
                session, QuarterlyBalanceSheet, QuarterlyBalanceSheetORM, query
            )
            return Financials(
                financial_metrics=financial_metrics,
                cash_flows=cash_flows,
                balance_sheets=balance_sheets,
                quarterly_financial_metrics=quarterly_financial_metrics,
                quarterly_cash_flows=quarterly_cash_flows,
                quarterly_balance_sheets=quarterly_balance_sheets,
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
                QuarterlyBalanceSheetORM,
                QuarterlyCashFlowORM,
                QuarterlyFinancialMetricsORM,
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
            if query.exchanges:
                query_ = query_.where(orm_table.exchange.in_(query.exchanges))  # type: ignore
        if query.excluded_sources:
            query_ = query_.where(~orm_table.source.in_(query.excluded_sources))  # type: ignore

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

    def _write_analysis(self, analysis: Analysis) -> None:
        with Session(self._engine) as session:
            stmt = (
                insert(AnalysisORM)
                .prefix_with("OR REPLACE")
                .values(analysis.model_dump())
            )
            session.exec(stmt)  # type: ignore
            session.commit()
            session.commit()

    def _read_analysis(self, ticker: Ticker) -> Optional[Analysis]:
        with Session(self._engine) as session:
            query = select(AnalysisORM).where(AnalysisORM.symbol == ticker.symbol)
            analysis = session.exec(query).first()
            if not analysis:
                return None
            return Analysis.model_validate(analysis)

    def _write_tracker(self, tracker: Tracker) -> None:
        with Session(self._engine) as session:
            query = (
                select(TrackerORM)
                .where(TrackerORM.symbol == tracker.symbol)
                .where(TrackerORM.source == tracker.source)
            )
            tracker_orm = session.exec(query).first()
            if tracker_orm:
                tracker_orm.financials = tracker.financials or tracker_orm.financials
                tracker_orm.price = tracker.price or tracker_orm.price
                session.commit()
            else:
                stmt = (
                    insert(TrackerORM)
                    .prefix_with("OR REPLACE")
                    .values(tracker.model_dump())
                )
                session.exec(stmt)  # type: ignore
                session.commit()

    def _read_tracker(self, tracker_query: TrackerQuery) -> List[Ticker]:
        with Session(self._engine) as session:
            query = select(TrackerORM.symbol, TrackerORM.exchange, TrackerORM.source)
            if tracker_query.exchange:
                query = query.where(TrackerORM.exchange == tracker_query.exchange)
            if tracker_query.financials:
                query = query.where(TrackerORM.financials == tracker_query.financials)
            if tracker_query.price:
                query = query.where(TrackerORM.price == tracker_query.price)
            tracker_orm = session.exec(query).all()
            return [
                Ticker(symbol=t[0], exchange=t[1], source=t[2]) for t in tracker_orm
            ]

    def _get_tickers(self, exchange_query: ExchangeQuery) -> List[Ticker]:
        if not exchange_query.sources:
            query = f"""SELECT symbol, exchange from equity where {exchange_query.to_suffixes_sql_statement()} 
                OR exchange IN {exchange_query.to_aliases_sql_statement()};"""
        else:
            query = f"""SELECT symbol, exchange from equity where source IN {exchange_query.to_sources_sql_statement()} 
            AND ( {exchange_query.to_suffixes_sql_statement()} 
                 OR exchange IN {exchange_query.to_aliases_sql_statement()});"""

        symbols = pd.read_sql(
            query,
            con=self._engine,
        )
        return [
            Ticker(symbol=symbol["symbol"], exchange=symbol["exchange"])
            for symbol in symbols.to_dict(orient="records")
        ]

    def _read_views(self, query: str) -> List[View]:
        views = pd.read_sql(
            query,
            con=self._engine,
        )
        return [
            View.model_validate(record) for record in views.to_dict(orient="records")
        ]

    def _write_views(self, views: List[View]) -> None:
        with Session(self._engine) as session:
            stmt = (
                insert(ViewORM)
                .prefix_with("OR REPLACE")
                .values([view.model_dump() for view in views])
            )

            session.exec(stmt)  # type: ignore
            session.commit()

    def _read_query(self, query: str) -> pd.DataFrame:
        return pd.read_sql(
            query,
            con=self._engine,
        )
