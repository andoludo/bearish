"""sector aliases

``sectoralias`` maps every known spelling of a sector / industry (Yahoo,
FinanceDatabase, ETF sector-weight keys) to the canonical GICS name, and the
``equitysector`` view exposes the resolved names next to ``equity.sector`` /
``equity.industry``.

Revision ID: 8c1f2a9d4b31
Revises: 9c21f96faefe
Create Date: 2026-10-23 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '8c1f2a9d4b31'
down_revision: Union[str, None] = '9c21f96faefe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EQUITY_SECTOR_VIEW = """
CREATE VIEW IF NOT EXISTS equitysector AS
SELECT e.symbol, e.source, e.sector, e.industry, s.name AS gics_sector, i.name AS gics_industry
FROM equity AS e
LEFT JOIN sectoralias AS s ON s.level = 'sector' AND s.alias = LOWER(TRIM(e.sector))
LEFT JOIN sectoralias AS i ON i.level = 'industry' AND i.alias = LOWER(TRIM(e.industry))
"""


def upgrade() -> None:
    op.create_table('sectoralias',
    sa.Column('alias', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('level', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.PrimaryKeyConstraint('alias', 'level')
    )
    with op.batch_alter_table('sectoralias', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sectoralias_name'), ['name'], unique=False)
    op.execute(EQUITY_SECTOR_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS equitysector")
    with op.batch_alter_table('sectoralias', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sectoralias_name'))

    op.drop_table('sectoralias')
