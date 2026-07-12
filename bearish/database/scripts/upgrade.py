import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from bearish.database.settings import DATABASE_URL


def upgrade(database_url: str) -> None:
    root_folder = Path(__file__).parents[1]
    os.environ.update({"DATABASE_URL": database_url})
    alembic_cfg = Config(root_folder / "alembic" / "alembic.ini")
    alembic_cfg.set_main_option("script_location", str(root_folder / "alembic"))
    command.upgrade(alembic_cfg, "head")


if __name__ == "__main__":
    upgrade(DATABASE_URL)
