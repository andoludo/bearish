import re
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING, Self

import pandas as pd
import requests  # type: ignore
from pydantic import BaseModel
from sec_cik_mapper import StockMapper  # type: ignore
from sec_edgar_downloader import Downloader  # type: ignore

from bearish.models.sec.ciks import CIKS

if TYPE_CHECKING:
    from bearish.database.crud import BearishDb


def normalize(s: str) -> str:
    s = s.upper()
    s = s.replace("COMMON STOCK", "")  # uppercase
    s = s.replace("COMMON SHARES", "")  # uppercase
    s = s.replace("CLASS A ORDINARY SHARES", "")  # uppercase
    s = s.replace("CLASS A COMMON STOCK", "")  # uppercase
    s = s.replace("INC", "")  # uppercase
    return re.sub(r"[^A-Z0-9]", "", s)


def company_ticker() -> Dict[str, str]:
    nasdaq_url = "https://www.nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
    other_url = "https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt"
    data_ = []
    headers = {"User-Agent": "YourName Contact@Email.com", "Accept": "text/plain"}
    mapper = StockMapper()

    for url in [nasdaq_url, other_url]:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = pd.read_csv(StringIO(response.text), delimiter="|")
        data = data.rename(columns={"ACT Symbol": "Symbol"})
        data_.append(data)
    data_all = pd.concat(data_, ignore_index=True)
    ticker_mapping = {
        normalize(str(e["Security Name"])): e["Symbol"]
        for e in data_all[["Symbol", "Security Name"]].to_dict(orient="records")
    }
    ticker_mapping.update(
        {normalize(n): t for t, n in mapper.ticker_to_company_name.items()}  # type: ignore
    )
    return ticker_mapping


TICKER_MAPPING = company_ticker()


class BaseSecShare(BaseModel):
    ticker: str
    previous_period: Optional[date] = None
    max_period: Optional[date] = None
    occurrences: Optional[int] = None
    prev_total_value: Optional[float] = None
    total_value: Optional[float] = None
    total_increase: Optional[float] = None
    prev_total_shares: Optional[float] = None
    total_shares: Optional[float] = None
    shares_increase: Optional[float] = None


class SecShareIncrease(BaseSecShare): ...


class Sec(BaseModel):
    name: Optional[str] = None
    ticker: Optional[str] = None
    cusip: Optional[str] = None
    shares: Optional[int] = None
    period: Optional[str] = None
    filed_date: Optional[str] = None
    source: Optional[str] = None
    company_name: Optional[str] = None
    value: Optional[float] = None

    def __hash__(self) -> int:
        return hash((self.name, self.source, self.period, self.filed_date, self.cusip))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Sec):
            return hash(self) == hash(other)
        return False

    def set_share(self, shares: int) -> Self:
        self.shares = shares
        return self


def _info_table_to_rows(
    sec_text: str, source: str, ticker_mapping: Optional[Dict[str, str]] = None
) -> List[Sec]:
    ticker_mapping = ticker_mapping or {}
    xml = re.search(  # type: ignore
        r"<DOCUMENT>.*?<TYPE>\s*INFORMATION TABLE.*?<XML>(.*?)</XML>.*?</DOCUMENT>",
        sec_text,
        re.DOTALL | re.IGNORECASE,
    ).group(1)
    ns = {"it": "http://www.sec.gov/edgar/document/thirteenf/informationtable"}
    root = ET.fromstring(xml.lstrip())  # noqa: S314
    period = re.search(r"CONFORMED PERIOD OF REPORT:\s+(\d{8})", sec_text)
    filed_date_ = re.search(r"FILED AS OF DATE:\s+(\d{8})", sec_text)
    company_name_ = re.search(r"COMPANY CONFORMED NAME:\s*([^\r\n]+)", sec_text)

    if not period:
        raise ValueError("period is required")
    per_dt = period.group(1)
    period_report = f"{per_dt[0:4]}-{per_dt[4:6]}-{per_dt[6:8]}"

    if not filed_date_:
        raise ValueError("Filed date is missing")
    filed_date__ = filed_date_.group(1)
    filed_date = f"{filed_date__[0:4]}-{filed_date__[4:6]}-{filed_date__[6:8]}"

    company_name = None
    if company_name_:
        company_name = company_name_.group(1)

    rows = []
    for t in root.findall(".//it:infoTable", ns):
        name = t.findtext("it:nameOfIssuer", default="", namespaces=ns).strip()
        cusip = t.findtext("it:cusip", default="", namespaces=ns).strip()
        # shares live inside shrsOrPrnAmt/sshPrnamt
        shares_text = t.findtext(
            "it:shrsOrPrnAmt/it:sshPrnamt", default="0", namespaces=ns
        )
        shares = int(float(shares_text))
        rows.append(
            Sec.model_validate(
                {
                    "name": name,
                    "cusip": cusip,
                    "shares": shares,
                    "period": period_report,
                    "source": source,
                    "filed_date": filed_date,
                    "ticker": ticker_mapping.get(normalize(name)),
                    "company_name": company_name,
                }
            )
        )
    return rows


def _query(symbols: List[str]) -> str:
    symbols_ = ",".join([f"'{s}'" for s in symbols])
    query = f"""WITH last_dates AS (SELECT DISTINCT date \
                                   FROM price \
                                   ORDER BY date DESC \
                                   LIMIT 3)
               SELECT date, symbol, close
               FROM price
               WHERE date IN (SELECT date FROM last_dates)
                 AND symbol IN ({symbols_})
               ORDER BY date DESC;"""
    return query


class Secs(BaseModel):
    secs: List[Sec]

    def write(self, bearish_db: "BearishDb") -> None:
        bearish_db.write_sec(self.secs)

    @classmethod
    def upload(cls, bearish_db: "BearishDb", date_: Optional[date] = None) -> None:
        for cik in CIKS:
            sec = cls.from_sec_13f_hr(cik, date_=date_)
            sec.write(bearish_db)
        cls.update_values(bearish_db)

    @classmethod
    def update_values(
        cls, bearish_db: "BearishDb", additional_tickers: Optional[List[str]] = None
    ) -> None:
        prices = {}
        additional_tickers = additional_tickers or []
        tickers = bearish_db.read_query(
            query="SELECT DISTINCT ticker from sec WHERE ticker NOT NULL"
        )
        tickers_ = [*tickers["ticker"].tolist(), *additional_tickers]
        batch_size = 100

        for i in range(0, len(tickers_), batch_size):
            batch = tickers_[i : i + batch_size]
            data = bearish_db.read_query(_query(batch))
            prices.update(
                {r["symbol"]: r["close"] for r in data.to_dict(orient="records")}
            )
        for symbol, price in prices.items():
            secs = bearish_db.read_sec(symbol)
            for sec in secs:
                sec.value = price * sec.shares
            bearish_db.write_sec(secs)
        sec_shares = bearish_db.read_sec_shares()
        bearish_db.write_sec_shares(sec_shares)

    @classmethod
    def from_sec_13f_hr(cls, source: str, date_: Optional[date] = None) -> "Secs":
        rows = []
        unique_secs = []
        groups = defaultdict(list)
        date__ = date_ or date.today() - timedelta(days=31 * 4)

        with tempfile.TemporaryDirectory() as tmpdir:
            dl = Downloader(
                "MyCompanyName", "email@example.com", download_folder=tmpdir
            )
            dl.get("13F-HR", source, after=date__.strftime("%Y-%m-%d"))
            for p in list(Path(tmpdir).rglob("*.txt")):
                rows.extend(
                    _info_table_to_rows(
                        p.read_text(), source, ticker_mapping=TICKER_MAPPING
                    )
                )
            for item in rows:
                groups[item].append(item)
            for key, values in groups.items():
                shares = sum([s.shares for s in values if s.shares is not None])
                unique_secs.append(key.set_share(shares))
        return cls(secs=unique_secs)
