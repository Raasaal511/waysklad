"""tenants.is_suspended — блокировка магазина платформой (admin-панель)

Revision ID: 36dd267585ac
Revises: 1530d46dd2f5
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36dd267585ac'
down_revision: Union[str, Sequence[str], None] = '1530d46dd2f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column('is_suspended', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('tenants', 'is_suspended')
