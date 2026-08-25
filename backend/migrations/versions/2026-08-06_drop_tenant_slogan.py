"""drop tenant slogan

Revision ID: c4a8e2f1b6d3
Revises: b3f7a1c9d2e4
Create Date: 2026-08-06 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a8e2f1b6d3'
down_revision: Union[str, Sequence[str], None] = 'b3f7a1c9d2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('tenants', 'slogan')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('tenants', sa.Column('slogan', sa.String(length=200), nullable=True))
