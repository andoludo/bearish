import re
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from io import StringIO
from pathlib import Path
from typing import Optional, List, Dict, TYPE_CHECKING, Self

import pandas as pd
import requests  # type: ignore
from pydantic import BaseModel
from sec_cik_mapper import StockMapper  # type: ignore
from sec_edgar_downloader import Downloader  # type: ignore

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


class Sec(BaseModel):
    name: Optional[str] = None
    cusip: Optional[str] = None
    shares: Optional[int] = None
    period: Optional[str] = None
    ticker: Optional[str] = None
    source: Optional[str] = None

    def __hash__(self) -> int:
        return hash((self.name, self.cusip))

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
    period_report = None
    if period:
        per_dt = period.group(1)
        period_report = f"{per_dt[0:4]}-{per_dt[4:6]}-{per_dt[6:8]}"

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
                    "ticker": ticker_mapping.get(normalize(name)),
                }
            )
        )
    return rows


class Secs(BaseModel):
    secs: List[Sec]

    def write(self, bearish_db: "BearishDb") -> None:
        bearish_db.write_sec(self.secs)

    @classmethod
    def from_sec_13f_hr(cls, source: str) -> "Secs":
        rows = []
        unique_secs = []
        groups = defaultdict(list)
        with tempfile.TemporaryDirectory() as tmpdir:
            dl = Downloader(
                "MyCompanyName", "email@example.com", download_folder=tmpdir
            )
            dl.get("13F-HR", source, after="2025-07-07")
            for p in list(Path(tmpdir).rglob("*.txt")):
                rows.extend(
                    _info_table_to_rows(
                        p.read_text(), source, ticker_mapping=TICKER_MAPPING
                    )
                )
            for item in rows:
                groups[item].append(item)
            for sec in groups.values():
                shares = sum([s.shares for s in sec if s.shares is not None])
                unique_secs.append(sec[0].set_share(shares))
        return cls(secs=unique_secs)
