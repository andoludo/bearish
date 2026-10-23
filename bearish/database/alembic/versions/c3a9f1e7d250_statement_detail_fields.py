"""statement detail fields

Interest expense, R&D, SG&A and diluted average shares on the income
statement tables; share-based compensation on the cash flow tables. They
feed interest coverage, the Mohanram G-score and dilution checks downstream.

Revision ID: c3a9f1e7d250
Revises: b7e4d2c90a15
Create Date: 2026-10-23 20:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a9f1e7d250'
down_revision: Union[str, None] = 'b7e4d2c90a15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

METRICS_TABLES = ('financialmetrics', 'quarterlyfinancialmetrics')
METRICS_COLUMNS = (
    'interest_expense',
    'research_and_development',
    'selling_general_and_administrative',
    'diluted_average_shares',
)
CASH_FLOW_TABLES = ('cashflow', 'quarterlycashflow')
CASH_FLOW_COLUMNS = ('stock_based_compensation',)


def upgrade() -> None:
    for table, columns in ((t, METRICS_COLUMNS) for t in METRICS_TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in columns:
                batch_op.add_column(sa.Column(column, sa.Float(), nullable=True))
    for table in CASH_FLOW_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in CASH_FLOW_COLUMNS:
                batch_op.add_column(sa.Column(column, sa.Float(), nullable=True))


def downgrade() -> None:
    for table in CASH_FLOW_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in CASH_FLOW_COLUMNS:
                batch_op.drop_column(column)
    for table in METRICS_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in METRICS_COLUMNS:
                batch_op.drop_column(column)
