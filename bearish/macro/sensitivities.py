"""Curated sign of equity sector / industry sensitivity to commodity prices.

Sector names follow the GICS-style vocabulary stored in ``equity.sector`` and
``equity.industry`` (``Energy``, ``Materials``, ``Airlines``, ...). The signs
are deliberately coarse priors: a positive direction means the group tends to
benefit from a higher commodity price, a negative one that it is an input
cost. Downstream KPIs may replace them with estimated betas; keeping them
explicit here lets a recommendation cite *why* a commodity move matters.
"""

from typing import Literal, Tuple

from bearish.interface.interface import BearishDbBase
from bearish.macro.links import SectorCommoditySensitivity

Strength = Literal["high", "medium", "low"]


def _s(sector: str, commodity: str, direction: int, strength: Strength, rationale: str) -> SectorCommoditySensitivity:
    return SectorCommoditySensitivity(
        sector=sector,
        commodity=commodity,
        direction=direction,
        strength=strength,
        rationale=rationale,
    )


SECTOR_COMMODITY_SENSITIVITIES: Tuple[SectorCommoditySensitivity, ...] = (
    # Energy producers and services
    _s("Energy", "BRENT", 1, "high", "Revenue of oil producers scales with the crude price"),
    _s("Energy", "WTI", 1, "high", "US producers realise WTI-linked prices"),
    _s("Energy", "NATGAS_HH", 1, "medium", "Gas producers and midstream earn more at higher Henry Hub prices"),
    _s("Oil, Gas & Consumable Fuels", "BRENT", 1, "high", "Upstream and integrated oil earnings track crude"),
    _s("Oil, Gas & Consumable Fuels", "NATGAS_HH", 1, "medium", "Gas-weighted producers track Henry Hub"),
    _s("Oil, Gas & Consumable Fuels", "COAL", 1, "medium", "Coal miners sit in this industry group"),
    _s("Energy Equipment & Services", "BRENT", 1, "high", "Drilling and services demand follows producer cash flow"),
    # Transport: fuel is the main variable cost
    _s("Airlines", "BRENT", -1, "high", "Jet fuel is 20-30% of airline operating cost"),
    _s("Air Freight & Logistics", "BRENT", -1, "medium", "Fuel surcharges lag cost increases"),
    _s("Marine", "BRENT", -1, "medium", "Bunker fuel is the largest voyage cost"),
    _s("Road & Rail", "BRENT", -1, "low", "Diesel cost partly passed through via surcharges"),
    _s("Transportation Infrastructure", "BRENT", -1, "low", "Higher fuel dampens traffic volumes"),
    # Materials and mining
    _s("Materials", "COPPER", 1, "high", "Copper is the bellwether metal for diversified miners"),
    _s("Materials", "IRON_ORE", 1, "high", "Iron ore drives bulk miners' earnings"),
    _s("Materials", "GOLD", 1, "medium", "Gold miners' margins expand with the gold price"),
    _s("Materials", "ALUMINIUM", 1, "medium", "Smelters and bauxite producers benefit from higher aluminium"),
    _s("Materials", "NICKEL", 1, "low", "Nickel exposure concentrated in a few producers"),
    _s("Metals & Mining", "COPPER", 1, "high", "Copper is the largest revenue line of diversified miners"),
    _s("Metals & Mining", "IRON_ORE", 1, "high", "Iron ore is the highest-margin bulk commodity"),
    _s("Metals & Mining", "GOLD", 1, "high", "Gold miners have high operating leverage to the gold price"),
    _s("Metals & Mining", "SILVER", 1, "medium", "Silver by-product credits lift mining margins"),
    _s("Metals & Mining", "ALUMINIUM", 1, "medium", "Aluminium producers benefit from higher LME prices"),
    _s("Metals & Mining", "NICKEL", 1, "medium", "Nickel miners are leveraged to battery and steel demand"),
    _s("Metals & Mining", "ZINC", 1, "low", "Zinc is a secondary revenue line for base-metal miners"),
    _s("Metals & Mining", "COAL", 1, "medium", "Coal miners are classified under metals & mining"),
    _s("Metals & Mining", "PLATINUM", 1, "medium", "PGM miners' margins track platinum"),
    _s("Metals & Mining", "PALLADIUM", 1, "medium", "PGM miners' margins track palladium"),
    _s("Chemicals", "NATGAS_HH", -1, "high", "Gas is both feedstock and energy for chemicals"),
    _s("Chemicals", "NATGAS_EU", -1, "high", "European chemicals are exposed to TTF gas"),
    _s("Chemicals", "BRENT", -1, "medium", "Naphtha feedstock follows crude"),
    _s("Construction Materials", "COAL", -1, "medium", "Cement kilns burn coal and petcoke"),
    _s("Construction Materials", "NATGAS_EU", -1, "low", "Energy is a large share of cement cost"),
    _s("Paper & Forest Products", "NATGAS_HH", -1, "low", "Pulp and paper mills are energy intensive"),
    _s("Containers & Packaging", "ALUMINIUM", -1, "medium", "Can makers buy aluminium sheet"),
    # Utilities and power
    _s("Utilities", "NATGAS_HH", -1, "medium", "Gas is the marginal fuel for regulated and merchant generators"),
    _s("Utilities", "COAL", -1, "low", "Coal-fired generators face higher fuel cost"),
    _s("Electric Utilities", "NATGAS_HH", -1, "medium", "Fuel cost recovery lags for gas-fired fleets"),
    _s("Gas Utilities", "NATGAS_HH", -1, "low", "Higher gas raises bills and dampens volumes"),
    _s("Multi-Utilities", "NATGAS_HH", -1, "low", "Mixed fuel exposure"),
    _s(
        "Independent Power and Renewable Electricity Producers",
        "NATGAS_HH",
        1,
        "medium",
        "Renewables earn more when gas sets a higher power price",
    ),
    _s(
        "Independent Power and Renewable Electricity Producers",
        "NATGAS_EU",
        1,
        "medium",
        "European power prices are set by gas",
    ),
    # Consumer staples: agricultural inputs
    _s("Consumer Staples", "WHEAT", -1, "medium", "Grain is a core input for food producers"),
    _s("Consumer Staples", "CORN", -1, "medium", "Corn drives feed and sweetener cost"),
    _s("Consumer Staples", "SUGAR", -1, "medium", "Sugar is a key input for beverages and confectionery"),
    _s("Consumer Staples", "COFFEE", -1, "medium", "Coffee roasters and cafes absorb bean prices"),
    _s("Consumer Staples", "COCOA", -1, "medium", "Chocolate makers face cocoa cost"),
    _s("Consumer Staples", "PALM_OIL", -1, "low", "Vegetable oils feed into packaged food"),
    _s("Food Products", "WHEAT", -1, "high", "Flour and bakery margins compress with wheat"),
    _s("Food Products", "CORN", -1, "medium", "Corn is the main feed and sweetener input"),
    _s("Food Products", "SOYBEANS", -1, "medium", "Soy meal and oil are protein and fat inputs"),
    _s("Food Products", "COCOA", -1, "high", "Cocoa is the largest input for chocolate makers"),
    _s("Food Products", "SUGAR", -1, "medium", "Sugar is a key sweetener input"),
    _s("Food Products", "LIVE_CATTLE", -1, "medium", "Meat packers pay more for cattle"),
    _s("Food Products", "LEAN_HOGS", -1, "medium", "Meat packers pay more for hogs"),
    _s("Beverages", "SUGAR", -1, "medium", "Sweeteners are a large input for soft drinks"),
    _s("Beverages", "COFFEE", -1, "medium", "Coffee chains and roasters absorb bean prices"),
    _s("Beverages", "ALUMINIUM", -1, "low", "Cans are an aluminium cost"),
    _s("Hotels, Restaurants & Leisure", "LIVE_CATTLE", -1, "low", "Beef is a major restaurant input"),
    _s("Hotels, Restaurants & Leisure", "COFFEE", -1, "low", "Cafes absorb bean cost"),
    _s("Food & Staples Retailing", "WHEAT", -1, "low", "Food inflation squeezes grocer margins before pass-through"),
    # Agriculture producers benefit from grain prices
    _s("Agricultural Products", "WHEAT", 1, "high", "Grain merchants and farmers earn more at higher prices"),
    _s("Agricultural Products", "CORN", 1, "high", "Corn producers and processors benefit"),
    _s("Agricultural Products", "SOYBEANS", 1, "high", "Oilseed crushers and growers benefit"),
    _s("Agricultural Products", "PALM_OIL", 1, "high", "Plantation companies earn more at higher CPO prices"),
    _s("Agricultural Products", "SUGAR", 1, "medium", "Sugar mills benefit from higher prices"),
    # Autos and durable goods
    _s("Automobiles", "PALLADIUM", -1, "medium", "Catalytic converters use palladium"),
    _s("Automobiles", "PLATINUM", -1, "low", "Diesel catalysts use platinum"),
    _s("Automobiles", "ALUMINIUM", -1, "medium", "Body and powertrain parts use aluminium"),
    _s("Automobiles", "COPPER", -1, "low", "Wiring and EV motors use copper"),
    _s("Auto Components", "ALUMINIUM", -1, "medium", "Castings and components use aluminium"),
    _s("Auto Components", "PALLADIUM", -1, "medium", "Catalyst suppliers buy PGMs"),
    _s("Household Durables", "COPPER", -1, "low", "Appliances and housing fittings use copper"),
    _s("Textiles, Apparel & Luxury Goods", "COTTON", -1, "medium", "Cotton is the main fibre input"),
    # Industrials
    _s("Industrials", "COPPER", -1, "low", "Copper is an input to electrical equipment and machinery"),
    _s("Electrical Equipment", "COPPER", -1, "medium", "Cables, motors and transformers are copper intensive"),
    _s("Machinery", "IRON_ORE", -1, "low", "Steel cost follows iron ore"),
    _s("Building Products", "ALUMINIUM", -1, "low", "Windows and facades use aluminium"),
    _s("Aerospace & Defense", "ALUMINIUM", -1, "low", "Airframes use aluminium alloys"),
    # Technology
    _s("Semiconductors & Semiconductor Equipment", "TIN", -1, "low", "Solder uses tin"),
    _s("Electronic Equipment, Instruments & Components", "COPPER", -1, "low", "PCBs and connectors use copper"),
)


def write_sector_sensitivities(db: BearishDbBase) -> int:
    db.write_sector_sensitivities(list(SECTOR_COMMODITY_SENSITIVITIES))
    return len(SECTOR_COMMODITY_SENSITIVITIES)
