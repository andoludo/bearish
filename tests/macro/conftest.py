from pathlib import Path

import pytest

MACRO_DATA_DIR = Path(__file__).parents[1] / "data" / "macro"


@pytest.fixture
def macro_data_dir() -> Path:
    return MACRO_DATA_DIR
