from bearish.database.crud import BearishDb
from bearish.models.sec.sec import Secs


def test_sec(bearish_db: BearishDb) -> None:
    secs = Secs.from_sec_13f_hr("0001067983")
    assert secs.secs
    secs.write(bearish_db)
