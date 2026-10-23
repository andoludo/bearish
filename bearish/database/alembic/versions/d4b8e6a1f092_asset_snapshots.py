"""asset snapshots

Dated copies of the fast-moving equity fields (market cap, short interest,
valuation ratios) and ETF fields (AUM, NAV, expense ratio, holdings), one
row per (symbol, source, as_of), written on every detailed asset fetch.

Revision ID: d4b8e6a1f092
Revises: c3a9f1e7d250
Create Date: 2026-10-23 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd4b8e6a1f092'
down_revision: Union[str, None] = 'c3a9f1e7d250'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EQUITY_COLUMNS = (
    'market_capitalization', 'shares_outstanding', 'float_shares', 'short_shares', 'short_ratio',
    'price_to_book', 'trailing_price_to_earnings', 'forward_price_to_earnings', 'trailing_price_to_sales',
    'trailing_peg_ratio', 'dividend_yield', 'trailing_earnings_per_share', 'forward_earnings_per_share',
    'return_on_equity', 'return_on_assets', 'gross_margins', 'operating_margins', 'revenue_growth',
    'earning_growth',
)
ETF_COLUMNS = (
    'total_net_assets', 'nav_price', 'annual_report_expense_ratio', 'annual_holdings_turnover',
    'price_to_earnings', 'price_to_book', 'price_to_sales', 'price_to_cashflow', 'yield_', 'ytd_return',
    'three_year_average_return',
)


def upgrade() -> None:
    op.create_table('equitysnapshot',
    sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('as_of', sa.Date(), nullable=False),
    *[sa.Column(column, sa.Float(), nullable=True) for column in EQUITY_COLUMNS],
    sa.PrimaryKeyConstraint('symbol', 'source', 'as_of')
    )
    with op.batch_alter_table('equitysnapshot', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_equitysnapshot_as_of'), ['as_of'], unique=False)
        batch_op.create_index(batch_op.f('ix_equitysnapshot_symbol'), ['symbol'], unique=False)

    op.create_table('etfsnapshot',
    sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('as_of', sa.Date(), nullable=False),
    *[sa.Column(column, sa.Float(), nullable=True) for column in ETF_COLUMNS],
    sa.Column('holding_percent', sa.JSON(), nullable=True),
    sa.Column('sector_weightings', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('symbol', 'source', 'as_of')
    )
    with op.batch_alter_table('etfsnapshot', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_etfsnapshot_as_of'), ['as_of'], unique=False)
        batch_op.create_index(batch_op.f('ix_etfsnapshot_symbol'), ['symbol'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('etfsnapshot', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_etfsnapshot_symbol'))
        batch_op.drop_index(batch_op.f('ix_etfsnapshot_as_of'))
    op.drop_table('etfsnapshot')
    with op.batch_alter_table('equitysnapshot', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_equitysnapshot_symbol'))
        batch_op.drop_index(batch_op.f('ix_equitysnapshot_as_of'))
    op.drop_table('equitysnapshot')
