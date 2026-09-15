"""Витрина (шаг 1): products.show_on_storefront + tenants.storefront_enabled

Revision ID: a1c6e0f3b7d2
Revises: f4d8b2a6c9e3
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c6e0f3b7d2'
down_revision: Union[str, Sequence[str], None] = 'f4d8b2a6c9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('show_on_storefront', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'tenants',
        sa.Column('storefront_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('tenants', 'storefront_enabled')
    op.drop_column('products', 'show_on_storefront')
