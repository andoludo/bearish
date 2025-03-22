from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator, validate_call

from bearish.models.base import Ticker
from bearish.models.query.query import AssetQuery
from bearish.types import Sources

Countries = Literal[
    "US",
    "Canada",
    "United Kingdom",
    "Germany",
    "France",
    "Netherlands",
    "Belgium",
    "Italy",
    "Spain",
    "Switzerland",
    "Sweden",
    "Denmark",
    "Norway",
    "Finland",
    "Portugal",
    "Austria",
    "Australia",
    "New Zealand",
    "Japan",
    "China",
    "Hong Kong",
    "Singapore",
    "India",
    "South Korea",
    "Taiwan",
    "Brazil",
    "Mexico",
    "Argentina",
    "Russia",
    "South Africa",
]

ExchangeType = Literal["suffixes", "aliases"]


class ExchangeQuery(BaseModel):
    suffixes: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)

    def to_suffixes_sql_statement(self) -> str:
        return f"""({' OR '.join([f"symbol LIKE '%{suffix}'" for suffix in self.suffixes])})"""

    def to_aliases_sql_statement(self) -> str:
        return f"""({','.join([f"'{alias}'" for alias in self.aliases])})"""

    def to_sources_sql_statement(self) -> str:
        if not self.sources:
            return ""
        return f"""({','.join([f"'{source}'" for source in self.sources])})"""

    def included(self, ticker: Ticker) -> bool:
        return (
            any(ticker.symbol.endswith(suffix) for suffix in self.suffixes)
            or ticker.exchange in self.aliases
        )


class Exchange(ExchangeQuery):
    name: str

    @model_validator(mode="after")
    def _model_validator(self) -> "Exchange":
        if not self.aliases and not self.suffixes:
            raise ValueError("At least one of names or suffixes must be provided")
        return self


class CountryExchanges(BaseModel):
    country: Countries
    exchanges: List[Exchange]


class Exchanges(BaseModel):
    exchanges: List[CountryExchanges] = Field(default_factory=list)

    @validate_call
    def get_exchanges(
        self, countries: List[Countries], type: ExchangeType = "suffixes"
    ) -> List[str]:
        return [
            suffix
            for country in countries
            for suffix in self._get_exchanges(country, type)
        ]

    def _get_exchanges(
        self, country: Countries, type: ExchangeType = "suffixes"
    ) -> List[str]:
        return [
            suffix
            for country_exchange in self.exchanges
            for exchange in country_exchange.exchanges
            for suffix in getattr(exchange, type)
            if country_exchange.country == country
        ]

    @validate_call
    def get_exchange_query(
        self, countries: List[Countries], sources: Optional[List[Sources]] = None
    ) -> ExchangeQuery:
        sources = sources or []
        suffixes = self.get_exchanges(countries, "suffixes")
        aliases = self.get_exchanges(countries, "aliases")
        return ExchangeQuery(suffixes=suffixes, aliases=aliases, sources=sources)

    def ticker_belongs_to_countries(
        self, ticker: Ticker, countries: List[Countries]
    ) -> bool:
        exchange_query = self.get_exchange_query(countries)
        return exchange_query.included(ticker)

    def get_asset_query(
        self, asset_query: AssetQuery, countries: List[Countries]
    ) -> AssetQuery:
        exchange_query = self.get_exchange_query(countries)
        symbols = asset_query.symbols.filter(exchange_query.included)
        asset_query_ = AssetQuery.model_validate(asset_query.model_dump())
        asset_query_.symbols = symbols
        return asset_query_


def exchanges_factory() -> Exchanges:
    return Exchanges(
        exchanges=[
            CountryExchanges(
                country="US",
                exchanges=[
                    Exchange(
                        name="NASDAQ",
                        suffixes=[".OQ"],
                        aliases=[
                            "NMS",
                            "NCM",
                            "NAS",
                            "NASDAQ",
                            "Nasdaq",
                            "NASDAQ Global Market",
                            "NASDAQ Capital Market",
                            "NASDAQ Global Select",
                            "NASDAQ Capital Markets",
                            "NASDAQ Stock Exchange",
                            "NASDAQ Stock Market",
                        ],
                    ),
                    Exchange(
                        name="New York Stock Exchange",
                        suffixes=[".N"],
                        aliases=[
                            "NYQ",
                            "NYS",
                            "New York Stock Exchange",
                            "New York Stock Exchange Arca",
                            "NYSE",
                            "NYSE American",
                            "American Stock Exchange",
                            "AMEX",
                            "NYSE Arca",
                        ],
                    ),
                    Exchange(name="NYSE American", suffixes=[".A"]),
                ],
            ),
            CountryExchanges(
                country="Canada",
                exchanges=[
                    Exchange(name="Toronto Stock Exchange", suffixes=[".TO"]),
                    Exchange(name="TSX Venture Exchange", suffixes=[".V"]),
                ],
            ),
            CountryExchanges(
                country="United Kingdom",
                exchanges=[Exchange(name="London Stock Exchange", suffixes=[".L"])],
            ),
            CountryExchanges(
                country="Germany",
                exchanges=[
                    Exchange(name="Deutsche Börse Xetra", suffixes=[".DE"]),
                    Exchange(name="Frankfurt Stock Exchange", suffixes=[".F"]),
                    Exchange(name="Munich Stock Exchange", suffixes=[".MU"]),
                    Exchange(name="Stuttgart Stock Exchange", suffixes=[".SG"]),
                ],
            ),
            CountryExchanges(
                country="France",
                exchanges=[Exchange(name="Euronext Paris", suffixes=[".PA"])],
            ),
            CountryExchanges(
                country="Netherlands",
                exchanges=[Exchange(name="Euronext Amsterdam", suffixes=[".AS"])],
            ),
            CountryExchanges(
                country="Belgium",
                exchanges=[Exchange(name="Euronext Brussels", suffixes=[".BR"])],
            ),
            CountryExchanges(
                country="Italy",
                exchanges=[Exchange(name="Borsa Italiana", suffixes=[".MI"])],
            ),
            CountryExchanges(
                country="Spain",
                exchanges=[Exchange(name="Bolsa de Madrid", suffixes=[".MC"])],
            ),
            CountryExchanges(
                country="Switzerland",
                exchanges=[Exchange(name="SIX Swiss Exchange", suffixes=[".SW"])],
            ),
            CountryExchanges(
                country="Sweden",
                exchanges=[Exchange(name="Stockholm Stock Exchange", suffixes=[".ST"])],
            ),
            CountryExchanges(
                country="Denmark",
                exchanges=[
                    Exchange(name="Copenhagen Stock Exchange", suffixes=[".CO"])
                ],
            ),
            CountryExchanges(
                country="Norway",
                exchanges=[Exchange(name="Oslo Stock Exchange", suffixes=[".OL"])],
            ),
            CountryExchanges(
                country="Finland",
                exchanges=[Exchange(name="Helsinki Stock Exchange", suffixes=[".HE"])],
            ),
            CountryExchanges(
                country="Portugal",
                exchanges=[Exchange(name="Euronext Lisbon", suffixes=[".LS"])],
            ),
            CountryExchanges(
                country="Austria",
                exchanges=[Exchange(name="Vienna Stock Exchange", suffixes=[".VI"])],
            ),
            CountryExchanges(
                country="Australia",
                exchanges=[
                    Exchange(name="Australian Securities Exchange", suffixes=[".AX"])
                ],
            ),
            CountryExchanges(
                country="New Zealand",
                exchanges=[Exchange(name="New Zealand Exchange", suffixes=[".NZ"])],
            ),
            CountryExchanges(
                country="Japan",
                exchanges=[Exchange(name="Tokyo Stock Exchange", suffixes=[".T"])],
            ),
            CountryExchanges(
                country="China",
                exchanges=[
                    Exchange(name="Shanghai Stock Exchange", suffixes=[".SS"]),
                    Exchange(name="Shenzhen Stock Exchange", suffixes=[".SZ"]),
                ],
            ),
            CountryExchanges(
                country="Hong Kong",
                exchanges=[Exchange(name="Hong Kong Stock Exchange", suffixes=[".HK"])],
            ),
            CountryExchanges(
                country="Singapore",
                exchanges=[Exchange(name="Singapore Exchange", suffixes=[".SI"])],
            ),
            CountryExchanges(
                country="India",
                exchanges=[
                    Exchange(name="National Stock Exchange", suffixes=[".NS"]),
                    Exchange(name="Bombay Stock Exchange", suffixes=[".BO"]),
                ],
            ),
            CountryExchanges(
                country="South Korea",
                exchanges=[Exchange(name="Korea Exchange", suffixes=[".KS"])],
            ),
            CountryExchanges(
                country="Taiwan",
                exchanges=[Exchange(name="Taiwan Stock Exchange", suffixes=[".TW"])],
            ),
            CountryExchanges(
                country="Brazil",
                exchanges=[
                    Exchange(name="B3 - Brazil Stock Exchange", suffixes=[".SA"])
                ],
            ),
            CountryExchanges(
                country="Mexico",
                exchanges=[Exchange(name="Mexican Stock Exchange", suffixes=[".MX"])],
            ),
            CountryExchanges(
                country="Argentina",
                exchanges=[
                    Exchange(name="Buenos Aires Stock Exchange", suffixes=[".BA"])
                ],
            ),
            CountryExchanges(
                country="Russia",
                exchanges=[Exchange(name="Moscow Exchange", suffixes=[".ME"])],
            ),
            CountryExchanges(
                country="South Africa",
                exchanges=[
                    Exchange(name="Johannesburg Stock Exchange", suffixes=[".JO"])
                ],
            ),
        ]
    )
