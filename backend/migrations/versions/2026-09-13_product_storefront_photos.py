"""products.storefront_photos — галерея фото для карточки товара на витрине,
независимая от складского products.photo (одна фотография для учёта).

Revision ID: 3f8a6c2d9b17
Revises: 9d2b5f7a1c84
Create Date: 2026-09-13 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f8a6c2d9b17'
down_revision: Union[str, Sequence[str], None] = '9d2b5f7a1c84'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('storefront_photos', sa.JSON(), nullable=False, server_default='[]'),
    )


def downgrade() -> None:
    op.drop_column('products', 'storefront_photos')
