"""Per-symbol data coverage: which tables hold rows for a symbol, over which
dates, and how many.

Downstream analysis needs to know *before* judging a stock whether the
database can support the judgement (enough fiscal years, fresh prices,
analyst rows, 13F quarters, ...). Scanning every table per request is slow,
so ``bearish coverage`` (and the end of ``run`` / ``update``) summarises each
dated table into ``coverage``: one row per ``(symbol, table, source)`` with
the first and last date and the row count. Grading the coverage is
downstream work; this is the raw census.
"""

import datetime
import logging
from typing import List, Optional, Tuple

from pydantic import BaseModel, ConfigDict

from bearish.interface.interface import BearishDbBase
from bearish.models.coverage import Coverage

logger = logging.getLogger(__name__)


class CoveredTable(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    date_column: str
    source_column: Optional[str] = "source"


COVERED_TABLES: Tuple[CoveredTable, ...] = (
    CoveredTable(name="price", date_column="date"),
    CoveredTable(name="priceetf", date_column="date"),
    CoveredTable(name="priceindex", date_column="date"),
    CoveredTable(name="financialmetrics", date_column="date"),
    CoveredTable(name="balancesheet", date_column="date"),
    CoveredTable(name="cashflow", date_column="date"),
    CoveredTable(name="quarterlyfinancialmetrics", date_column="date"),
    CoveredTable(name="quarterlybalancesheet", date_column="date"),
    CoveredTable(name="quarterlycashflow", date_column="date"),
    CoveredTable(name="earningsdate", date_column="date"),
    CoveredTable(name="pricetarget", date_column="date"),
    CoveredTable(name="analystrecommendation", date_column="date"),
    CoveredTable(name="filing", date_column="filed_date", source_column=None),
    CoveredTable(name="insidertransaction", date_column="transaction_date"),
    CoveredTable(name="holding13fsummary", date_column="period"),
    CoveredTable(name="ownership13dg", date_column="filed_date"),
    CoveredTable(name="equitysnapshot", date_column="as_of"),
    CoveredTable(name="etfsnapshot", date_column="as_of"),
    CoveredTable(name="indexmember", date_column="as_of"),
)


def _census_query(table: CoveredTable, symbols: Optional[List[str]]) -> str:
    source = f'"{table.source_column}"' if table.source_column else "''"
    where = ""
    if symbols:
        quoted = ", ".join("'" + symbol.replace("'", "''") + "'" for symbol in symbols)
        where = f" WHERE symbol IN ({quoted})"
    return (
        f'SELECT symbol, {source} AS source, MIN(date("{table.date_column}")) AS first_date, '
        f'MAX(date("{table.date_column}")) AS last_date, COUNT(*) AS rows '
        f'FROM "{table.name}"{where} GROUP BY symbol, {source}'
    )


def compute_coverage(
    db: BearishDbBase, symbols: Optional[List[str]] = None, as_of: Optional[datetime.date] = None
) -> List[Coverage]:
    """The census of every covered table (restricted to ``symbols`` when given)."""
    as_of = as_of or datetime.date.today()
    rows: List[Coverage] = []
    for table in COVERED_TABLES:
        try:
            frame = db.read_query(_census_query(table, symbols))
        except Exception as e:  # a table missing from an old database must not abort the census
            logger.warning(f"Coverage of {table.name} skipped: {e}")
            continue
        for record in frame.to_dict(orient="records"):
            if record["symbol"] is None or record["first_date"] is None:
                continue
            rows.append(
                Coverage(
                    symbol=str(record["symbol"]),
                    table_name=table.name,
                    source=str(record["source"] or ""),
                    first_date=datetime.date.fromisoformat(str(record["first_date"])[:10]),
                    last_date=datetime.date.fromisoformat(str(record["last_date"])[:10]),
                    rows=int(record["rows"]),
                    as_of=as_of,
                )
            )
    return rows


def write_coverage(db: BearishDbBase, symbols: Optional[List[str]] = None) -> int:
    """Refresh the ``coverage`` table; returns the number of rows written."""
    rows = compute_coverage(db, symbols=symbols)
    db.write_coverage(rows, replace=symbols is None)
    logger.info(f"Coverage written: {len(rows)} rows over {len({r.table_name for r in rows})} tables")
    return len(rows)
