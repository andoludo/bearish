from datetime import datetime

from bearish.database.crud import BearishDb
from bearish.models.sec.sec import Secs


def test_sec(bear_db: BearishDb) -> None:
    secs = Secs.from_sec_13f_hr(
        "0001067983", date_=datetime.strptime("2024-10-01", "%Y-%m-%d").date()
    )
    assert secs.secs
    secs.write(bear_db)
