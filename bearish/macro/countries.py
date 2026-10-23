"""Country reference data shared by macro sources and the linking layer.

One row per country with the codes each provider expects, plus the name
spellings seen in asset tables (``equity.country``) so they can be mapped to
ISO-3.
"""

from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


class Country(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    iso3: str
    iso2: str
    name: str
    aliases: Tuple[str, ...] = Field(default=(), description="Other spellings seen in source data")
    eurostat_code: Optional[str] = Field(default=None, description="Eurostat geo code when it differs from ISO-2")
    euro_area: bool = False
    eu: bool = False
    oecd: bool = False
    region: str = Field(description="Coarse region used for roll-ups")
    priority: bool = Field(default=False, description="Fetched by default by ``bearish macro``")


# Priority = G7 + China + India + every country already supported by the
# equities pipeline (bearish.exchanges.exchanges.Countries).
COUNTRIES: Tuple[Country, ...] = (
    Country(
        iso3="USA",
        iso2="US",
        name="United States",
        aliases=("US", "USA", "United States of America"),
        oecd=True,
        region="North America",
        priority=True,
    ),
    Country(iso3="CAN", iso2="CA", name="Canada", oecd=True, region="North America", priority=True),
    Country(iso3="MEX", iso2="MX", name="Mexico", oecd=True, region="Latin America", priority=True),
    Country(iso3="BRA", iso2="BR", name="Brazil", aliases=("Brasil",), region="Latin America", priority=True),
    Country(iso3="ARG", iso2="AR", name="Argentina", region="Latin America", priority=True),
    Country(
        iso3="GBR",
        iso2="GB",
        name="United Kingdom",
        aliases=("UK", "Great Britain", "Britain"),
        eurostat_code="UK",
        oecd=True,
        region="Europe",
        priority=True,
    ),
    Country(iso3="DEU", iso2="DE", name="Germany", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="FRA", iso2="FR", name="France", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="ITA", iso2="IT", name="Italy", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="ESP", iso2="ES", name="Spain", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(
        iso3="NLD",
        iso2="NL",
        name="Netherlands",
        aliases=("The Netherlands", "Holland"),
        euro_area=True,
        eu=True,
        oecd=True,
        region="Europe",
        priority=True,
    ),
    Country(iso3="BEL", iso2="BE", name="Belgium", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="AUT", iso2="AT", name="Austria", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="PRT", iso2="PT", name="Portugal", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="FIN", iso2="FI", name="Finland", euro_area=True, eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="IRL", iso2="IE", name="Ireland", euro_area=True, eu=True, oecd=True, region="Europe"),
    Country(
        iso3="GRC", iso2="GR", name="Greece", eurostat_code="EL", euro_area=True, eu=True, oecd=True, region="Europe"
    ),
    Country(iso3="SWE", iso2="SE", name="Sweden", eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="DNK", iso2="DK", name="Denmark", eu=True, oecd=True, region="Europe", priority=True),
    Country(iso3="NOR", iso2="NO", name="Norway", oecd=True, region="Europe", priority=True),
    Country(iso3="CHE", iso2="CH", name="Switzerland", oecd=True, region="Europe", priority=True),
    Country(iso3="POL", iso2="PL", name="Poland", eu=True, oecd=True, region="Europe"),
    Country(iso3="RUS", iso2="RU", name="Russia", aliases=("Russian Federation",), region="Europe", priority=True),
    Country(iso3="TUR", iso2="TR", name="Turkey", aliases=("Türkiye", "Turkiye"), oecd=True, region="Middle East"),
    Country(iso3="ZAF", iso2="ZA", name="South Africa", region="Africa", priority=True),
    Country(iso3="SAU", iso2="SA", name="Saudi Arabia", region="Middle East"),
    Country(iso3="JPN", iso2="JP", name="Japan", oecd=True, region="Asia Pacific", priority=True),
    Country(
        iso3="CHN",
        iso2="CN",
        name="China",
        aliases=("People's Republic of China", "China (mainland)"),
        region="Asia Pacific",
        priority=True,
    ),
    Country(
        iso3="HKG",
        iso2="HK",
        name="Hong Kong",
        aliases=("Hong Kong SAR", "Hong Kong SAR, China"),
        region="Asia Pacific",
        priority=True,
    ),
    Country(
        iso3="TWN",
        iso2="TW",
        name="Taiwan",
        aliases=("Taiwan, China", "Chinese Taipei"),
        region="Asia Pacific",
        priority=True,
    ),
    Country(
        iso3="KOR",
        iso2="KR",
        name="South Korea",
        aliases=("Korea", "Korea, Republic of", "Republic of Korea", "Korea, Rep."),
        oecd=True,
        region="Asia Pacific",
        priority=True,
    ),
    Country(iso3="IND", iso2="IN", name="India", region="Asia Pacific", priority=True),
    Country(iso3="IDN", iso2="ID", name="Indonesia", region="Asia Pacific"),
    Country(iso3="SGP", iso2="SG", name="Singapore", region="Asia Pacific", priority=True),
    Country(iso3="AUS", iso2="AU", name="Australia", oecd=True, region="Asia Pacific", priority=True),
    Country(iso3="NZL", iso2="NZ", name="New Zealand", oecd=True, region="Asia Pacific", priority=True),
    # Further countries seen in asset tables (not fetched by default).
    Country(iso3="THA", iso2="TH", name="Thailand", region="Asia Pacific"),
    Country(iso3="ISR", iso2="IL", name="Israel", region="Middle East"),
    Country(iso3="VNM", iso2="VN", name="Vietnam", aliases=("Viet Nam",), region="Asia Pacific"),
    Country(iso3="MYS", iso2="MY", name="Malaysia", region="Asia Pacific"),
    Country(iso3="PHL", iso2="PH", name="Philippines", region="Asia Pacific"),
    Country(iso3="PAK", iso2="PK", name="Pakistan", region="Asia Pacific"),
    Country(iso3="BGD", iso2="BD", name="Bangladesh", region="Asia Pacific"),
    Country(iso3="LKA", iso2="LK", name="Sri Lanka", region="Asia Pacific"),
    Country(iso3="MNG", iso2="MN", name="Mongolia", region="Asia Pacific"),
    Country(iso3="KHM", iso2="KH", name="Cambodia", region="Asia Pacific"),
    Country(iso3="MMR", iso2="MM", name="Myanmar", aliases=("Burma",), region="Asia Pacific"),
    Country(iso3="PNG", iso2="PG", name="Papua New Guinea", region="Asia Pacific"),
    Country(iso3="MAC", iso2="MO", name="Macau", aliases=("Macao", "Macao SAR"), region="Asia Pacific"),
    Country(iso3="KAZ", iso2="KZ", name="Kazakhstan", region="Asia Pacific"),
    Country(iso3="KGZ", iso2="KG", name="Kyrgyzstan", region="Asia Pacific"),
    Country(iso3="AZE", iso2="AZ", name="Azerbaijan", region="Asia Pacific"),
    Country(iso3="GEO", iso2="GE", name="Georgia", region="Europe"),
    Country(iso3="AFG", iso2="AF", name="Afghanistan", region="Asia Pacific"),
    Country(iso3="CHL", iso2="CL", name="Chile", region="Latin America"),
    Country(iso3="PER", iso2="PE", name="Peru", region="Latin America"),
    Country(iso3="COL", iso2="CO", name="Colombia", region="Latin America"),
    Country(iso3="VEN", iso2="VE", name="Venezuela", region="Latin America"),
    Country(iso3="URY", iso2="UY", name="Uruguay", region="Latin America"),
    Country(iso3="PAN", iso2="PA", name="Panama", region="Latin America"),
    Country(iso3="CRI", iso2="CR", name="Costa Rica", region="Latin America"),
    Country(iso3="DOM", iso2="DO", name="Dominican Republic", region="Latin America"),
    Country(iso3="JAM", iso2="JM", name="Jamaica", region="Latin America"),
    Country(iso3="BRB", iso2="BB", name="Barbados", region="Latin America"),
    Country(iso3="BHS", iso2="BS", name="Bahamas", aliases=("The Bahamas",), region="Latin America"),
    Country(iso3="BMU", iso2="BM", name="Bermuda", region="North America"),
    Country(iso3="CYM", iso2="KY", name="Cayman Islands", region="Latin America"),
    Country(
        iso3="VGB",
        iso2="VG",
        name="British Virgin Islands",
        aliases=("Virgin Islands, British",),
        region="Latin America",
    ),
    Country(
        iso3="VIR",
        iso2="VI",
        name="U.S. Virgin Islands",
        aliases=("US Virgin Islands", "Virgin Islands, U.S."),
        region="Latin America",
    ),
    Country(iso3="AIA", iso2="AI", name="Anguilla", region="Latin America"),
    Country(iso3="BLZ", iso2="BZ", name="Belize", region="Latin America"),
    Country(iso3="SUR", iso2="SR", name="Suriname", region="Latin America"),
    Country(iso3="GUF", iso2="GF", name="French Guiana", region="Latin America"),
    Country(iso3="FLK", iso2="FK", name="Falkland Islands", region="Latin America"),
    Country(iso3="CUW", iso2="CW", name="Curacao", aliases=("Netherlands Antilles", "Curaçao"), region="Latin America"),
    Country(iso3="GRL", iso2="GL", name="Greenland", region="North America"),
    Country(iso3="LUX", iso2="LU", name="Luxembourg", euro_area=True, eu=True, oecd=True, region="Europe"),
    Country(iso3="HUN", iso2="HU", name="Hungary", eu=True, oecd=True, region="Europe"),
    Country(iso3="CZE", iso2="CZ", name="Czech Republic", aliases=("Czechia",), eu=True, oecd=True, region="Europe"),
    Country(
        iso3="SVK",
        iso2="SK",
        name="Slovakia",
        aliases=("Slovak Republic",),
        euro_area=True,
        eu=True,
        oecd=True,
        region="Europe",
    ),
    Country(iso3="SVN", iso2="SI", name="Slovenia", euro_area=True, eu=True, oecd=True, region="Europe"),
    Country(iso3="ROU", iso2="RO", name="Romania", aliases=("Rumania",), eu=True, region="Europe"),
    Country(iso3="BGR", iso2="BG", name="Bulgaria", eu=True, region="Europe"),
    Country(iso3="HRV", iso2="HR", name="Croatia", euro_area=True, eu=True, region="Europe"),
    Country(iso3="SRB", iso2="RS", name="Serbia", region="Europe"),
    Country(iso3="BIH", iso2="BA", name="Bosnia and Herzegovina", aliases=("Bosnia",), region="Europe"),
    Country(iso3="MNE", iso2="ME", name="Montenegro", region="Europe"),
    Country(iso3="MKD", iso2="MK", name="North Macedonia", aliases=("Macedonia",), region="Europe"),
    Country(iso3="UKR", iso2="UA", name="Ukraine", region="Europe"),
    Country(iso3="LTU", iso2="LT", name="Lithuania", euro_area=True, eu=True, oecd=True, region="Europe"),
    Country(iso3="LVA", iso2="LV", name="Latvia", euro_area=True, eu=True, oecd=True, region="Europe"),
    Country(iso3="EST", iso2="EE", name="Estonia", euro_area=True, eu=True, oecd=True, region="Europe"),
    Country(iso3="ISL", iso2="IS", name="Iceland", oecd=True, region="Europe"),
    Country(iso3="CYP", iso2="CY", name="Cyprus", euro_area=True, eu=True, region="Europe"),
    Country(iso3="MLT", iso2="MT", name="Malta", euro_area=True, eu=True, region="Europe"),
    Country(iso3="MCO", iso2="MC", name="Monaco", region="Europe"),
    Country(iso3="LIE", iso2="LI", name="Liechtenstein", region="Europe"),
    Country(iso3="JEY", iso2="JE", name="Jersey", region="Europe"),
    Country(iso3="GGY", iso2="GG", name="Guernsey", region="Europe"),
    Country(iso3="IMN", iso2="IM", name="Isle of Man", region="Europe"),
    Country(iso3="GIB", iso2="GI", name="Gibraltar", region="Europe"),
    Country(
        iso3="ARE", iso2="AE", name="United Arab Emirates", aliases=("UAE", "Dubai", "Abu Dhabi"), region="Middle East"
    ),
    Country(iso3="KWT", iso2="KW", name="Kuwait", region="Middle East"),
    Country(iso3="QAT", iso2="QA", name="Qatar", region="Middle East"),
    Country(iso3="OMN", iso2="OM", name="Oman", region="Middle East"),
    Country(iso3="BHR", iso2="BH", name="Bahrain", region="Middle East"),
    Country(iso3="JOR", iso2="JO", name="Jordan", region="Middle East"),
    Country(iso3="LBN", iso2="LB", name="Lebanon", region="Middle East"),
    Country(iso3="IRQ", iso2="IQ", name="Iraq", region="Middle East"),
    Country(
        iso3="PSE",
        iso2="PS",
        name="Palestine",
        aliases=("Palestinian Territories", "West Bank and Gaza"),
        region="Middle East",
    ),
    Country(iso3="EGY", iso2="EG", name="Egypt", region="Africa"),
    Country(iso3="NGA", iso2="NG", name="Nigeria", region="Africa"),
    Country(iso3="KEN", iso2="KE", name="Kenya", region="Africa"),
    Country(iso3="MAR", iso2="MA", name="Morocco", region="Africa"),
    Country(iso3="TUN", iso2="TN", name="Tunisia", region="Africa"),
    Country(iso3="MUS", iso2="MU", name="Mauritius", region="Africa"),
    Country(iso3="ZWE", iso2="ZW", name="Zimbabwe", region="Africa"),
    Country(iso3="BWA", iso2="BW", name="Botswana", region="Africa"),
    Country(iso3="NAM", iso2="NA", name="Namibia", region="Africa"),
    Country(iso3="GHA", iso2="GH", name="Ghana", region="Africa"),
    Country(iso3="TZA", iso2="TZ", name="Tanzania", region="Africa"),
    Country(iso3="UGA", iso2="UG", name="Uganda", region="Africa"),
    Country(iso3="ZMB", iso2="ZM", name="Zambia", region="Africa"),
    Country(iso3="MWI", iso2="MW", name="Malawi", region="Africa"),
    Country(iso3="MOZ", iso2="MZ", name="Mozambique", region="Africa"),
    Country(iso3="RWA", iso2="RW", name="Rwanda", region="Africa"),
    Country(iso3="SEN", iso2="SN", name="Senegal", region="Africa"),
    Country(iso3="GAB", iso2="GA", name="Gabon", region="Africa"),
    Country(iso3="CIV", iso2="CI", name="Ivory Coast", aliases=("Cote d'Ivoire", "Côte d'Ivoire"), region="Africa"),
    Country(iso3="REU", iso2="RE", name="Reunion", aliases=("Réunion",), region="Africa"),
    # Conflict- and sanctions-relevant countries (no listed equities needed).
    Country(
        iso3="IRN",
        iso2="IR",
        name="Iran",
        aliases=("Iran, Islamic Republic of", "Islamic Republic of Iran"),
        region="Middle East",
    ),
    Country(
        iso3="PRK",
        iso2="KP",
        name="North Korea",
        aliases=("Korea, North", "Korea, Dem. People's Rep.", "Democratic People's Republic of Korea", "DPRK"),
        region="Asia Pacific",
    ),
    Country(iso3="SYR", iso2="SY", name="Syria", aliases=("Syrian Arab Republic",), region="Middle East"),
    Country(iso3="BLR", iso2="BY", name="Belarus", region="Europe"),
    Country(iso3="YEM", iso2="YE", name="Yemen", aliases=("Yemen, Rep.",), region="Middle East"),
    Country(iso3="CUB", iso2="CU", name="Cuba", region="Latin America"),
    Country(iso3="ARM", iso2="AM", name="Armenia", region="Europe"),
    Country(iso3="LBY", iso2="LY", name="Libya", region="Africa"),
    Country(iso3="SDN", iso2="SD", name="Sudan", region="Africa"),
    Country(iso3="XKX", iso2="XK", name="Kosovo", region="Europe"),
)

# Aggregates that providers publish as if they were countries.
REGIONS: Dict[str, str] = {
    "WLD": "World",
    "EA20": "Euro area",
    "EU27": "European Union",
    "OECD": "OECD total",
    "G7": "G7",
    "G20": "G20",
    # Fama-French regional portfolios
    "DM": "Developed markets",
    "EM": "Emerging markets",
    "EUR": "Europe",
    "APXJ": "Asia Pacific ex Japan",
    "NAM": "North America",
    "LATAM": "Latin America",
}


@lru_cache(maxsize=1)
def _name_index() -> Dict[str, Country]:
    index: Dict[str, Country] = {}
    for country in COUNTRIES:
        for key in (country.iso3, country.iso2, country.name, *country.aliases):
            index[key.casefold()] = country
    return index


def country_from(value: Optional[str]) -> Optional[Country]:
    """Resolve an ISO-2/ISO-3 code or a name spelling to a Country (None if unknown)."""
    if not value:
        return None
    return _name_index().get(value.strip().casefold())


def iso3_from(value: Optional[str]) -> Optional[str]:
    country = country_from(value)
    return country.iso3 if country else None


def priority_countries() -> List[Country]:
    return [country for country in COUNTRIES if country.priority]


def countries_by_iso3(iso3_codes: Optional[List[str]] = None) -> List[Country]:
    if not iso3_codes:
        return priority_countries()
    wanted = {code.upper() for code in iso3_codes}
    return [country for country in COUNTRIES if country.iso3 in wanted]
