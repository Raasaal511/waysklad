"""products.description — текст для карточки товара на витрине (не складская
характеристика), заполняется владельцем вручную или через AI-генерацию.

Revision ID: 9d2b5f7a1c84
Revises: 7c4e9a1d8f36
Create Date: 2026-09-13 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d2b5f7a1c84'
down_revision: Union[str, Sequence[str], None] = '7c4e9a1d8f36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
    )


def downgrade() -> None:
    op.drop_column('products', 'description')
