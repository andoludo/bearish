from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "bearish.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
