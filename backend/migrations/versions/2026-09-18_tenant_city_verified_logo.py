"""tenants.city/is_verified/logo — город магазина, проверенный магазин
(значок доверия, меняет только админ), логотип магазина (M-B1 п.2, п.3, п.5)

Revision ID: 19e6010ad1f2
Revises: bb829e81f02a
Create Date: 2026-09-18 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '19e6010ad1f2'
down_revision: Union[str, Sequence[str], None] = 'bb829e81f02a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('city', sa.String(100), nullable=True))
    op.add_column(
        'tenants',
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'tenants', sa.Column('logo', sa.String(500), nullable=False, server_default='')
    )


def downgrade() -> None:
    op.drop_column('tenants', 'logo')
    op.drop_column('tenants', 'is_verified')
    op.drop_column('tenants', 'city')
