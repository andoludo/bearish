"""Form 13F institutional holdings from the SEC's quarterly bulk data sets.

Instead of downloading every manager's filing, the SEC publishes one zip per
filing window (quarterly up to 2024, then three-month windows such as
``01jun2026-31aug2026``) with structured tables: ``SUBMISSION`` (who filed
what for which quarter), ``COVERPAGE`` (manager name, amendment flags) and
``INFOTABLE`` (one row per position). One ~100 MB download therefore covers
every 13F filer for a quarter.

What is stored:

* ``holding13f`` — per-manager positions, for the managers selected
  (explicit CIKs and/or the top N by reported value), so the table stays a
  few hundred thousand rows per quarter rather than millions.
* ``holding13fsummary`` — for every security: number of holders, total
  shares/value, and flows against the prior quarter (new and closed holders,
  share and value change) computed across all filers.

Values are USD; reports filed before 3 January 2023 state thousands and later
ones dollars, which is normalised here. Only share positions
(``SSHPRNAMTTYPE == SH``) are kept; principal-amount rows (bonds) are
dropped. Amendments: a ``RESTATEMENT`` replaces the manager's original report
for that quarter, ``NEW HOLDINGS`` rows are added to it.
"""

import datetime
import io
import logging
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, cast

import pandas as pd
import requests
from pydantic import BaseModel, ConfigDict, Field

from bearish.interface.interface import BearishDbBase
from bearish.models.sec.holdings import Holding13F, Holding13FSummary
from bearish.sources.edgar_filings import HEADERS

logger = logging.getLogger(__name__)

DATA_SETS_URL = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
SEC_ROOT = "https://www.sec.gov"
VALUE_IN_DOLLARS_FROM = datetime.date(2023, 1, 1)
HOLDING_FORMS = ("13F-HR", "13F-HR/A")
CHUNK_ROWS = 500_000
_MONTHS = {
    m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)
}
_WINDOW = re.compile(r"(\d{2})([a-z]{3})(\d{4})-(\d{2})([a-z]{3})(\d{4})_form13f\.zip$")
_QUARTER = re.compile(r"(\d{4})q([1-4])_form13f\.zip$")
_HREF = re.compile(r'href="([^"]*form-13f-data-sets/[^"]*_form13f\.zip)"')


class DataSetRef(BaseModel):
    """One downloadable data set and the filing-date window it covers."""

    model_config = ConfigDict(frozen=True)

    name: str
    url: str
    start: datetime.date
    end: datetime.date


def parse_data_set_index(html: str) -> List[DataSetRef]:
    """Data sets linked from the SEC page, newest filing window first."""
    refs: Dict[str, DataSetRef] = {}
    for href in _HREF.findall(html):
        name = href.rsplit("/", 1)[-1]
        if match := _WINDOW.search(name):
            d1, m1, y1, d2, m2, y2 = match.groups()
            start = datetime.date(int(y1), _MONTHS[m1], int(d1))
            end = datetime.date(int(y2), _MONTHS[m2], int(d2))
        elif match := _QUARTER.search(name):
            year, quarter = int(match.group(1)), int(match.group(2))
            start = datetime.date(year, 3 * (quarter - 1) + 1, 1)
            end = (datetime.date(year + quarter // 4, (3 * quarter) % 12 + 1, 1)) - datetime.timedelta(days=1)
        else:
            continue
        url = href if href.startswith("http") else SEC_ROOT + href
        refs.setdefault(name, DataSetRef(name=name, url=url, start=start, end=end))
    return sorted(refs.values(), key=lambda ref: ref.end, reverse=True)


def list_data_sets(timeout: int = 60) -> List[DataSetRef]:
    response = requests.get(DATA_SETS_URL, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return parse_data_set_index(response.text)


def download_data_set(ref: DataSetRef, destination: Path, timeout: int = 600) -> Path:
    """Stream a data set zip to ``destination`` (they are ~100 MB each)."""
    with requests.get(ref.url, headers=HEADERS, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)
    return destination


# --- identifier mapping ------------------------------------------------------


class SecurityMapper(BaseModel):
    """Resolve 13F identifiers (CUSIP, FIGI) to the symbols in the equity table.

    Built from ``equity.cusip``, US ISINs (``US`` + CUSIP + check digit) and
    the FIGI columns; when several listings share an identifier the US
    primary listing (no exchange suffix) wins.
    """

    by_cusip: Dict[str, str] = Field(default_factory=dict)
    by_figi: Dict[str, str] = Field(default_factory=dict)

    @staticmethod
    def _prefer(current: Optional[str], candidate: str) -> str:
        if current is None:
            return candidate
        if "." in current and "." not in candidate:
            return candidate
        return current

    @classmethod
    def from_frame(cls, equities: pd.DataFrame) -> "SecurityMapper":
        by_cusip: Dict[str, str] = {}
        by_figi: Dict[str, str] = {}
        for row in equities.itertuples(index=False):
            symbol = str(row.symbol)
            cusips = set()
            if isinstance(row.cusip, str) and 6 <= len(row.cusip.strip()) <= 9:  # noqa: PLR2004
                # Some providers deliver CUSIPs as numbers, losing leading zeros.
                cusips.add(row.cusip.strip().upper().zfill(9))
            if isinstance(row.isin, str) and row.isin.upper().startswith("US") and len(row.isin) == 12:  # noqa: PLR2004
                cusips.add(row.isin[2:11].upper())
            for cusip in cusips:
                by_cusip[cusip] = cls._prefer(by_cusip.get(cusip), symbol)
            for column in ("figi", "composite_figi", "shareclass_figi"):
                figi = getattr(row, column, None)
                if isinstance(figi, str) and figi.strip():
                    by_figi[figi.strip().upper()] = cls._prefer(by_figi.get(figi.strip().upper()), symbol)
        return cls(by_cusip=by_cusip, by_figi=by_figi)

    @classmethod
    def from_db(cls, db: BearishDbBase) -> "SecurityMapper":
        frame = db.read_query(
            "SELECT symbol, cusip, isin, figi, composite_figi, shareclass_figi FROM equity "
            "WHERE cusip IS NOT NULL OR isin LIKE 'US%' OR figi IS NOT NULL OR composite_figi IS NOT NULL"
        )
        return cls.from_frame(frame)

    def resolve(self, cusip: object, figi: object) -> Optional[str]:
        if isinstance(cusip, str) and cusip.upper() in self.by_cusip:
            return self.by_cusip[cusip.upper()]
        if isinstance(figi, str) and figi.upper() in self.by_figi:
            return self.by_figi[figi.upper()]
        return None


# --- reading one data set --------------------------------------------------------


def _parse_sec_date(value: object) -> Optional[datetime.date]:
    if not isinstance(value, str) or not value:
        return None
    return datetime.datetime.strptime(value, "%d-%b-%Y").date()


def read_filings(archive: zipfile.ZipFile) -> pd.DataFrame:
    """Holdings reports in the data set with manager name and amendment flags."""
    submissions = pd.read_csv(archive.open("SUBMISSION.tsv"), sep="\t", dtype=str, keep_default_na=False)
    cover = pd.read_csv(archive.open("COVERPAGE.tsv"), sep="\t", dtype=str, keep_default_na=False)
    cover = cover[["ACCESSION_NUMBER", "FILINGMANAGER_NAME", "ISAMENDMENT", "AMENDMENTTYPE"]]
    filings = submissions.merge(cover, on="ACCESSION_NUMBER", how="left")
    filings = filings[filings["SUBMISSIONTYPE"].isin(HOLDING_FORMS)].copy()
    filings["period"] = filings["PERIODOFREPORT"].map(_parse_sec_date)
    filings["filed_date"] = filings["FILING_DATE"].map(_parse_sec_date)
    filings["is_amendment"] = filings["SUBMISSIONTYPE"].eq("13F-HR/A") | filings["ISAMENDMENT"].eq("Y")
    filings["amendment_type"] = filings["AMENDMENTTYPE"].fillna("").str.upper()
    filings = filings.rename(
        columns={"ACCESSION_NUMBER": "accession_number", "CIK": "manager_cik", "FILINGMANAGER_NAME": "manager_name"}
    )
    filings["manager_name"] = filings["manager_name"].fillna("").str.strip()
    filings["manager_cik"] = filings["manager_cik"].str.strip().str.zfill(10)
    return filings[
        ["accession_number", "manager_cik", "manager_name", "period", "filed_date", "is_amendment", "amendment_type"]
    ]


def read_positions(archive: zipfile.ZipFile, accessions: Set[str]) -> pd.DataFrame:
    """Share positions for ``accessions`` aggregated per (filing, CUSIP, put/call)."""
    columns = [
        "ACCESSION_NUMBER",
        "NAMEOFISSUER",
        "TITLEOFCLASS",
        "CUSIP",
        "FIGI",
        "VALUE",
        "SSHPRNAMT",
        "SSHPRNAMTTYPE",
        "PUTCALL",
    ]
    parts: List[pd.DataFrame] = []
    with archive.open("INFOTABLE.tsv") as handle:
        for chunk in pd.read_csv(
            io.TextIOWrapper(handle, encoding="utf-8"),
            sep="\t",
            usecols=columns,
            dtype=dict.fromkeys(columns, str),
            keep_default_na=False,
            chunksize=CHUNK_ROWS,
        ):
            selected = chunk[chunk["ACCESSION_NUMBER"].isin(accessions) & chunk["SSHPRNAMTTYPE"].eq("SH")]
            if selected.empty:
                continue
            selected = selected.assign(
                VALUE=pd.to_numeric(selected["VALUE"], errors="coerce").fillna(0.0),
                SSHPRNAMT=pd.to_numeric(selected["SSHPRNAMT"], errors="coerce").fillna(0.0),
                PUTCALL=selected["PUTCALL"].str.upper().str.strip(),
                CUSIP=selected["CUSIP"].str.upper().str.strip(),
            )
            parts.append(
                selected.groupby(["ACCESSION_NUMBER", "CUSIP", "PUTCALL"], as_index=False).agg(
                    issuer_name=("NAMEOFISSUER", "first"),
                    title_of_class=("TITLEOFCLASS", "first"),
                    figi=("FIGI", "first"),
                    value=("VALUE", "sum"),
                    shares=("SSHPRNAMT", "sum"),
                )
            )
    if not parts:
        return pd.DataFrame(
            columns=[
                "accession_number",
                "cusip",
                "put_call",
                "issuer_name",
                "title_of_class",
                "figi",
                "value",
                "shares",
            ]
        )
    positions = pd.concat(parts, ignore_index=True)
    positions = positions.groupby(["ACCESSION_NUMBER", "CUSIP", "PUTCALL"], as_index=False).agg(
        issuer_name=("issuer_name", "first"),
        title_of_class=("title_of_class", "first"),
        figi=("figi", "first"),
        value=("value", "sum"),
        shares=("shares", "sum"),
    )
    return positions.rename(columns={"ACCESSION_NUMBER": "accession_number", "CUSIP": "cusip", "PUTCALL": "put_call"})


def select_reports(filings: pd.DataFrame) -> pd.DataFrame:
    """Keep one report per (manager, quarter): the latest original or restatement, plus new-holdings amendments."""
    base = filings[~filings["is_amendment"] | filings["amendment_type"].eq("RESTATEMENT")]
    base = base.sort_values("filed_date").groupby(["manager_cik", "period"], as_index=False).tail(1)
    additions = filings[filings["is_amendment"] & filings["amendment_type"].eq("NEW HOLDINGS")]
    return pd.concat([base, additions], ignore_index=True)


def read_data_set(path: Path) -> pd.DataFrame:
    """Positions of all selected reports in a data set, one row per (filing, CUSIP, put/call)."""
    with zipfile.ZipFile(path) as archive:
        filings = select_reports(read_filings(archive))
        positions = read_positions(archive, set(filings["accession_number"]))
    merged = positions.merge(filings, on="accession_number", how="inner")
    in_thousands = merged["filed_date"] < VALUE_IN_DOLLARS_FROM
    merged.loc[in_thousands, "value"] = merged.loc[in_thousands, "value"] * 1000.0
    return merged


# --- aggregation ---------------------------------------------------------------

FILING_DEADLINE = datetime.timedelta(days=45)


def quarter_ends(start: datetime.date, end: datetime.date) -> List[datetime.date]:
    ends: List[datetime.date] = []
    year, month = start.year, 3 * ((start.month - 1) // 3 + 1)
    while True:
        next_month = datetime.date(year + month // 12, month % 12 + 1, 1)
        quarter_end = next_month - datetime.timedelta(days=1)
        if quarter_end > end:
            return ends
        if quarter_end >= start:
            ends.append(quarter_end)
        year, month = next_month.year, next_month.month + 2


def covered_periods(data_sets: Iterable[DataSetRef]) -> Set[datetime.date]:
    """Quarter ends whose regular 45-day filing deadline falls inside a loaded filing window.

    Data sets also contain stragglers reporting much older quarters; summaries
    for those quarters would mix a handful of late filers with nothing else,
    so only fully covered quarters are summarised.
    """
    covered: Set[datetime.date] = set()
    for ref in data_sets:
        for quarter_end in quarter_ends(ref.start - FILING_DEADLINE - datetime.timedelta(days=10), ref.end):
            if ref.start <= quarter_end + FILING_DEADLINE <= ref.end:
                covered.add(quarter_end)
    return covered


def consolidate(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """Merge several data sets, keeping the latest report per (manager, quarter) across windows."""
    frame = pd.concat(list(frames), ignore_index=True)
    if frame.empty:
        return frame
    reports = frame[~(frame["is_amendment"] & frame["amendment_type"].eq("NEW HOLDINGS"))]
    latest = (
        reports.sort_values("filed_date").groupby(["manager_cik", "period"], as_index=False)["accession_number"].last()
    )
    keep = set(latest["accession_number"]) | set(
        frame.loc[frame["is_amendment"] & frame["amendment_type"].eq("NEW HOLDINGS"), "accession_number"]
    )
    return frame[frame["accession_number"].isin(keep)].reset_index(drop=True)


def top_managers(frame: pd.DataFrame, n: int) -> Set[str]:
    """CIKs of the ``n`` largest managers by reported long value in their latest quarter."""
    longs = frame[frame["put_call"].eq("")]
    if longs.empty or n <= 0:
        return set()
    latest_period = longs.groupby("manager_cik")["period"].transform("max")
    latest = longs[longs["period"] == latest_period]
    ranked = latest.groupby("manager_cik")["value"].sum().sort_values(ascending=False)
    return set(ranked.head(n).index)


def holdings_from_frame(frame: pd.DataFrame, mapper: SecurityMapper) -> List[Holding13F]:
    records = cast(List[Dict[str, Any]], frame.to_dict("records"))
    return [
        Holding13F(
            accession_number=row["accession_number"],
            manager_cik=row["manager_cik"],
            manager_name=row["manager_name"] or row["manager_cik"],
            period=row["period"],
            filed_date=row["filed_date"],
            cusip=row["cusip"],
            figi=row["figi"] or None,
            symbol=mapper.resolve(row["cusip"], row["figi"]),
            issuer_name=row["issuer_name"],
            title_of_class=row["title_of_class"] or None,
            shares=float(row["shares"]),
            value=float(row["value"]),
            put_call=row["put_call"] if row["put_call"] in ("PUT", "CALL") else "",
            is_amendment=bool(row["is_amendment"]),
        )
        for row in records
    ]


def summarise(frame: pd.DataFrame, mapper: SecurityMapper) -> List[Holding13FSummary]:
    """Per-security aggregates for every quarter in ``frame``, with flows where the prior quarter is present."""
    longs = frame[frame["put_call"].eq("") & (frame["shares"] > 0)]
    if longs.empty:
        return []
    per_period: Dict[datetime.date, pd.DataFrame] = {}
    for period_key, group in longs.groupby("period"):
        per_period[cast(datetime.date, period_key)] = group
    periods = sorted(per_period)
    summaries: List[Holding13FSummary] = []
    for index, period in enumerate(periods):
        current = per_period[period]
        totals = current.groupby("cusip").agg(
            issuer_name=("issuer_name", "first"),
            figi=("figi", "first"),
            holders=("manager_cik", "nunique"),
            total_shares=("shares", "sum"),
            total_value=("value", "sum"),
            latest_filed_date=("filed_date", "max"),
        )
        previous = (
            per_period[periods[index - 1]] if index > 0 and _is_previous_quarter(periods[index - 1], period) else None
        )
        flows = _flows(current, previous) if previous is not None else None
        total_rows = cast(List[Dict[str, Any]], totals.reset_index().to_dict("records"))
        for row in total_rows:
            cusip = str(row["cusip"])
            flow = flows.get(cusip) if flows is not None else None
            summaries.append(
                Holding13FSummary(
                    cusip=cusip,
                    period=period,
                    symbol=mapper.resolve(cusip, row["figi"]),
                    issuer_name=row["issuer_name"],
                    holders=int(row["holders"]),
                    total_shares=float(row["total_shares"]),
                    total_value=float(row["total_value"]),
                    prev_holders=int(flow["prev_holders"]) if flow else None,
                    new_holders=int(flow["new_holders"]) if flow else None,
                    closed_holders=int(flow["closed_holders"]) if flow else None,
                    shares_change=flow["shares_change"] if flow else None,
                    value_change=flow["value_change"] if flow else None,
                    latest_filed_date=row["latest_filed_date"],
                )
            )
    return summaries


def _is_previous_quarter(earlier: datetime.date, later: datetime.date) -> bool:
    months = (later.year - earlier.year) * 12 + later.month - earlier.month
    return 2 <= months <= 4  # noqa: PLR2004


def _flows(current: pd.DataFrame, previous: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    now = current.groupby(["cusip", "manager_cik"])[["shares", "value"]].sum()
    then = previous.groupby(["cusip", "manager_cik"])[["shares", "value"]].sum()
    joined = now.join(then, how="outer", lsuffix="_now", rsuffix="_then").reset_index()
    joined["is_new"] = joined["shares_then"].isna()
    joined["is_closed"] = joined["shares_now"].isna()
    joined["had_then"] = ~joined["is_new"]
    joined = joined.fillna(0.0)
    per_cusip = joined.groupby("cusip").agg(
        prev_holders=("had_then", "sum"),
        new_holders=("is_new", "sum"),
        closed_holders=("is_closed", "sum"),
        shares_now=("shares_now", "sum"),
        shares_then=("shares_then", "sum"),
        value_now=("value_now", "sum"),
        value_then=("value_then", "sum"),
    )
    flow_rows = cast(List[Dict[str, Any]], per_cusip.reset_index().to_dict("records"))
    return {
        str(row["cusip"]): {
            "prev_holders": float(row["prev_holders"]),
            "new_holders": float(row["new_holders"]),
            "closed_holders": float(row["closed_holders"]),
            "shares_change": float(row["shares_now"] - row["shares_then"]),
            "value_change": float(row["value_now"] - row["value_then"]),
        }
        for row in flow_rows
    }


# --- orchestration ---------------------------------------------------------------


class HoldingsReport(BaseModel):
    data_sets: List[str] = Field(default_factory=list)
    periods: List[datetime.date] = Field(default_factory=list)
    managers_stored: int = 0
    holdings_written: int = 0
    summaries_written: int = 0
    symbols_resolved: int = 0


def load_holdings(  # noqa: PLR0913
    db: BearishDbBase,
    data_sets: List[DataSetRef],
    managers: Optional[List[str]] = None,
    top_n: int = 300,
    mapper: Optional[SecurityMapper] = None,
    download_dir: Optional[Path] = None,
) -> HoldingsReport:
    """Download ``data_sets``, store per-manager holdings for the selected managers and summaries for all securities."""
    mapper = mapper or SecurityMapper.from_db(db)
    report = HoldingsReport(data_sets=[ref.name for ref in data_sets])
    with tempfile.TemporaryDirectory() as tmp:
        frames = []
        for ref in data_sets:
            path = (download_dir or Path(tmp)) / ref.name
            if not path.exists():
                logger.info(f"Downloading 13F data set {ref.name}")
                download_data_set(ref, path)
            frames.append(read_data_set(path))
            logger.info(f"Read {len(frames[-1])} positions from {ref.name}")
        frame = consolidate(frames)
    if frame.empty:
        return report
    frame["manager_cik"] = frame["manager_cik"].str.zfill(10)
    selected = {cik.zfill(10) for cik in managers or []} | top_managers(frame, top_n)
    holdings = holdings_from_frame(frame[frame["manager_cik"].isin(selected)], mapper)
    db.write_holdings13f(holdings)
    covered = covered_periods(data_sets)
    summaries = summarise(frame[frame["period"].isin(covered)], mapper)
    db.write_holdings13f_summary(summaries)
    report.periods = sorted({h.period for h in holdings} | {s.period for s in summaries})
    report.managers_stored = len(selected)
    report.holdings_written = len(holdings)
    report.summaries_written = len(summaries)
    report.symbols_resolved = sum(1 for s in summaries if s.symbol)
    return report


def pick_data_sets(
    available: List[DataSetRef], windows: int, names: Optional[List[str]] = None
) -> Tuple[List[DataSetRef], List[str]]:
    """The newest ``windows`` data sets, or the named ones; returns (refs, unknown names)."""
    if names:
        by_name = {ref.name: ref for ref in available}
        wanted = [by_name[name] for name in names if name in by_name]
        return wanted, [name for name in names if name not in by_name]
    return available[:windows], []
