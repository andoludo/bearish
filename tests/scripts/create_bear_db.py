from pathlib import Path

from bearish.main import run

if __name__ == "__main__":
    db_path = Path(__file__).parents[1] / "data" / "bear.db"
    config_path = Path(__file__).parents[2] / "config.json"
    if db_path.exists():
        db_path.unlink()
    run(
        db_path,
        ["US"],
        filters="NVDA, AAPL, AMZN, KO, VRSN, V",
        api_keys=config_path,
        etf=False,
        index=False,
        sec=False,
    )
