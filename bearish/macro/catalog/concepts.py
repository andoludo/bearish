"""Normalised concept definitions.

A concept names *what* a series measures, independent of the provider. Catalog
entries must reference a concept defined here (enforced by the catalog test)
so that downstream KPIs can rely on a closed vocabulary.
"""

from typing import Dict

from pydantic import BaseModel, ConfigDict

from bearish.macro.models import Category


class ConceptDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: Category
    unit: str
    description: str


CONCEPTS: Dict[str, ConceptDefinition] = {
    # growth
    "GDP_YOY": ConceptDefinition(category="growth", unit="%", description="Real GDP growth, year on year"),
    "GDP_QOQ": ConceptDefinition(category="growth", unit="%", description="Real GDP growth, quarter on quarter"),
    "GDP_FCST": ConceptDefinition(category="growth", unit="%", description="Real GDP growth forecast (IMF WEO)"),
    "GDP_NOWCAST": ConceptDefinition(category="growth", unit="% SAAR", description="Current-quarter real GDP nowcast"),
    "GDP_PER_CAPITA": ConceptDefinition(category="growth", unit="USD", description="GDP per capita, current USD"),
    "IP_YOY": ConceptDefinition(category="growth", unit="%", description="Industrial production, year on year"),
    "RETAIL_YOY": ConceptDefinition(category="growth", unit="%", description="Retail sales volume, year on year"),
    "CLI": ConceptDefinition(
        category="growth", unit="index", description="OECD composite leading indicator (100 = trend)"
    ),
    # inflation
    "CPI_YOY": ConceptDefinition(category="inflation", unit="%", description="Headline consumer prices, year on year"),
    "CORE_CPI_YOY": ConceptDefinition(category="inflation", unit="%", description="Core consumer prices, year on year"),
    "PPI_YOY": ConceptDefinition(category="inflation", unit="%", description="Producer prices, year on year"),
    "INFL_FCST": ConceptDefinition(category="inflation", unit="%", description="Inflation forecast (IMF WEO)"),
    "INFL_EXP_5Y5Y": ConceptDefinition(
        category="inflation", unit="%", description="5y5y forward inflation expectation"
    ),
    # labour
    "UNEMP_RATE": ConceptDefinition(category="labour", unit="%", description="Unemployment rate"),
    "UNEMP_FCST": ConceptDefinition(category="labour", unit="%", description="Unemployment rate forecast (IMF WEO)"),
    "PAYROLLS_CHG": ConceptDefinition(
        category="labour", unit="thousands", description="Monthly change in non-farm payrolls"
    ),
    # rates
    "POLICY_RATE": ConceptDefinition(category="rates", unit="%", description="Central bank policy rate"),
    "Y10": ConceptDefinition(category="rates", unit="%", description="10-year government bond yield"),
    "Y2": ConceptDefinition(category="rates", unit="%", description="2-year government bond yield"),
    "Y3M": ConceptDefinition(category="rates", unit="%", description="3-month government bill yield"),
    "CURVE_10_2": ConceptDefinition(category="rates", unit="pp", description="10-year minus 2-year yield"),
    "CURVE_10_3M": ConceptDefinition(category="rates", unit="pp", description="10-year minus 3-month yield"),
    "REAL_Y10": ConceptDefinition(category="rates", unit="%", description="10-year inflation-indexed yield"),
    "MORTGAGE_30Y": ConceptDefinition(category="rates", unit="%", description="30-year fixed mortgage rate"),
    "SOFR": ConceptDefinition(category="rates", unit="%", description="Secured overnight financing rate"),
    # credit / financial conditions
    "HY_SPREAD": ConceptDefinition(category="credit", unit="pp", description="High-yield corporate OAS"),
    "IG_SPREAD": ConceptDefinition(category="credit", unit="pp", description="Investment-grade corporate OAS"),
    "NFCI": ConceptDefinition(
        category="credit", unit="index", description="Chicago Fed national financial conditions index"
    ),
    "CREDIT_GDP_GAP": ConceptDefinition(category="credit", unit="pp", description="BIS credit-to-GDP gap"),
    "CREDIT_GDP": ConceptDefinition(
        category="credit", unit="% GDP", description="Credit to private non-financial sector"
    ),
    "HOUSE_PRICE_YOY": ConceptDefinition(
        category="credit", unit="%", description="Residential property prices, year on year"
    ),
    "M2_YOY": ConceptDefinition(category="credit", unit="%", description="Broad money, year on year"),
    "VIX": ConceptDefinition(category="credit", unit="index", description="CBOE volatility index"),
    "RECESSION_PROB": ConceptDefinition(category="credit", unit="%", description="Smoothed US recession probability"),
    # fiscal / external
    "DEBT_GDP": ConceptDefinition(category="fiscal", unit="% GDP", description="General government gross debt"),
    "DEFICIT_GDP": ConceptDefinition(
        category="fiscal", unit="% GDP", description="General government net lending/borrowing"
    ),
    "CA_GDP": ConceptDefinition(category="external", unit="% GDP", description="Current account balance"),
    "REER": ConceptDefinition(
        category="external", unit="index", description="Real effective exchange rate (BIS broad)"
    ),
    "FX_USD": ConceptDefinition(category="external", unit="per USD", description="Exchange rate against the US dollar"),
    "DXY": ConceptDefinition(category="external", unit="index", description="Trade-weighted US dollar index"),
    "TRADE_GDP": ConceptDefinition(
        category="external", unit="% GDP", description="Trade (exports + imports) share of GDP"
    ),
    "RESERVES": ConceptDefinition(category="external", unit="USD", description="Total reserves including gold"),
    # sentiment
    "CONS_CONF": ConceptDefinition(
        category="sentiment", unit="index", description="Consumer confidence (OECD amplitude adjusted)"
    ),
    "BIZ_CONF": ConceptDefinition(
        category="sentiment", unit="index", description="Business confidence (OECD amplitude adjusted)"
    ),
    "PMI_MFG": ConceptDefinition(
        category="sentiment", unit="index", description="Manufacturing PMI or closest open proxy"
    ),
    "EPU": ConceptDefinition(category="sentiment", unit="index", description="Economic policy uncertainty index"),
    "GPR": ConceptDefinition(category="sentiment", unit="index", description="Geopolitical risk index"),
    "ESI": ConceptDefinition(category="sentiment", unit="index", description="EU economic sentiment indicator"),
    # commodities
    "PRICE": ConceptDefinition(category="prices", unit="native", description="Spot or front-month commodity price"),
    "PRICE_M": ConceptDefinition(category="prices", unit="native", description="Monthly average commodity price"),
    "COT_NET_SPEC": ConceptDefinition(
        category="positioning", unit="contracts", description="Net non-commercial futures positioning"
    ),
    "COT_NET_SPEC_PCT_OI": ConceptDefinition(
        category="positioning", unit="% OI", description="Net non-commercial positioning as % of open interest"
    ),
    "COT_OPEN_INTEREST": ConceptDefinition(
        category="positioning", unit="contracts", description="Total futures open interest"
    ),
    "STOCKS_TO_USE": ConceptDefinition(
        category="supply_demand", unit="ratio", description="Ending stocks over total use"
    ),
    "PRODUCTION": ConceptDefinition(category="supply_demand", unit="native", description="Production volume"),
    "CONSUMPTION": ConceptDefinition(category="supply_demand", unit="native", description="Consumption volume"),
    "ENDING_STOCKS": ConceptDefinition(category="supply_demand", unit="native", description="Ending stocks"),
    "INVENTORIES": ConceptDefinition(
        category="supply_demand", unit="native", description="Reported inventories (weekly)"
    ),
    # factors
    "FF_MKT": ConceptDefinition(category="factor", unit="%", description="Fama-French market excess return"),
    "FF_SMB": ConceptDefinition(category="factor", unit="%", description="Fama-French size factor"),
    "FF_HML": ConceptDefinition(category="factor", unit="%", description="Fama-French value factor"),
    "FF_RMW": ConceptDefinition(category="factor", unit="%", description="Fama-French profitability factor"),
    "FF_CMA": ConceptDefinition(category="factor", unit="%", description="Fama-French investment factor"),
    "FF_MOM": ConceptDefinition(category="factor", unit="%", description="Momentum factor"),
    "FF_RF": ConceptDefinition(category="factor", unit="%", description="Risk-free rate used by Fama-French"),
    # technology themes (attention / adoption)
    "THEME_FILINGS": ConceptDefinition(
        category="sentiment", unit="filings", description="SEC filings per quarter mentioning a technology theme"
    ),
    "ADOPTION_PAPERS": ConceptDefinition(
        category="sentiment", unit="papers", description="arXiv papers per month on a technology theme"
    ),
    # conflict & supply-chain shocks
    "TRANSITS": ConceptDefinition(
        category="supply_demand", unit="vessels/day", description="Vessel transits through a maritime chokepoint"
    ),
    "TRANSITS_TANKER": ConceptDefinition(
        category="supply_demand", unit="vessels/day", description="Tanker transits through a maritime chokepoint"
    ),
    "TRANSITS_CONTAINER": ConceptDefinition(
        category="supply_demand", unit="vessels/day", description="Container-ship transits through a chokepoint"
    ),
    "CAPACITY_TONNES": ConceptDefinition(
        category="supply_demand", unit="dwt/day", description="Deadweight tonnage transiting a chokepoint"
    ),
    "GDELT_CONFLICT_EVENTS": ConceptDefinition(
        category="sentiment", unit="events/day", description="GDELT material-conflict events (QuadClass 4)"
    ),
    "GDELT_VERBAL_CONFLICT": ConceptDefinition(
        category="sentiment", unit="events/day", description="GDELT verbal-conflict events (QuadClass 3)"
    ),
    "GDELT_GOLDSTEIN": ConceptDefinition(
        category="sentiment", unit="scale -10..10", description="Mean Goldstein cooperation/conflict score"
    ),
    "GDELT_TONE": ConceptDefinition(
        category="sentiment", unit="tone", description="Mean article tone of GDELT events"
    ),
    "SANCTIONS_NEW": ConceptDefinition(
        category="external", unit="designations/month", description="New OFAC SDN designations (still listed)"
    ),
    "MILEX_USD": ConceptDefinition(
        category="fiscal", unit="USD m, constant prices", description="Military expenditure (SIPRI)"
    ),
    "MILEX_GDP": ConceptDefinition(category="fiscal", unit="% GDP", description="Military expenditure share of GDP"),
}
