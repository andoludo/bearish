import json
from pathlib import Path

import pandas as pd
from alpha_vantage.fundamentaldata import FundamentalData

from bearish.database.crud import BearishDb
from bearish.models.base import Equity
from bearish.equities import Equities, DailySeries, EquityQuery
from bearish.financials import Financials, ManyFinancials




def test_write_read_equities(equities: pd.DataFrame, bearish_db: BearishDb) -> None:
    equities = Equities.from_dataframe(equities)
    equities.write(bearish_db)
    query = EquityQuery(countries=["Belgium", "China"], exchanges=["Euronext", 'SHZ'])
    queries = bearish_db.read_equities(query)
    assert queries
    assert all(isinstance(eq, Equity) for eq in queries)

def test_write_equities_from_url(bearish_db: BearishDb) -> None:
    equities = Equities.from_url()
    equities.write(bearish_db)


def test_from_raw_alphavantage(bearish_db: BearishDb) -> None:
    data = json.loads(
        Path(__file__).parent.joinpath("data", "alphavantage.json").read_text()
    )
    daily_ohlcv = DailySeries._from_raw_alphavantage(data)
    daily_series = DailySeries(daily_ohlcv=daily_ohlcv)


def test_write_daily_series_many(bearish_db: BearishDb) -> None:
    data = json.loads(
        Path(__file__).parent.joinpath("data", "alphavantage.json").read_text()
    )
    daily_ohlcv = DailySeries._from_raw_alphavantage(data)
    daily_series = DailySeries(daily_ohlcv=daily_ohlcv)
    daily_series.write(bearish_db)
    daily_series.write(bearish_db)


def test_from_alphavantage(bearish_db: BearishDb) -> None:
    daily_series = DailySeries.from_alphavantage(Equity(symbol="ATEB.BR"))
    daily_series.write(bearish_db)
    a = 12
def test_from_yfinance(bearish_db: BearishDb) -> None:
    daily_series = DailySeries.from_yfinance(Equity(symbol="ATEB.BR"))
    daily_series.write(bearish_db)

def test_fundamentals():
    fn = FundamentalData(key="JMHRENO4DYQ3SE14")
    fn.get_company_overview("ATEB.BR")
    a = 12


#
# def test_get_indicators():
#     from alpha_vantage.techindicators import TechIndicators
#     ti = TechIndicators(key='JMHRENO4DYQ3SE14')
#     ti.get_adx("ABI.BR")
#     ti.get_macd("ABI.BR")
#     ti.ge
#     res = ts.get_daily("ABI.BR")


def test_yfinance(bearish_db: BearishDb):
    many_financials = ManyFinancials.from_yfinance(Equity(symbol="AAPL"))
    many_financials.write(bearish_db)


