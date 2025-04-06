# 📉 Bearish

> A lightweight stock data fetching tool that stores market data in SQLite using a common format.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg?logo=python)](https://www.python.org/) [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![GitHub Stars](https://img.shields.io/github/stars/your-repo/bearish?style=social)](https://github.com/your-repo/bearish)

## ✨ Features
✅ Fetch stock data from multiple sources 📊  
✅ Store data in an SQLite database 🗄️  
✅ Support for multiple markets and countries 🌍  
✅ Simple command-line interface 🖥️  

## 📥 Installation
Install Bearish using `pip`:

```sh
pip install bearishpy
```

## 🚀 Usage

### 📌 Fetch and Store Tickers
To get and store stock tickers from different markets and countries, run:

```sh 
bearish tickers /path/to/sqlite/db France Germany --api-keys=config.json
```

### 📌 Fetch Stock Prices
To retrieve stock prices from different markets, use:

```sh
bearish prices /path/to/sqlite/db France Germany --api-keys=config.json
```

## 🔑 API Keys Configuration
Make sure to provide a `config.json` file with your API keys to fetch data from various sources.

Example `config.json`:
```json
{
  "FMPAssets": "your Financial Modeling Prep API key", 
  "FMP": "your Financial Modeling Prep API key", 
  "AlphaVantage": "your Alphavantage API key",
  "Tiingo": "yout Tiingo API key"
}

```

## 🤝 Contributing
Contributions are welcome! Feel free to submit a pull request or open an issue.

## 📜 License
This project is licensed under the **MIT License**.

🚀 Happy Investing! 📈


poetry run python ./bearish/main.py run  ./test.db Germany US --filters NVDA,RHM.DE --api-keys=config.json