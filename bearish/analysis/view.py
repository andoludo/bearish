import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import plotly.graph_objects as go  # type: ignore
from pydantic import BaseModel, Field

from bearish.analysis.figures import plot
from bearish.models.assets.base import ComponentDescription
from bearish.models.base import Ticker
from bearish.models.price.prices import Prices
from bearish.models.query.query import AssetQuery, Symbols

if TYPE_CHECKING:
    from bearish.interface.interface import BearishDbBase


def _remove_alpha_numeric(string: Optional[str] = None) -> str:
    if not string:
        return ""
    return re.sub(r"[^a-zA-Z0-9]", "_", string)


class View(ComponentDescription):
    view_name: Optional[str] = None

    def set_view_name(self, view_name: str) -> None:
        self.view_name = view_name

    def plot(self, bearish_db: "BearishDbBase") -> None:
        prices_ = bearish_db.read_series(
            AssetQuery(  # type: ignore
                symbols=Symbols(  # type: ignore
                    equities=[
                        Ticker(
                            symbol=self.symbol,
                            source=self.source,
                            exchange=self.exchange,
                        )
                    ]
                )
            ),
            months=12,
        )
        prices = Prices(prices=prices_).to_dataframe()
        figure = plot(prices, self.symbol, self.name)
        self.save_figure(figure)

    def save_figure(self, figure: go.Figure) -> None:
        now = datetime.now()
        formatted = now.strftime("%Y_%m_%d_%H_%M_%S")
        view_path = Path.cwd().joinpath(
            f"view_{_remove_alpha_numeric(self.view_name).lower()}_{formatted}"
        )
        view_path.mkdir(parents=True, exist_ok=True)
        figure.write_html(
            view_path.joinpath(f"{_remove_alpha_numeric(self.symbol).lower()}.html")
        )


class BaseViews(BaseModel):
    view_name: str
    query: str

    def compute(self, bearish_db: "BearishDbBase") -> None:
        views = bearish_db.read_views(self.query)
        for view in views:
            view.set_view_name(self.view_name)
            view.plot(bearish_db)
        bearish_db.write_views(views)


class TestView(BaseViews):
    view_name: str = "Test views"
    query: str = """SELECT symbol, name, source, isin FROM analysis"""


class DefensiveIndustries(BaseViews):
    view_name: str = "defensive_industries"
    query: str = """SELECT symbol, name, source, isin FROM analysis 
    WHERE positive_free_cash_flow=1 
    AND positive_net_income=1 
    AND positive_operating_income=1 
    AND quarterly_positive_free_cash_flow=1 
    AND quarterly_positive_net_income=1 
    AND quarterly_positive_operating_income=1 
    AND growing_net_income=1 
    AND quarterly_operating_cash_flow_is_higher_than_net_income=1 
    AND operating_cash_flow_is_higher_than_net_income=1
	AND rsi_last_value IS NOT NULL
	AND market_capitalization > 3000000000
	AND industry IN (
  'Food & Staples Retailing',
  'Packaged Foods',
  'Grocery Stores',
  'Household Products',
  'Household & Personal Products',
  'Confectioners',
  'Beverages',
  'Beverages - Non - Alcoholic',
  'Beverages - Wineries & Distilleries',
  'Pharmaceuticals',
  'Health Care Providers & Services',
  'Health Care Equipment & Supplies',
  'Healthcare Plans',
  'Medical Devices',
  'Medical Instruments & Supplies',
  'Medical Care Facilities',
  'Diagnostics & Research',
  'Drug Manufacturers - General',
  'Drug Manufacturers - Specialty & Generic',
  'Pharmaceutical Retailers',
  'Health Information Services',
  'Medical Distribution',
  'Electric Utilities',
  'Gas Utilities',
  'Water Utilities',
  'Utilities - Diversified',
  'Utilities - Regulated Electric',
  'Utilities - Regulated Gas',
  'Utilities - Renewable',
  'Utilities - Independent Power Producers',
  'Waste Management',
  'Pollution & Treatment Controls',
  'Security & Protection Services',
  'Insurance',
  'Insurance - Property & Casual')
	ORDER BY price_per_earning_ratio"""


class ViewsFactory(BaseModel):
    views: list[BaseViews] = Field(default_factory=lambda: [DefensiveIndustries()])  # type: ignore

    def compute(self, bearish_db: "BearishDbBase") -> None:
        for view in self.views:
            view.compute(bearish_db)
