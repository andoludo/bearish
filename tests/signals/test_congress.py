import datetime
import re
from pathlib import Path

import pytest
import requests_mock

from bearish.signals.sources.congress import (
    INDEX_URL,
    PtrFiling,
    fetch_house_trades,
    parse_index,
    parse_ptr_text,
    pdf_text,
)

DATA_DIR = Path(__file__).parents[1] / "data" / "signals" / "congress"
FILING = PtrFiling(
    doc_id="20034201", member="Mark Alford", state_district="MO04", filed_date=datetime.date(2026, 3, 31), year=2026
)


def test_parse_index_keeps_only_ptrs() -> None:
    import zipfile

    with zipfile.ZipFile(DATA_DIR / "2026FD.zip") as archive:
        filings = parse_index(archive.read("2026FD.xml").decode("utf-8"))
    assert {f.doc_id for f in filings} == {"20034201", "20035691", "20033751"}  # the 'W' filing is dropped
    alford = next(f for f in filings if f.doc_id == "20034201")
    assert alford.member == "Mark Alford"
    assert alford.state_district == "MO04"
    assert alford.filed_date == datetime.date(2026, 3, 31)


def test_parse_ptr_with_wrapped_assets_and_tickers() -> None:
    trades = parse_ptr_text(pdf_text((DATA_DIR / "ptr_20034201.pdf").read_bytes()), FILING)
    by_symbol = {t.symbol: t for t in trades if t.symbol}
    assert {"AMZN", "AAPL", "T", "BRK.B", "DIA", "PYPL"} <= set(by_symbol)
    amzn = by_symbol["AMZN"]
    assert amzn.asset_description == "Amazon.com, Inc. - Common Stock (AMZN) [ST]"
    assert amzn.transaction_type == "S (partial)"
    assert amzn.transaction_date == datetime.date(2026, 3, 16)
    assert (amzn.amount_min, amzn.amount_max) == (1001.0, 15000.0)
    assert by_symbol["DIA"].asset_description.endswith("NYSEARCA: DIA [OT]")
    assert [t.line_no for t in trades] == list(range(1, len(trades) + 1))
    assert not any("shares sold" in t.asset_description for t in trades)


def test_parse_ptr_amount_split_over_two_lines() -> None:
    filing = FILING.model_copy(update={"doc_id": "20035691"})
    (trade,) = parse_ptr_text(pdf_text((DATA_DIR / "ptr_20035691.pdf").read_bytes()), filing)
    assert trade.asset_description == "Treasury Bill (6-Week, Matures 12/3/2026) [GS]"
    assert trade.symbol is None
    assert trade.transaction_type == "P"
    assert (trade.amount_min, trade.amount_max) == (15001.0, 50000.0)


def test_owner_codes_and_open_ended_amounts() -> None:
    text = "SP NVIDIA Corporation - Common Stock (NVDA)\n[ST]\nP 09/01/2026 09/02/2026 Over $50,000,000\nF S: New\n"
    (trade,) = parse_ptr_text(text, FILING)
    assert trade.owner == "SP"
    assert trade.symbol == "NVDA"
    assert (trade.amount_min, trade.amount_max) == (50_000_000.0, None)


def test_fetch_house_trades_counts_scanned_filings() -> None:
    with requests_mock.Mocker() as req:
        req.get(INDEX_URL.format(year=2026), content=(DATA_DIR / "2026FD.zip").read_bytes())
        req.get(re.compile(r".*/ptr-pdfs/2026/20034201\.pdf"), content=(DATA_DIR / "ptr_20034201.pdf").read_bytes())
        req.get(re.compile(r".*/ptr-pdfs/2026/20035691\.pdf"), content=(DATA_DIR / "ptr_20035691.pdf").read_bytes())
        req.get(re.compile(r".*/ptr-pdfs/2026/20033751\.pdf"), content=(DATA_DIR / "scanned_blank.pdf").read_bytes())
        result = fetch_house_trades(2026, pause=0)
        since = fetch_house_trades(2026, since=datetime.date(2026, 10, 1), pause=0)
    assert (result.filings, result.parsed, result.scanned, result.failed) == (3, 2, 1, 0)
    assert len(result.trades) == 10
    assert since.filings == 1
    assert {t.doc_id for t in since.trades} == {"20035691"}


@pytest.mark.network
def test_fetch_house_trades_live() -> None:
    result = fetch_house_trades(datetime.date.today().year, max_filings=3, pause=0.5)
    assert result.filings == 3
    assert result.parsed + result.scanned + result.failed >= 1
