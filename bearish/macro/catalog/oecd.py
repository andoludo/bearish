"""OECD catalog: harmonised activity, prices, labour, rates and confidence.

OECD is the primary owner of the cross-country monthly/quarterly concepts
(CLI, confidence, CPI, unemployment, GDP, industrial production, retail,
long and short rates) for its members plus the large non-members it covers.
Keys were verified against the Data Explorer in October 2026.
"""

from typing import List

from bearish.macro.catalog._builder import for_countries
from bearish.macro.countries import priority_countries
from bearish.macro.models import MacroSeries

_STES = "OECD.SDD.STES,DSD_STES@DF_CLI,/{code}.M.{measure}...AA...H"
_PRICES = "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/{code}.M.N.CPI.PA.{expenditure}.N.GY"
_UNEMPLOYMENT = "OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0/{code}..._Z.Y._T.Y_GE15..M"
_GDP = "OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD,1.1/Q..{code}.S1..B1GQ......GY."
_INDSERV = "OECD.SDD.STES,DSD_STES@DF_INDSERV,/{code}.M.{measure}.IX.{activity}.Y._Z.."
_FINMARK = "OECD.SDD.STES,DSD_STES@DF_FINMARK,/{code}.M.{measure}.PA....."

# CLI/BCI/CCI and GDP growth are published for these non-members too.
_CLI_NON_MEMBERS = {"BRA", "CHN", "IND", "IDN", "ZAF"}
_CPI_NON_MEMBERS = {"BRA", "CHN", "IND", "IDN", "ZAF", "ARG", "SAU", "RUS"}

_members = [c for c in priority_countries() if c.oecd]
_cli_countries = [c for c in priority_countries() if c.oecd or c.iso3 in _CLI_NON_MEMBERS]
# EU members take headline/core CPI from the Eurostat HICP (continuous across
# national methodology changes); OECD covers the rest.
_cpi_countries = [c for c in priority_countries() if (c.oecd or c.iso3 in _CPI_NON_MEMBERS) and not c.eu]
_core_cpi_countries = [c for c in _members if c.iso3 != "USA" and not c.eu]
# FRED owns the US yield curve (daily, longer history).
_rate_countries = [c for c in _members if c.iso3 != "USA"]


def _template(template: str, **fixed: str) -> str:
    return template.replace("{code}", "\x00").format(**fixed).replace("\x00", "{code}")


SERIES: List[MacroSeries] = [
    *for_countries("CLI", _cli_countries, "OECD", _template(_STES, measure="LI"), "M", seasonal_adj=True),
    *for_countries("BIZ_CONF", _cli_countries, "OECD", _template(_STES, measure="BCICP"), "M", seasonal_adj=True),
    *for_countries("CONS_CONF", _cli_countries, "OECD", _template(_STES, measure="CCICP"), "M", seasonal_adj=True),
    *for_countries("CPI_YOY", _cpi_countries, "OECD", _template(_PRICES, expenditure="_T"), "M"),
    *for_countries("CORE_CPI_YOY", _core_cpi_countries, "OECD", _template(_PRICES, expenditure="_TXCP01_NRG"), "M"),
    *for_countries("UNEMP_RATE", _members, "OECD", _UNEMPLOYMENT, "M", seasonal_adj=True),
    *for_countries("GDP_YOY", _cli_countries, "OECD", _GDP, "Q", seasonal_adj=True),
    *for_countries(
        "IP_YOY",
        _members,
        "OECD",
        _template(_INDSERV, measure="PRVM", activity="BTE"),
        "M",
        transform="yoy",
        seasonal_adj=True,
    ),
    *for_countries(
        "RETAIL_YOY",
        _members,
        "OECD",
        _template(_INDSERV, measure="TOVM", activity="G47"),
        "M",
        transform="yoy",
        seasonal_adj=True,
    ),
    *for_countries("Y10", _rate_countries, "OECD", _template(_FINMARK, measure="IRLT"), "M"),
    *for_countries("Y3M", _rate_countries, "OECD", _template(_FINMARK, measure="IR3TIB"), "M"),
]
