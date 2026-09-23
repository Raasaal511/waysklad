"""product_variants.name, products.warranty_text, tenants.storefront_show_stock_qty —
название варианта, гарантия товара и настройка «показывать точный остаток
на витрине» (промпт B1 п.1, п.2, п.4).

Revision ID: 6f5fbdec3a40
Revises: dfb4ef46f27a
Create Date: 2026-09-18 21:50:34.407999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f5fbdec3a40'
down_revision: Union[str, Sequence[str], None] = 'dfb4ef46f27a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'product_variants', sa.Column('name', sa.String(100), nullable=False, server_default='')
    )
    op.add_column(
        'products', sa.Column('warranty_text', sa.Text(), nullable=False, server_default='')
    )
    op.add_column(
        'tenants',
        sa.Column(
            'storefront_show_stock_qty', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column('tenants', 'storefront_show_stock_qty')
    op.drop_column('products', 'warranty_text')
    op.drop_column('product_variants', 'name')
