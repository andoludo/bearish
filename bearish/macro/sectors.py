"""Shared sector and industry vocabulary.

Asset providers do not agree on sector names: FinanceDatabase stores GICS
names (``Information Technology``, ``Consumer Discretionary``), Yahoo stores
its own (``Technology``, ``Consumer Cyclical``) and Yahoo ETF sector weights
use snake-case keys (``consumer_cyclical``). Downstream joins between
equities, ETF exposures and the sector-commodity sensitivities only work when
every spelling resolves to one canonical name.

* ``GICS_SECTORS`` and ``GICS_INDUSTRIES`` are the closed vocabulary
  (GICS 2023, plus the ``Agricultural Products`` sub-industry that the
  sensitivities need because grain producers and food makers have opposite
  commodity exposure),
* ``sector_from`` / ``industry_from`` resolve any known spelling,
* ``sector_aliases`` lists every spelling for the ``sectoralias`` table, which
  the ``equitysector`` view joins onto ``equity.sector`` / ``equity.industry``.
"""

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

AliasLevel = Literal["sector", "industry"]

GICS_SECTORS: Tuple[str, ...] = (
    "Energy",
    "Materials",
    "Industrials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Health Care",
    "Financials",
    "Information Technology",
    "Communication Services",
    "Utilities",
    "Real Estate",
)

# GICS industry → GICS sector.
GICS_INDUSTRIES: Dict[str, str] = {
    "Energy Equipment & Services": "Energy",
    "Oil, Gas & Consumable Fuels": "Energy",
    "Chemicals": "Materials",
    "Construction Materials": "Materials",
    "Containers & Packaging": "Materials",
    "Metals & Mining": "Materials",
    "Paper & Forest Products": "Materials",
    "Aerospace & Defense": "Industrials",
    "Building Products": "Industrials",
    "Construction & Engineering": "Industrials",
    "Electrical Equipment": "Industrials",
    "Industrial Conglomerates": "Industrials",
    "Machinery": "Industrials",
    "Trading Companies & Distributors": "Industrials",
    "Commercial Services & Supplies": "Industrials",
    "Professional Services": "Industrials",
    "Air Freight & Logistics": "Industrials",
    "Passenger Airlines": "Industrials",
    "Marine Transportation": "Industrials",
    "Ground Transportation": "Industrials",
    "Transportation Infrastructure": "Industrials",
    "Automobile Components": "Consumer Discretionary",
    "Automobiles": "Consumer Discretionary",
    "Household Durables": "Consumer Discretionary",
    "Leisure Products": "Consumer Discretionary",
    "Textiles, Apparel & Luxury Goods": "Consumer Discretionary",
    "Hotels, Restaurants & Leisure": "Consumer Discretionary",
    "Diversified Consumer Services": "Consumer Discretionary",
    "Distributors": "Consumer Discretionary",
    "Broadline Retail": "Consumer Discretionary",
    "Specialty Retail": "Consumer Discretionary",
    "Consumer Staples Distribution & Retail": "Consumer Staples",
    "Beverages": "Consumer Staples",
    "Food Products": "Consumer Staples",
    "Agricultural Products": "Consumer Staples",  # sub-industry of Food Products, kept for sensitivities
    "Tobacco": "Consumer Staples",
    "Household Products": "Consumer Staples",
    "Personal Care Products": "Consumer Staples",
    "Health Care Equipment & Supplies": "Health Care",
    "Health Care Providers & Services": "Health Care",
    "Health Care Technology": "Health Care",
    "Biotechnology": "Health Care",
    "Pharmaceuticals": "Health Care",
    "Life Sciences Tools & Services": "Health Care",
    "Banks": "Financials",
    "Financial Services": "Financials",
    "Consumer Finance": "Financials",
    "Capital Markets": "Financials",
    "Mortgage Real Estate Investment Trusts (REITs)": "Financials",
    "Insurance": "Financials",
    "IT Services": "Information Technology",
    "Software": "Information Technology",
    "Communications Equipment": "Information Technology",
    "Technology Hardware, Storage & Peripherals": "Information Technology",
    "Electronic Equipment, Instruments & Components": "Information Technology",
    "Semiconductors & Semiconductor Equipment": "Information Technology",
    "Diversified Telecommunication Services": "Communication Services",
    "Wireless Telecommunication Services": "Communication Services",
    "Media": "Communication Services",
    "Entertainment": "Communication Services",
    "Interactive Media & Services": "Communication Services",
    "Electric Utilities": "Utilities",
    "Gas Utilities": "Utilities",
    "Multi-Utilities": "Utilities",
    "Water Utilities": "Utilities",
    "Independent Power and Renewable Electricity Producers": "Utilities",
    "Diversified REITs": "Real Estate",
    "Industrial REITs": "Real Estate",
    "Hotel & Resort REITs": "Real Estate",
    "Office REITs": "Real Estate",
    "Health Care REITs": "Real Estate",
    "Residential REITs": "Real Estate",
    "Retail REITs": "Real Estate",
    "Specialized REITs": "Real Estate",
    "Real Estate Management & Development": "Real Estate",
}

# Every known spelling of a sector (Yahoo, FinanceDatabase, Yahoo ETF keys,
# common abbreviations) → GICS sector. Matching is case-insensitive.
_SECTOR_SPELLINGS: Dict[str, Tuple[str, ...]] = {
    "Energy": ("Oil & Gas", "Oil and Gas", "Oil, Gas & Consumable Fuels"),
    "Materials": ("Basic Materials", "basic_materials", "Materials & Mining"),
    "Industrials": ("Industrial", "industrials", "Industrial Goods", "Conglomerates"),
    "Consumer Discretionary": ("Consumer Cyclical", "consumer_cyclical", "Consumer Cyclicals", "Consumer Services"),
    "Consumer Staples": ("Consumer Defensive", "consumer_defensive", "Consumer Non-Cyclical", "Consumer Goods"),
    "Health Care": ("Healthcare", "healthcare", "Health Care Services", "Medical"),
    "Financials": ("Financial Services", "financial_services", "Financial", "Finance", "Banking"),
    "Information Technology": ("Technology", "technology", "Tech", "IT", "Information Technology Services"),
    "Communication Services": (
        "communication_services",
        "Telecommunications",
        "Telecommunication Services",
        "Telecom",
        "Communications",
    ),
    "Utilities": ("utilities", "Utility"),
    "Real Estate": ("realestate", "real_estate", "Property"),
}

# Yahoo industry → GICS industry.
_INDUSTRY_SPELLINGS: Dict[str, Tuple[str, ...]] = {
    "Energy Equipment & Services": ("Oil & Gas Equipment & Services", "Oil & Gas Drilling"),
    "Oil, Gas & Consumable Fuels": (
        "Oil & Gas E&P",
        "Oil & Gas Integrated",
        "Oil & Gas Midstream",
        "Oil & Gas Refining & Marketing",
        "Thermal Coal",
        "Uranium",
    ),
    "Chemicals": ("Specialty Chemicals", "Agricultural Inputs"),
    "Construction Materials": ("Building Materials",),
    "Containers & Packaging": ("Packaging & Containers",),
    "Metals & Mining": (
        "Aluminum",
        "Copper",
        "Gold",
        "Silver",
        "Steel",
        "Coking Coal",
        "Other Industrial Metals & Mining",
        "Other Precious Metals & Mining",
    ),
    "Paper & Forest Products": ("Paper & Paper Products", "Lumber & Wood Production"),
    "Aerospace & Defense": (),
    "Building Products": ("Building Products & Equipment",),
    "Construction & Engineering": ("Engineering & Construction", "Infrastructure Operations"),
    "Electrical Equipment": ("Electrical Equipment & Parts",),
    "Industrial Conglomerates": ("Conglomerates",),
    "Machinery": (
        "Specialty Industrial Machinery",
        "Farm & Heavy Construction Machinery",
        "Metal Fabrication",
        "Tools & Accessories",
        "Pollution & Treatment Controls",
    ),
    "Trading Companies & Distributors": ("Industrial Distribution",),
    "Commercial Services & Supplies": (
        "Specialty Business Services",
        "Security & Protection Services",
        "Waste Management",
        "Business Equipment & Supplies",
    ),
    "Professional Services": ("Consulting Services", "Staffing & Employment Services", "Rental & Leasing Services"),
    "Air Freight & Logistics": ("Integrated Freight & Logistics",),
    "Passenger Airlines": ("Airlines",),
    "Marine Transportation": ("Marine Shipping", "Marine"),
    "Ground Transportation": ("Railroads", "Trucking", "Road & Rail"),
    "Transportation Infrastructure": ("Airports & Air Services",),
    "Automobile Components": ("Auto Parts", "Auto Components"),
    "Automobiles": ("Auto Manufacturers", "Recreational Vehicles"),
    "Household Durables": ("Furnishings, Fixtures & Appliances", "Residential Construction"),
    "Leisure Products": ("Leisure",),
    "Textiles, Apparel & Luxury Goods": (
        "Apparel Manufacturing",
        "Footwear & Accessories",
        "Luxury Goods",
        "Textile Manufacturing",
    ),
    "Hotels, Restaurants & Leisure": ("Restaurants", "Lodging", "Resorts & Casinos", "Gambling", "Travel Services"),
    "Diversified Consumer Services": ("Personal Services", "Education & Training Services"),
    "Distributors": ("Auto & Truck Dealerships",),
    "Broadline Retail": ("Internet Retail", "Department Stores"),
    "Specialty Retail": ("Apparel Retail", "Home Improvement Retail"),
    "Consumer Staples Distribution & Retail": (
        "Grocery Stores",
        "Discount Stores",
        "Food Distribution",
        "Pharmaceutical Retailers",
        "Food & Staples Retailing",
    ),
    "Beverages": ("Beverages - Brewers", "Beverages - Wineries & Distilleries", "Beverages - Non-Alcoholic"),
    "Food Products": ("Packaged Foods", "Confectioners"),
    "Agricultural Products": ("Farm Products",),
    "Tobacco": (),
    "Household Products": ("Household & Personal Products",),
    "Personal Care Products": (),
    "Health Care Equipment & Supplies": ("Medical Devices", "Medical Instruments & Supplies"),
    "Health Care Providers & Services": ("Healthcare Plans", "Medical Care Facilities", "Medical Distribution"),
    "Health Care Technology": ("Health Information Services",),
    "Biotechnology": (),
    "Pharmaceuticals": ("Drug Manufacturers - General", "Drug Manufacturers - Specialty & Generic"),
    "Life Sciences Tools & Services": ("Diagnostics & Research",),
    "Banks": ("Banks - Diversified", "Banks - Regional"),
    "Financial Services": ("Financial Data & Stock Exchanges", "Financial Conglomerates", "Shell Companies"),
    "Consumer Finance": ("Credit Services",),
    "Capital Markets": ("Asset Management",),
    "Mortgage Real Estate Investment Trusts (REITs)": ("REIT - Mortgage", "Mortgage Finance"),
    "Insurance": (
        "Insurance - Life",
        "Insurance - Property & Casualty",
        "Insurance - Reinsurance",
        "Insurance - Specialty",
        "Insurance - Diversified",
        "Insurance Brokers",
    ),
    "IT Services": ("Information Technology Services",),
    "Software": ("Software - Application", "Software - Infrastructure"),
    "Communications Equipment": ("Communication Equipment",),
    "Technology Hardware, Storage & Peripherals": ("Computer Hardware", "Consumer Electronics"),
    "Electronic Equipment, Instruments & Components": (
        "Electronic Components",
        "Electronics & Computer Distribution",
        "Scientific & Technical Instruments",
    ),
    "Semiconductors & Semiconductor Equipment": ("Semiconductors", "Semiconductor Equipment & Materials", "Solar"),
    "Diversified Telecommunication Services": ("Telecom Services",),
    "Wireless Telecommunication Services": (),
    "Media": ("Advertising Agencies", "Publishing", "Broadcasting"),
    "Entertainment": ("Electronic Gaming & Multimedia",),
    "Interactive Media & Services": ("Internet Content & Information",),
    "Electric Utilities": ("Utilities - Regulated Electric",),
    "Gas Utilities": ("Utilities - Regulated Gas",),
    "Multi-Utilities": ("Utilities - Diversified",),
    "Water Utilities": ("Utilities - Regulated Water",),
    "Independent Power and Renewable Electricity Producers": (
        "Utilities - Independent Power Producers",
        "Utilities - Renewable",
    ),
    "Diversified REITs": ("REIT - Diversified",),
    "Industrial REITs": ("REIT - Industrial",),
    "Hotel & Resort REITs": ("REIT - Hotel & Motel",),
    "Office REITs": ("REIT - Office",),
    "Health Care REITs": ("REIT - Healthcare Facilities",),
    "Residential REITs": ("REIT - Residential",),
    "Retail REITs": ("REIT - Retail",),
    "Specialized REITs": ("REIT - Specialty",),
    "Real Estate Management & Development": (
        "Real Estate - Development",
        "Real Estate Services",
        "Real Estate - Diversified",
    ),
}


class SectorAlias(BaseModel):
    """A spelling of a sector or industry as it appears in asset tables, mapped to the canonical name."""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(description="Case-folded spelling")
    level: AliasLevel
    name: str = Field(description="Canonical GICS sector or industry")


def _key(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())


def _build(canonical: Tuple[str, ...], spellings: Dict[str, Tuple[str, ...]]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for name in canonical:
        lookup[_key(name)] = name
    for name, aliases in spellings.items():
        for alias in aliases:
            lookup.setdefault(_key(alias), name)
    return lookup


SECTOR_LOOKUP: Dict[str, str] = _build(GICS_SECTORS, _SECTOR_SPELLINGS)
INDUSTRY_LOOKUP: Dict[str, str] = _build(tuple(GICS_INDUSTRIES), _INDUSTRY_SPELLINGS)


def sector_from(value: Optional[str]) -> Optional[str]:
    """Canonical GICS sector for any known spelling, ``None`` when unknown."""
    if not value:
        return None
    return SECTOR_LOOKUP.get(_key(value))


def industry_from(value: Optional[str]) -> Optional[str]:
    """Canonical GICS industry for any known spelling, ``None`` when unknown."""
    if not value:
        return None
    return INDUSTRY_LOOKUP.get(_key(value))


def sector_of_industry(industry: Optional[str]) -> Optional[str]:
    """GICS sector an industry (any spelling) belongs to."""
    canonical = industry_from(industry)
    return GICS_INDUSTRIES.get(canonical) if canonical else None


def is_known_group(value: str) -> bool:
    """True when ``value`` is a canonical sector or industry name."""
    return value in GICS_SECTORS or value in GICS_INDUSTRIES


def sector_aliases() -> List[SectorAlias]:
    """Every spelling, for the ``sectoralias`` table."""
    return [SectorAlias(alias=alias, level="sector", name=name) for alias, name in SECTOR_LOOKUP.items()] + [
        SectorAlias(alias=alias, level="industry", name=name) for alias, name in INDUSTRY_LOOKUP.items()
    ]
