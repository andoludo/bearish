import re
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import pandas as pd
import plotly.graph_objects as go  # type: ignore
from pydantic import BaseModel, Field

from bearish.analysis.figures import plot
from bearish.models.assets.base import ComponentDescription
from bearish.models.base import Ticker
from bearish.models.price.prices import Prices
from bearish.models.query.query import AssetQuery, Symbols
from bearish.utils.utils import to_dataframe

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

    def plot(
        self, bearish_db: "BearishDbBase", view_path: Path, show: bool = False
    ) -> None:
        query = AssetQuery(  # type: ignore
            symbols=Symbols(  # type: ignore
                equities=[
                    Ticker(
                        symbol=self.symbol,
                        source=self.source,
                        exchange=self.exchange,
                    )
                ]
            )
        )
        prices_ = bearish_db.read_series(
            query,
            months=12,
        )
        prices = Prices(prices=prices_).to_dataframe()
        earnings_date = to_dataframe(bearish_db.read_earnings_date(query))
        dates = None
        if not earnings_date.empty:
            dates = earnings_date.index.to_series()[
                (earnings_date.index >= prices.index[0])
                & (earnings_date.index <= prices.index[-1] + pd.Timedelta(days=100))
            ]
        figure = plot(
            prices,
            self.symbol,
            self.name,
            dates=dates,
        )
        if show:
            figure.show()
        else:
            self.save_figure(figure, view_path)

    def save_figure(self, figure: go.Figure, view_path: Path) -> None:

        figure.write_html(view_path.joinpath(f"{self.name}.html"))


class BaseViews(BaseModel):
    query: str

    def compute(self, bearish_db: "BearishDbBase", view_path: Path) -> None:
        views = bearish_db.read_views(self.query)
        for view in views:
            view.set_view_name(self.view_name)
            view.plot(bearish_db, view_path)
        bearish_db.write_views(views)

    @property
    def view_name(self) -> str:
        return self.__class__.__name__.lower()


class TestView(BaseViews):
    query: str = """SELECT symbol, name, source, isin FROM analysis"""


class DefensiveLargeCapLoser(BaseViews):
    query: str = """SELECT symbol, name, source , last_month_max_growth FROM analysis 
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
	AND market_capitalization > 10000000000
	AND last_month_max_growth <0
	AND price_per_earning_ratio < 30
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
	ORDER BY last_month_max_growth ASC"""


class EuropeanLargeCapLoser(BaseViews):
    query: str = """SELECT symbol, name, source , last_month_max_growth, last_year_max_growth FROM analysis 
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
	AND market_capitalization > 10000000000
	AND last_month_max_growth <0
	AND price_per_earning_ratio < 30
	AND country IN (
    'Germany',
    'France',
    'Netherlands',
    'Belgium',
    'Italy',
    'Spain',
    'Switzerland',
    'Sweden',
    'Denmark',
    'Norway',
    'Finland',
    'Portugal',
    'Austria'
)
	ORDER BY last_month_max_growth ASC"""


class RisingStars(BaseViews):
    query: str = """SELECT 
    symbol, 
    name, 
    star_wow, 
    star_mom, 
    star_yoy, 
    country, 
    last_price
FROM 
    ANALYSIS
WHERE 
    positive_free_cash_flow = 1
    AND operating_cash_flow_is_higher_than_net_income = 1
    AND market_capitalization > 1000000000
    AND country IN ('Germany', 'United states','France')
ORDER BY 
    star_yoy DESC,
    last_price ASC
LIMIT 50;"""


class ViewsFactory(BaseModel):
    views: list[BaseViews] = Field(
        default_factory=lambda: [
            DefensiveLargeCapLoser(),
            EuropeanLargeCapLoser(),
            RisingStars(),
        ]
    )

    def compute(self, bearish_db: "BearishDbBase") -> None:
        for view in self.views:
            view.compute(bearish_db, self.view_path(view.view_name))

    def view_path(self, view_name: str) -> Path:
        now = datetime.now()
        formatted = now.strftime("%Y_%m_%d_%H_%M")
        view_path = Path.cwd().joinpath(
            f"view_{_remove_alpha_numeric(view_name).lower()}_{formatted}"
        )
        view_path.mkdir(parents=True, exist_ok=True)
        return view_path
