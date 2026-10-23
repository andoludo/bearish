"""filing items

8-K filings are now stored in ``filing`` with their EDGAR item codes.

Revision ID: b7e4d2c90a15
Revises: 8c1f2a9d4b31
Create Date: 2026-10-23 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b7e4d2c90a15'
down_revision: Union[str, None] = '8c1f2a9d4b31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('filing', schema=None) as batch_op:
        batch_op.add_column(sa.Column('items', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.create_index(batch_op.f('ix_filing_form_type'), ['form_type'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('filing', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_filing_form_type'))
        batch_op.drop_column('items')
