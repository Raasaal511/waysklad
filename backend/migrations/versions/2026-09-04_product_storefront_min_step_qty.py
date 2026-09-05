"""products.storefront_min_qty/storefront_step_qty — минимум и шаг заказа на витрине

Revision ID: 8b1e4f6c2a9d
Revises: 3f7a2c9d1b6e
Create Date: 2026-09-04 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b1e4f6c2a9d'
down_revision: Union[str, Sequence[str], None] = '3f7a2c9d1b6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('storefront_min_qty', sa.Numeric(14, 3), nullable=True))
    op.add_column('products', sa.Column('storefront_step_qty', sa.Numeric(14, 3), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'storefront_step_qty')
    op.drop_column('products', 'storefront_min_qty')
