"""coverage

Per (symbol, table, source) census: first / last date and row count.

Revision ID: a9d3e5f7c164
Revises: f1a6c4d8e273
Create Date: 2026-10-23 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a9d3e5f7c164'
down_revision: Union[str, None] = 'f1a6c4d8e273'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('coverage',
    sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('table_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('first_date', sa.Date(), nullable=False),
    sa.Column('last_date', sa.Date(), nullable=False),
    sa.Column('rows', sa.Integer(), nullable=False),
    sa.Column('as_of', sa.Date(), nullable=False),
    sa.PrimaryKeyConstraint('symbol', 'table_name', 'source')
    )
    with op.batch_alter_table('coverage', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_coverage_symbol'), ['symbol'], unique=False)
        batch_op.create_index(batch_op.f('ix_coverage_table_name'), ['table_name'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('coverage', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_coverage_table_name'))
        batch_op.drop_index(batch_op.f('ix_coverage_symbol'))

    op.drop_table('coverage')
