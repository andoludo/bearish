import os
from pathlib import Path

from alembic import command
from alembic.config import Config

from bearish.database.settings import DATABASE_URL


def create_revision(database_url: str, message: str) -> None:
    os.environ.update({"DATABASE_URL": database_url})
    root_folder = Path(__file__).parents[1]
    alembic_cfg = Config(root_folder / "alembic" / "alembic.ini")
    alembic_cfg.set_main_option("script_location", str(root_folder / "alembic"))
    command.revision(alembic_cfg, message=message, autogenerate=True)


if __name__ == "__main__":
    message = "price_etf"
    create_revision(DATABASE_URL, message)
