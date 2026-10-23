"""index members

Dated index constituent snapshots (Wikipedia constituent tables).

Revision ID: f1a6c4d8e273
Revises: e5c7a3b2d918
Create Date: 2026-10-23 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f1a6c4d8e273'
down_revision: Union[str, None] = 'e5c7a3b2d918'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('indexmember',
    sa.Column('index_symbol', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('symbol', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('as_of', sa.Date(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('weight', sa.Float(), nullable=True),
    sa.Column('source', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.PrimaryKeyConstraint('index_symbol', 'symbol', 'as_of')
    )
    with op.batch_alter_table('indexmember', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_indexmember_as_of'), ['as_of'], unique=False)
        batch_op.create_index(batch_op.f('ix_indexmember_index_symbol'), ['index_symbol'], unique=False)
        batch_op.create_index(batch_op.f('ix_indexmember_symbol'), ['symbol'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('indexmember', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_indexmember_symbol'))
        batch_op.drop_index(batch_op.f('ix_indexmember_index_symbol'))
        batch_op.drop_index(batch_op.f('ix_indexmember_as_of'))

    op.drop_table('indexmember')
