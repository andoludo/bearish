"""Commodity reference data: one canonical code per commodity with the
identifiers each provider uses for it (futures symbol, World Bank Pink Sheet
series, CFTC market code, HS codes for trade statistics).
"""

from functools import lru_cache
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

CommodityGroup = Literal["energy", "precious", "industrial", "grains", "softs", "livestock"]


class Commodity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(description="Canonical code used as macro entity, e.g. BRENT")
    name: str
    group: CommodityGroup
    unit: str
    yfinance_symbol: Optional[str] = Field(default=None, description="Front-month future on Yahoo Finance")
    pinksheet_series: Optional[str] = Field(default=None, description="World Bank CMO monthly column")
    cftc_market_code: Optional[str] = Field(default=None, description="CFTC cftc_contract_market_code")
    hs_codes: Tuple[str, ...] = Field(default=(), description="HS 4-digit codes for Comtrade")
    sectors: Tuple[str, ...] = Field(default=(), description="Equity sectors most exposed (GICS-like names)")


COMMODITIES: Tuple[Commodity, ...] = (
    # energy
    Commodity(
        code="BRENT",
        name="Brent crude",
        group="energy",
        unit="USD/bbl",
        yfinance_symbol="BZ=F",
        pinksheet_series="CRUDE_BRENT",
        cftc_market_code="06765T",
        hs_codes=("2709",),
        sectors=("Energy",),
    ),
    Commodity(
        code="WTI",
        name="WTI crude",
        group="energy",
        unit="USD/bbl",
        yfinance_symbol="CL=F",
        pinksheet_series="CRUDE_WTI",
        cftc_market_code="067651",
        hs_codes=("2709",),
        sectors=("Energy",),
    ),
    Commodity(
        code="NATGAS_HH",
        name="Natural gas (Henry Hub)",
        group="energy",
        unit="USD/mmbtu",
        yfinance_symbol="NG=F",
        pinksheet_series="NGAS_US",
        cftc_market_code="023651",
        hs_codes=("2711",),
        sectors=("Energy", "Utilities"),
    ),
    Commodity(
        code="NATGAS_EU",
        name="Natural gas (Europe, TTF)",
        group="energy",
        unit="USD/mmbtu",
        yfinance_symbol="TTF=F",
        pinksheet_series="NGAS_EUR",
        hs_codes=("2711",),
        sectors=("Energy", "Utilities"),
    ),
    Commodity(
        code="COAL",
        name="Thermal coal (Australia)",
        group="energy",
        unit="USD/mt",
        pinksheet_series="COAL_AUS",
        hs_codes=("2701",),
        sectors=("Energy", "Utilities"),
    ),
    Commodity(
        code="GASOLINE",
        name="RBOB gasoline",
        group="energy",
        unit="USD/gal",
        yfinance_symbol="RB=F",
        cftc_market_code="111659",
        hs_codes=("2710",),
        sectors=("Energy",),
    ),
    Commodity(
        code="HEATING_OIL",
        name="Heating oil",
        group="energy",
        unit="USD/gal",
        yfinance_symbol="HO=F",
        cftc_market_code="022651",
        hs_codes=("2710",),
        sectors=("Energy",),
    ),
    # precious
    Commodity(
        code="GOLD",
        name="Gold",
        group="precious",
        unit="USD/troy oz",
        yfinance_symbol="GC=F",
        pinksheet_series="GOLD",
        cftc_market_code="088691",
        hs_codes=("7108",),
        sectors=("Materials",),
    ),
    Commodity(
        code="SILVER",
        name="Silver",
        group="precious",
        unit="USD/troy oz",
        yfinance_symbol="SI=F",
        pinksheet_series="SILVER",
        cftc_market_code="084691",
        hs_codes=("7106",),
        sectors=("Materials",),
    ),
    Commodity(
        code="PLATINUM",
        name="Platinum",
        group="precious",
        unit="USD/troy oz",
        yfinance_symbol="PL=F",
        pinksheet_series="PLATINUM",
        cftc_market_code="076651",
        hs_codes=("7110",),
        sectors=("Materials", "Consumer Discretionary"),
    ),
    Commodity(
        code="PALLADIUM",
        name="Palladium",
        group="precious",
        unit="USD/troy oz",
        yfinance_symbol="PA=F",
        cftc_market_code="075651",
        hs_codes=("7110",),
        sectors=("Materials", "Consumer Discretionary"),
    ),
    # industrial metals
    Commodity(
        code="COPPER",
        name="Copper",
        group="industrial",
        unit="USD/mt",
        yfinance_symbol="HG=F",
        pinksheet_series="COPPER",
        cftc_market_code="085692",
        hs_codes=("7403", "2603"),
        sectors=("Materials", "Industrials"),
    ),
    Commodity(
        code="ALUMINIUM",
        name="Aluminium",
        group="industrial",
        unit="USD/mt",
        yfinance_symbol="ALI=F",
        pinksheet_series="ALUMINUM",
        hs_codes=("7601", "2606"),
        sectors=("Materials", "Industrials"),
    ),
    Commodity(
        code="NICKEL",
        name="Nickel",
        group="industrial",
        unit="USD/mt",
        pinksheet_series="NICKEL",
        hs_codes=("7502", "2604"),
        sectors=("Materials",),
    ),
    Commodity(
        code="ZINC",
        name="Zinc",
        group="industrial",
        unit="USD/mt",
        pinksheet_series="ZINC",
        hs_codes=("7901", "2608"),
        sectors=("Materials",),
    ),
    Commodity(
        code="IRON_ORE",
        name="Iron ore",
        group="industrial",
        unit="USD/dmtu",
        pinksheet_series="IRON_ORE",
        hs_codes=("2601",),
        sectors=("Materials",),
    ),
    Commodity(
        code="LEAD",
        name="Lead",
        group="industrial",
        unit="USD/mt",
        pinksheet_series="LEAD",
        hs_codes=("7801", "2607"),
        sectors=("Materials",),
    ),
    Commodity(
        code="TIN",
        name="Tin",
        group="industrial",
        unit="USD/mt",
        pinksheet_series="TIN",
        hs_codes=("8001", "2609"),
        sectors=("Materials", "Information Technology"),
    ),
    # grains & oilseeds
    Commodity(
        code="WHEAT",
        name="Wheat",
        group="grains",
        unit="USc/bu",
        yfinance_symbol="ZW=F",
        pinksheet_series="WHEAT_US_HRW",
        cftc_market_code="001602",
        hs_codes=("1001",),
        sectors=("Consumer Staples",),
    ),
    Commodity(
        code="CORN",
        name="Corn (maize)",
        group="grains",
        unit="USc/bu",
        yfinance_symbol="ZC=F",
        pinksheet_series="MAIZE",
        cftc_market_code="002602",
        hs_codes=("1005",),
        sectors=("Consumer Staples",),
    ),
    Commodity(
        code="SOYBEANS",
        name="Soybeans",
        group="grains",
        unit="USc/bu",
        yfinance_symbol="ZS=F",
        pinksheet_series="SOYBEANS",
        cftc_market_code="005602",
        hs_codes=("1201",),
        sectors=("Consumer Staples",),
    ),
    Commodity(
        code="RICE",
        name="Rice (Thai 5%)",
        group="grains",
        unit="USD/mt",
        yfinance_symbol="ZR=F",
        pinksheet_series="RICE_05",
        hs_codes=("1006",),
        sectors=("Consumer Staples",),
    ),
    Commodity(
        code="PALM_OIL",
        name="Palm oil",
        group="grains",
        unit="USD/mt",
        pinksheet_series="PALM_OIL",
        hs_codes=("1511",),
        sectors=("Consumer Staples",),
    ),
    # softs
    Commodity(
        code="SUGAR",
        name="Sugar (world)",
        group="softs",
        unit="USc/lb",
        yfinance_symbol="SB=F",
        pinksheet_series="SUGAR_WLD",
        cftc_market_code="080732",
        hs_codes=("1701",),
        sectors=("Consumer Staples",),
    ),
    Commodity(
        code="COFFEE",
        name="Coffee (arabica)",
        group="softs",
        unit="USc/lb",
        yfinance_symbol="KC=F",
        pinksheet_series="COFFEE_ARABIC",
        cftc_market_code="083731",
        hs_codes=("0901",),
        sectors=("Consumer Staples",),
    ),
    Commodity(
        code="COCOA",
        name="Cocoa",
        group="softs",
        unit="USD/mt",
        yfinance_symbol="CC=F",
        pinksheet_series="COCOA",
        cftc_market_code="073732",
        hs_codes=("1801",),
        sectors=("Consumer Staples",),
    ),
    Commodity(
        code="COTTON",
        name="Cotton",
        group="softs",
        unit="USc/lb",
        yfinance_symbol="CT=F",
        pinksheet_series="COTTON_A_INDX",
        cftc_market_code="033661",
        hs_codes=("5201",),
        sectors=("Consumer Discretionary",),
    ),
    # livestock
    Commodity(
        code="LIVE_CATTLE",
        name="Live cattle",
        group="livestock",
        unit="USc/lb",
        yfinance_symbol="LE=F",
        cftc_market_code="057642",
        hs_codes=("0102", "0201"),
        sectors=("Consumer Staples",),
    ),
    Commodity(
        code="LEAN_HOGS",
        name="Lean hogs",
        group="livestock",
        unit="USc/lb",
        yfinance_symbol="HE=F",
        cftc_market_code="054642",
        hs_codes=("0103", "0203"),
        sectors=("Consumer Staples",),
    ),
)


@lru_cache(maxsize=1)
def commodities_by_code() -> Dict[str, Commodity]:
    return {commodity.code: commodity for commodity in COMMODITIES}


def commodity_from(code: str) -> Optional[Commodity]:
    return commodities_by_code().get(code.strip().upper())


def commodities_with(attribute: str) -> List[Commodity]:
    """Commodities for which a given provider identifier is known."""
    return [commodity for commodity in COMMODITIES if getattr(commodity, attribute)]


class CountryCommodityExposure(BaseModel):
    """Share of a country's trade accounted for by one commodity (UN Comtrade)."""

    model_config = ConfigDict(extra="forbid")

    country: str = Field(description="ISO-3")
    commodity: str = Field(description="Commodity code")
    direction: Literal["export", "import"]
    year: int
    value_usd: float
    share: float = Field(description="Fraction of the country's total trade in that direction")
    source: str = "Comtrade"
