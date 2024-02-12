from bearish.scrapers.model import unflatten_json, Ticker


def test_screener(investing_record, trading_record):
    investing = unflatten_json(Ticker, investing_record)
    trading = unflatten_json(Ticker, trading_record)
    a = 12


def test_ticker(ticker_trading):
    income_statement_trading = unflatten_json(Ticker, ticker_trading)
    a = 12


def test_unflatten_json(screener_investing, screener_trading):
    nested_data = unflatten_json(Ticker, screener_trading)
    assert nested_data["fundamental"]["ratios"]["price_earning_ratio"]


#
#
# def test_ticker_from_record(investing_record):
#     ticker = Ticker.from_record(investing_record)
#     assert ticker.fundamental.ratios.price_earning_ratio
#
#
# def test_ticker_from_csv(investing_file_path):
#     tickers = Ticker.from_csv(investing_file_path)
#     assert len(tickers) > 1
#     assert tickers[0].fundamental.ratios.price_earning_ratio
#
#
# def test_ticker_trading_from_csv(trading_file_path):
#     tickers = Ticker.from_csv(trading_file_path)
#     assert len(tickers) > 1
#     assert tickers[0].fundamental.ratios.price_earning_ratio
#
# def test_instantiate():
#     path = Path(
#         "/home/aan/Documents/stocks/tests/scrapers/bearish/investing/investingtickerscraper/belgacom/data_2024_01_24_18_27.pkl"
#     )
#     tickers = Ticker.from_csv("/home/aan/Documents/stocks/tests/scrapers/bearish/investing/investingscreenerscraper/data_34_2024_01_24_17_48.csv")
#     prx = [t for t in tickers if t.reference == "belgacom"][0]
#     with path.open(mode="rb") as f:
#         data = pickle.load(f)
#     d = {}
#     for name, value in data.items():
#         if not isinstance(name, tuple) or not np.isnan(name):
#             d[str(name)] = value
#
#     data = unflatten_json(Ticker, d)
#     prx_2 = Ticker(**data)
#     merge(Ticker, prx, prx_2)
#
#
# def test_load_file():
#     path = Path("/home/aan/Documents/stocks/tests/scrapers/bearish/investing/investingtickerscraper/ucb/data_2024_01_25_09_31.pkl")
#     with path.open(mode="rb") as f:
#         data = pickle.load(f)
#         d = {}
#         for name, value in data.items():
#             if not isinstance(name, tuple) or not np.isnan(name):
#                 d[str(name)] = value
#     data = unflatten_json(Ticker, d)
#     Ticker(**data)
#     a = 12
#
# def test_create_db_json():
#     tickers = Ticker.from_csv(
#         "/home/aan/Documents/stocks/tests/scrapers/bearish/investing/investingscreenerscraper/data_34_2024_01_24_17_48.csv")
#     stock_directory = "/home/aan/Documents/stocks/tests/scrapers/bearish/investing/investingtickerscraper"
#     db_json = []
#     for ticker in tickers:
#         path = Path(stock_directory) / ticker.reference
#         if path.exists():
#             list_of_files = glob.glob(f"{path}/*")  # * means all if need specific format then *.csv
#             latest_file_path = Path(max(list_of_files, key=os.path.getctime))
#             with latest_file_path.open(mode="rb") as f:
#                 data = pickle.load(f)
#                 d = {}
#                 for name, value in data.items():
#                     if not isinstance(name, tuple) or not np.isnan(name):
#                         d[str(name)] = value
#             data = unflatten_json(Ticker, d)
#             ticker_ = Ticker(**data)
#             merge(Ticker, ticker, ticker_)
#             db_json.append(ticker.model_dump())
#     a = 12
