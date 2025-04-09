from bearish.analysis.view import BaseViews, TestView
from bearish.database.crud import BearishDb


def test_base_views(bearish_db_with_analysis: BearishDb) -> None:

    views = BaseViews(
        view_name="test", query="SELECT symbol, name, source FROM analysis"
    )
    views.compute(bearish_db_with_analysis)
    views = bearish_db_with_analysis.read_query("SELECT * FROM view")
    assert not views.empty


def test_views(bear_db: BearishDb):
    TestView().compute(bear_db)
    query = """
    SELECT * FROM view;
    """
    data = bear_db.read_query(query)
    assert not data.empty
