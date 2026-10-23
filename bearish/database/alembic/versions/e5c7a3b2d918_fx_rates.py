"""fx rates

``pricecurrency`` holds the daily Yahoo quotes of USD<CCY>=X pairs and the
``fxrate`` view reads them as (date, base, quote, rate).

Revision ID: e5c7a3b2d918
Revises: d4b8e6a1f092
Create Date: 2026-10-23 21:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e5c7a3b2d918'
down_revision: Union[str, None] = 'd4b8e6a1f092'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FX_RATE_VIEW = """
CREATE VIEW IF NOT EXISTS fxrate AS
SELECT date, symbol, source, SUBSTR(symbol, 1, 3) AS base, SUBSTR(symbol, 4, 3) AS quote, close AS rate
FROM pricecurrency
WHERE symbol LIKE '______=X'
"""


def upgrade() -> None:
    op.create_table('pricecurrency',
    sa.Column('open', sa.Float(), nullable=True),
    sa.Column('high', sa.Float(), nullable=True),
    sa.Column('low', sa.Float(), nullable=True),
    sa.Column('close', sa.Float(), nullable=False),
    sa.Column('volume', sa.Float(), nullable=True),
    sa.Column('dividends', sa.Float(), nullable=True),
    sa.Column('stock_splits', sa.Float(), nullable=True),
    sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('exchange', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('date', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.Date(), nullable=False),
    sa.PrimaryKeyConstraint('symbol', 'source', 'date')
    )
    with op.batch_alter_table('pricecurrency', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pricecurrency_date'), ['date'], unique=False)
        batch_op.create_index(batch_op.f('ix_pricecurrency_source'), ['source'], unique=False)
        batch_op.create_index(batch_op.f('ix_pricecurrency_symbol'), ['symbol'], unique=False)
    op.execute(FX_RATE_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS fxrate")
    with op.batch_alter_table('pricecurrency', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pricecurrency_symbol'))
        batch_op.drop_index(batch_op.f('ix_pricecurrency_source'))
        batch_op.drop_index(batch_op.f('ix_pricecurrency_date'))

    op.drop_table('pricecurrency')
