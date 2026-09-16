"""reviews — отзывы покупателей на товар, привязаны к принятой заявке с
витрины (один отзыв на заявку), модерация владельцем через is_hidden.

Revision ID: 7625414d2dbb
Revises: 7d3a9c5e2f14
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7625414d2dbb'
down_revision: Union[str, Sequence[str], None] = '7d3a9c5e2f14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reviews',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False),
        sa.Column(
            'storefront_request_id', sa.Integer(),
            sa.ForeignKey('storefront_requests.id'), nullable=False,
        ),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False, server_default=''),
        sa.Column('author_name', sa.String(200), nullable=False),
        sa.Column('photo', sa.String(500), nullable=False, server_default=''),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_reviews_tenant_id', 'reviews', ['tenant_id'])
    op.create_index('ix_reviews_product_id', 'reviews', ['product_id'])
    op.create_index('ix_reviews_customer_id', 'reviews', ['customer_id'])
    op.create_index(
        'ix_reviews_storefront_request_id', 'reviews', ['storefront_request_id'], unique=True
    )


def downgrade() -> None:
    op.drop_index('ix_reviews_storefront_request_id', table_name='reviews')
    op.drop_index('ix_reviews_customer_id', table_name='reviews')
    op.drop_index('ix_reviews_product_id', table_name='reviews')
    op.drop_index('ix_reviews_tenant_id', table_name='reviews')
    op.drop_table('reviews')
