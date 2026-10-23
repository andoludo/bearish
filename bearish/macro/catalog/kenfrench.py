"""Ken French factor catalog: US daily factors and regional monthly factors."""

from typing import List, Tuple

from bearish.macro.catalog._builder import series
from bearish.macro.models import MacroSeries

US_DAILY_ZIP = "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
US_MOMENTUM_ZIP = "F-F_Momentum_Factor_daily_CSV.zip"

FACTOR_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("FF_MKT", "Mkt-RF"),
    ("FF_SMB", "SMB"),
    ("FF_HML", "HML"),
    ("FF_RMW", "RMW"),
    ("FF_CMA", "CMA"),
    ("FF_RF", "RF"),
)

REGIONAL_ZIPS: Tuple[Tuple[str, str], ...] = (
    ("DM", "Developed_5_Factors_CSV.zip"),
    ("EUR", "Europe_5_Factors_CSV.zip"),
    ("JPN", "Japan_5_Factors_CSV.zip"),
    ("APXJ", "Asia_Pacific_ex_Japan_5_Factors_CSV.zip"),
    ("EM", "Emerging_5_Factors_CSV.zip"),
    ("NAM", "North_America_5_Factors_CSV.zip"),
)

SERIES: List[MacroSeries] = [
    *[series(concept, "USA", "KenFrench", f"{US_DAILY_ZIP}|{column}", "D") for concept, column in FACTOR_COLUMNS],
    series("FF_MOM", "USA", "KenFrench", f"{US_MOMENTUM_ZIP}|Mom", "D"),
    *[
        series(
            concept,
            entity,
            "KenFrench",
            f"{zip_name}|{column}",
            "M",
            entity_type="region" if entity != "JPN" else "country",
        )
        for entity, zip_name in REGIONAL_ZIPS
        for concept, column in FACTOR_COLUMNS
    ],
]
