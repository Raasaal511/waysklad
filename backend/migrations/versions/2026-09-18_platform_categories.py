"""platform_categories — глобальный справочник категорий платформы (без
tenant_id), плюс сид базового набора (M-B1 п.1)

Revision ID: e67db7e572c9
Revises: ef0c4189ea12
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e67db7e572c9'
down_revision: Union[str, Sequence[str], None] = 'ef0c4189ea12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (slug, name, sort_order) — базовый набор, slug латиницей (см. промпт M-B1 п.1)
_SEED_CATEGORIES = [
    ("electronics", "Электроника", 10),
    ("clothing", "Одежда", 20),
    ("shoes", "Обувь", 30),
    ("tools", "Инструменты", 40),
    ("auto", "Автотовары", 50),
    ("accessories", "Аксессуары", 60),
    ("food", "Продукты", 70),
    ("home", "Для дома", 80),
    ("beauty", "Красота", 90),
    ("kids", "Детские товары", 100),
    ("construction", "Строительство", 110),
    ("other", "Прочее", 120),
]


def upgrade() -> None:
    op.create_table(
        'platform_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('image', sa.String(500), nullable=False, server_default=''),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('platform_categories.id')),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        'ix_platform_categories_slug', 'platform_categories', ['slug'], unique=True
    )

    table = sa.table(
        'platform_categories',
        sa.column('name', sa.String),
        sa.column('slug', sa.String),
        sa.column('sort_order', sa.Integer),
    )
    op.bulk_insert(
        table,
        [{"name": name, "slug": slug, "sort_order": sort_order} for slug, name, sort_order in _SEED_CATEGORIES],
    )


def downgrade() -> None:
    op.drop_index('ix_platform_categories_slug', table_name='platform_categories')
    op.drop_table('platform_categories')
