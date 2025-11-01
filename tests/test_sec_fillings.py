from datetime import datetime

from bearish.database.crud import BearishDb
from bearish.models.sec.sec import Secs


def test_sec(bearish_db: BearishDb) -> None:
    secs = Secs.from_sec_13f_hr(
        "0001067983", date_=datetime.strptime("2024-10-01", "%Y-%m-%d").date()
    )
    assert secs.secs
    secs.write(bearish_db)


def test_sec_all(bearish_db: BearishDb) -> None:
    Secs.upload(bearish_db, date_=datetime.strptime("2023-10-01", "%Y-%m-%d").date())


def test_sec_all_price(bearish_db: BearishDb) -> None:
    Secs.update_values(bearish_db)
