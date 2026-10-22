import datetime
import re
import zipfile
from pathlib import Path

import pandas as pd
import pytest
import requests_mock

from bearish.database.crud import BearishDb
from bearish.sources.sec_13f import (
    DATA_SETS_URL,
    DataSetRef,
    SecurityMapper,
    consolidate,
    covered_periods,
    list_data_sets,
    load_holdings,
    parse_data_set_index,
    pick_data_sets,
    quarter_ends,
    read_data_set,
    read_filings,
    summarise,
    top_managers,
)

DATA_DIR = Path(__file__).parents[1] / "data" / "sources" / "sec_13f"
LATEST = "01jun2026-31aug2026_form13f.zip"
PREVIOUS = "01mar2026-31may2026_form13f.zip"
BERKSHIRE = "0001067983"
VANGUARD = "0000102909"
AAPL_CUSIP = "037833100"


@pytest.fixture
def mapper() -> SecurityMapper:
    # CUSIPs as they come out of the equity table: sometimes numeric (leading zero lost).
    frame = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "cusip": "37833100",
                "isin": "US0378331005",
                "figi": None,
                "composite_figi": "BBG000B9XRY4",
                "shareclass_figi": None,
            },
            {
                "symbol": "AAPL.MX",
                "cusip": None,
                "isin": "US0378331005",
                "figi": None,
                "composite_figi": None,
                "shareclass_figi": None,
            },
            {
                "symbol": "KO",
                "cusip": None,
                "isin": "US1912161007",
                "figi": None,
                "composite_figi": None,
                "shareclass_figi": None,
            },
            {
                "symbol": "BAC",
                "cusip": None,
                "isin": None,
                "figi": "BBG000BCTN44",
                "composite_figi": "BBG000BCTLF6",
                "shareclass_figi": None,
            },
            {
                "symbol": "SAP.DE",
                "cusip": None,
                "isin": "DE0007164600",
                "figi": None,
                "composite_figi": None,
                "shareclass_figi": None,
            },
        ]
    )
    return SecurityMapper.from_frame(frame)


@pytest.fixture
def sec_api() -> requests_mock.Mocker:
    with requests_mock.Mocker() as req:
        req.get(DATA_SETS_URL, text=(DATA_DIR / "index.html").read_text())
        req.get(
            re.compile(r"https://www\.sec\.gov/files/.*_form13f\.zip"),
            content=lambda request, context: (DATA_DIR / request.url.rsplit("/", 1)[-1]).read_bytes(),
        )
        yield req


def test_parse_data_set_index_handles_windows_and_quarters() -> None:
    refs = parse_data_set_index((DATA_DIR / "index.html").read_text())
    assert refs[0].name == LATEST
    assert refs[0].start == datetime.date(2026, 6, 1)
    assert refs[0].end == datetime.date(2026, 8, 31)
    assert refs[0].url.startswith("https://www.sec.gov/files/")
    quarterly = next(ref for ref in refs if ref.name == "2013q4_form13f.zip")
    assert (quarterly.start, quarterly.end) == (datetime.date(2013, 10, 1), datetime.date(2013, 12, 31))
    assert [ref.end for ref in refs] == sorted((ref.end for ref in refs), reverse=True)


def test_security_mapper_prefers_primary_listing_and_pads_cusips(mapper: SecurityMapper) -> None:
    assert mapper.resolve(AAPL_CUSIP, None) == "AAPL"  # padded numeric CUSIP and US ISIN agree
    assert mapper.resolve("191216100", None) == "KO"  # from the ISIN only
    assert mapper.resolve("060505104", "BBG000BCTN44") == "BAC"  # FIGI fallback
    assert mapper.resolve("XXXXXXXXX", None) is None
    assert "716460" not in "".join(mapper.by_cusip)  # non-US ISINs are not CUSIPs


def test_read_data_set_selects_reports_and_aggregates_positions() -> None:
    with zipfile.ZipFile(DATA_DIR / LATEST) as archive:
        filings = read_filings(archive)
    assert BERKSHIRE in set(filings["manager_cik"])
    # Vanguard Group files a 13F-NT (notice: holdings reported elsewhere) -> not a holdings report
    assert VANGUARD not in set(filings["manager_cik"])

    frame = read_data_set(DATA_DIR / LATEST)
    assert {
        "accession_number",
        "manager_cik",
        "manager_name",
        "period",
        "filed_date",
        "cusip",
        "shares",
        "value",
        "put_call",
    } <= set(frame.columns)
    berkshire = frame[frame["manager_cik"] == BERKSHIRE]
    assert len(berkshire) > 20
    apple = berkshire[berkshire["cusip"] == AAPL_CUSIP].iloc[0]
    assert apple["period"] == datetime.date(2026, 6, 30)
    assert apple["shares"] > 1e8
    assert apple["value"] > 1e10  # dollars, not thousands
    assert apple["put_call"] == ""
    # one row per (filing, cusip, put/call): several lines for the same CUSIP are summed
    assert not frame.duplicated(["accession_number", "cusip", "put_call"]).any()


def test_consolidate_keeps_latest_report_per_manager_quarter() -> None:
    latest = read_data_set(DATA_DIR / LATEST)
    previous = read_data_set(DATA_DIR / PREVIOUS)
    frame = consolidate([previous, latest])
    per_manager_quarter = frame.groupby(["manager_cik", "period"])["accession_number"].nunique()
    # new-holdings amendments may add a second accession; restatements/originals never do
    assert (per_manager_quarter <= 2).all()
    assert {datetime.date(2026, 3, 31), datetime.date(2026, 6, 30)} <= set(frame["period"])
    assert BERKSHIRE in top_managers(frame, 2)


def test_summarise_computes_flows_between_consecutive_quarters(mapper: SecurityMapper) -> None:
    frame = consolidate([read_data_set(DATA_DIR / PREVIOUS), read_data_set(DATA_DIR / LATEST)])
    summaries = {(s.cusip, s.period): s for s in summarise(frame, mapper)}
    q1 = summaries[(AAPL_CUSIP, datetime.date(2026, 3, 31))]
    q2 = summaries[(AAPL_CUSIP, datetime.date(2026, 6, 30))]
    assert q1.symbol == q2.symbol == "AAPL"
    assert q1.new_holders is None  # no earlier quarter loaded
    assert q2.prev_holders == q1.holders
    assert q2.new_holders is not None and q2.closed_holders is not None
    assert q2.holders == q2.prev_holders + q2.new_holders - q2.closed_holders
    assert q2.shares_change == pytest.approx(q2.total_shares - q1.total_shares)
    assert q2.latest_filed_date >= datetime.date(2026, 7, 1)


def test_load_holdings_end_to_end(tmp_path: Path, mapper: SecurityMapper, sec_api: requests_mock.Mocker) -> None:
    db = BearishDb(database_path=tmp_path / "bear.db")
    refs, unknown = pick_data_sets(list_data_sets(), windows=2)
    assert [ref.name for ref in refs] == [LATEST, PREVIOUS]
    assert unknown == []

    report = load_holdings(db, refs, managers=[BERKSHIRE], top_n=2, mapper=mapper)

    assert report.data_sets == [LATEST, PREVIOUS]
    assert report.periods[-2:] == [datetime.date(2026, 3, 31), datetime.date(2026, 6, 30)]
    # straggler quarters keep their raw per-manager rows but get no summary
    assert {s.period for s in db.read_holdings13f_summary()} == {datetime.date(2026, 3, 31), datetime.date(2026, 6, 30)}
    assert report.managers_stored == 2  # Berkshire (explicit, also among the top 2) + the other largest filer
    assert VANGUARD not in {h.manager_cik for h in db.read_holdings13f()}  # 13F-NT filers have no positions
    berkshire = db.read_holdings13f(manager_cik=BERKSHIRE)
    assert {h.period for h in berkshire} == set(report.periods)
    apple = [h for h in berkshire if h.symbol == "AAPL"]
    assert len(apple) == 2
    assert all(h.manager_name == "Berkshire Hathaway Inc" for h in apple)
    assert db.read_holdings13f(symbol="AAPL")
    summary = db.read_holdings13f_summary(symbol="AAPL")
    assert len(summary) == 2
    assert report.symbols_resolved >= 4

    # Re-running is idempotent (upserts on the primary keys).
    load_holdings(db, refs, managers=[BERKSHIRE], top_n=2, mapper=mapper)
    assert len(db.read_holdings13f(manager_cik=BERKSHIRE)) == len(berkshire)


def test_covered_periods_follow_the_45_day_deadline() -> None:
    refs = parse_data_set_index((DATA_DIR / "index.html").read_text())
    june_window = next(ref for ref in refs if ref.name == LATEST)  # filings 1 Jun - 31 Aug 2026
    assert covered_periods([june_window]) == {datetime.date(2026, 6, 30)}
    q4_2013 = next(ref for ref in refs if ref.name == "2013q4_form13f.zip")  # filings 1 Oct - 31 Dec 2013
    assert covered_periods([q4_2013]) == {datetime.date(2013, 9, 30)}
    assert quarter_ends(datetime.date(2026, 1, 15), datetime.date(2026, 7, 1)) == [
        datetime.date(2026, 3, 31),
        datetime.date(2026, 6, 30),
    ]


def _tiny_data_set(path: Path) -> Path:
    """Two reports for the same old quarter: one filed in 2022 (thousands), one filed in 2026 (dollars)."""
    submission = (
        "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT\n"
        "0000000001-22-000001\t14-NOV-2022\t13F-HR\t1\t30-SEP-2022\n"
        "0000000002-26-000001\t05-JUN-2026\t13F-HR\t2\t30-SEP-2022\n"
    )
    cover = (
        "ACCESSION_NUMBER\tFILINGMANAGER_NAME\tISAMENDMENT\tAMENDMENTTYPE\n"
        "0000000001-22-000001\tOld Timer LP\tN\t\n"
        "0000000002-26-000001\tLate Filer LLC\tN\t\n"
    )
    info = (
        "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP\tFIGI\tVALUE\tSSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL\t"
        "INVESTMENTDISCRETION\tOTHERMANAGER\tVOTING_AUTH_SOLE\tVOTING_AUTH_SHARED\tVOTING_AUTH_NONE\n"
        "0000000001-22-000001\t1\tAPPLE INC\tCOM\t037833100\t\t1000\t5000\tSH\t\tSOLE\t\t5000\t0\t0\n"
        "0000000002-26-000001\t2\tAPPLE INC\tCOM\t037833100\t\t1000000\t5000\tSH\t\tSOLE\t\t5000\t0\t0\n"
        "0000000002-26-000001\t3\tUS TREASURY\tNOTE\t912828XX1\t\t999\t999\tPRN\t\tSOLE\t\t0\t0\t0\n"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("SUBMISSION.tsv", submission)
        archive.writestr("COVERPAGE.tsv", cover)
        archive.writestr("INFOTABLE.tsv", info)
    return path


def test_values_rescaled_by_filing_date_not_period(tmp_path: Path) -> None:
    frame = read_data_set(_tiny_data_set(tmp_path / "tiny_form13f.zip"))
    by_manager = frame.set_index("manager_cik")
    assert by_manager.loc["0000000001", "value"] == 1_000_000.0  # filed 2022: thousands -> dollars
    assert by_manager.loc["0000000002", "value"] == 1_000_000.0  # filed 2026: already dollars
    assert "912828XX1" not in set(frame["cusip"])  # principal-amount rows dropped


def test_pick_data_sets_by_name() -> None:
    available = [DataSetRef(name="a", url="u", start=datetime.date(2026, 1, 1), end=datetime.date(2026, 2, 1))]
    assert pick_data_sets(available, windows=1, names=["a", "zzz"]) == (available, ["zzz"])


@pytest.mark.network
def test_list_data_sets_live() -> None:
    refs = list_data_sets()
    assert len(refs) > 40
    assert refs[0].end >= datetime.date(2026, 6, 1)
