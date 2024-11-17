import tempfile
from pathlib import Path

import pandas as pd
import pytest

from bearish.database.crud import BearishDb
from bearish.database.scripts.upgrade import upgrade


@pytest.fixture(scope="session")
def bearish_db() -> BearishDb:
    with tempfile.NamedTemporaryFile(delete=False, suffix="db") as file:
        return BearishDb(database_path=file.name)



@pytest.fixture(scope="session")
def equities_path() -> Path:
    return Path(__file__).parent.joinpath("data/equities.csv")

@pytest.fixture(scope="session")
def equities(equities_path: Path) -> pd.DataFrame:
    return pd.read_csv(equities_path)
