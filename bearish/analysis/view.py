from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel


from bearish.models.assets.base import ComponentDescription

if TYPE_CHECKING:
    from bearish.interface.interface import BearishDbBase


class View(ComponentDescription):
    view_name: Optional[str] = None

    def set_view_name(self, view_name: str) -> None:
        self.view_name = view_name


class BaseViews(BaseModel):
    view_name: str
    query: str

    def compute(self, bearish_db: "BearishDbBase") -> None:
        views = bearish_db.read_views(self.query)
        for view in views:
            view.set_view_name(self.view_name)
        bearish_db.write_views(views)
