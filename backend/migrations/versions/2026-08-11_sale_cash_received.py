"""add sales.cash_received (snapshot of cash given by client at checkout)

Revision ID: d3e7a1f9b4c2
Revises: c8a2d6e5f1b9
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e7a1f9b4c2'
down_revision: Union[str, Sequence[str], None] = 'c8a2d6e5f1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('sales', sa.Column('cash_received', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sales', 'cash_received')
