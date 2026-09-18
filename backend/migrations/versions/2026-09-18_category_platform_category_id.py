"""categories.platform_category_id — привязка категории магазина к общему
справочнику категорий платформы (M-B1 п.1)

Revision ID: bb829e81f02a
Revises: e67db7e572c9
Create Date: 2026-09-18 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb829e81f02a'
down_revision: Union[str, Sequence[str], None] = 'e67db7e572c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'categories',
        sa.Column('platform_category_id', sa.Integer(), sa.ForeignKey('platform_categories.id')),
    )


def downgrade() -> None:
    op.drop_column('categories', 'platform_category_id')
