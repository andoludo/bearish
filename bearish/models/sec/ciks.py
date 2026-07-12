from pathlib import Path
from typing import List, Optional

import pandas as pd


INITIAL_CIKS = [
    "0001081316",
    "0001274791",
    "0000829771",
    "0001067983",
    "0000109694",
    "0001015867",
    "0000895421",
    "0001364742",
    "0000880052",
    "0000102909",
    "0000735286",
    "0000093751",
    "0000315066",
    "0000080255",
    "0000017283",
    "0001562230",
    "0001214717",
    "0001009268",
    "0001179392",
    "0001037389",
    "0001350694",
    "0001423053",
    "0001167483",
    "0001336528",
    "0000921669",
    "0001061768",
    "0001103804",
    "0001603466",
    "0000070858",
]


def _read_tsv(ciks: Optional[List[str]] = None) -> list[str]:
    ciks = ciks or []
    data = pd.read_csv(Path(__file__).parent.joinpath("SUBMISSION.tsv"), sep="\t")
    return list(map(str, {*data["CIK"].tolist(), *ciks}))


CIKS = _read_tsv(INITIAL_CIKS)
