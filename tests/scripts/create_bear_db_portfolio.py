from pathlib import Path

from bearish.main import run, Options

if __name__ == "__main__":
    db_path = Path(__file__).parents[1] / "data" / "bear_portfolio.db"
    config_path = Path(__file__).parents[2] / "config.json"
    options = Options(etf=False, financials=False, sec=False)
    if db_path.exists():
        db_path.unlink()
    run(
        db_path,
        ["US"],
        filters="NVDA, AAPL, GOOG, MSFT, UNH, LLY, LMT, MRK, TSLA, VZ",
        api_keys=config_path,
        options=options,
    )
