"""add tenant slogan

Revision ID: b3f7a1c9d2e4
Revises: 8f1c2e4a7b3d
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f7a1c9d2e4'
down_revision: Union[str, Sequence[str], None] = '8f1c2e4a7b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tenants', sa.Column('slogan', sa.String(length=200), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tenants', 'slogan')
