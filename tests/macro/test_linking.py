from bearish.database.crud import BearishDb
from bearish.macro.countries import iso3_from
from bearish.macro.pipelines.linking import run_linking, write_country_references

# The 60 most frequent equity.country spellings in the reference database.
BEAR_DB_COUNTRY_SPELLINGS = [
    "United states", "Canada", "China", "Japan", "India", "United kingdom", "Australia", "South korea", "Germany",
    "Hong kong", "France", "Taiwan", "Sweden", "Thailand", "Brazil", "Singapore", "Israel", "Indonesia", "Vietnam",
    "Italy", "Switzerland", "Malaysia", "Poland", "Norway", "Mexico", "Turkey", "South africa", "Spain", "Denmark",
    "Netherlands", "Austria", "Finland", "Russia", "Chile", "Belgium", "Pakistan", "Greece", "Ireland", "New zealand",
    "Philippines", "Bangladesh", "Saudi arabia", "Sri lanka", "Argentina", "Luxembourg", "Bermuda", "Egypt", "Romania",
    "Cayman islands", "Kuwait", "Nigeria", "Jordan", "Portugal", "Cyprus", "Dubai", "Mauritius", "Qatar", "Peru",
    "Mongolia", "Bulgaria", "Czech republic", "United arab emirates", "Isle of man", "Macau", "Ivory coast",
]


def test_known_asset_country_spellings_resolve() -> None:
    unresolved = [spelling for spelling in BEAR_DB_COUNTRY_SPELLINGS if iso3_from(spelling) is None]
    assert not unresolved, unresolved
    assert iso3_from("Dubai") == "ARE"


def test_equity_country_view_resolves_fixture_assets(bearish_db_with_assets: BearishDb) -> None:
    write_country_references(bearish_db_with_assets)
    frame = bearish_db_with_assets.read_query("SELECT symbol, country, iso3 FROM equitycountry")
    assert not frame.empty
    unresolved = frame[frame["iso3"].isna()]["country"].dropna().unique().tolist()
    assert not unresolved, unresolved
    assert set(frame["iso3"].dropna()) >= {"USA", "CHN"}


def test_run_linking_writes_every_table(bearish_db_with_assets: BearishDb) -> None:
    counts = run_linking(bearish_db_with_assets)
    assert counts["countryref"] > 100
    assert counts["sectorcommoditysensitivity"] > 50
    assert counts["etfexposure"] >= 0
    assert len(bearish_db_with_assets.read_country_references()) == counts["countryref"]
