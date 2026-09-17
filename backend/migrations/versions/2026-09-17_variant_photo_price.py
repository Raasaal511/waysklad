"""product_variants.photo/price — своё фото и своя цена на вариант товара,
независимые от складского products.photo и products.retail_price (по умолчанию
цена варианта не задана — используется цена товара).

Revision ID: ef0c4189ea12
Revises: 7bf239d6b97b
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef0c4189ea12'
down_revision: Union[str, Sequence[str], None] = '7bf239d6b97b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'product_variants',
        sa.Column('photo', sa.String(500), nullable=False, server_default=''),
    )
    op.add_column(
        'product_variants',
        sa.Column('price', sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('product_variants', 'price')
    op.drop_column('product_variants', 'photo')
