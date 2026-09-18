"""product_view_daily — просмотры карточки товара на витрине, агрегированные
по дню (промпт B1 п.5). Сырые события (кто/когда/IP) не храним — только
Redis-ключ для дедупликации на время TTL, см. RecordProductViewUseCase.

Revision ID: aae7ba8019cc
Revises: 6f5fbdec3a40
Create Date: 2026-09-18 21:50:49.530873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aae7ba8019cc'
down_revision: Union[str, Sequence[str], None] = '6f5fbdec3a40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_view_daily',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column(
            'product_id', sa.Integer(), sa.ForeignKey('products.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('tenant_id', 'product_id', 'day'),
    )
    op.create_index(
        'ix_product_view_daily_tenant_id', 'product_view_daily', ['tenant_id']
    )


def downgrade() -> None:
    op.drop_index('ix_product_view_daily_tenant_id', table_name='product_view_daily')
    op.drop_table('product_view_daily')
