"""storefront_requests/storefront_request_lines — сырые заявки с публичной витрины

Revision ID: d5f0b2c8a1e7
Revises: c3e9a1d4f6b8
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5f0b2c8a1e7'
down_revision: Union[str, Sequence[str], None] = 'c3e9a1d4f6b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'storefront_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('customer_name', sa.String(length=200), nullable=False),
        sa.Column('customer_phone', sa.String(length=20), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('new', 'accepted', 'rejected', name='storefrontrequeststatus', native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_storefront_requests_tenant_id'), 'storefront_requests', ['tenant_id'], unique=False
    )
    op.create_table(
        'storefront_request_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['request_id'], ['storefront_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['variant_id'], ['product_variants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_storefront_request_lines_tenant_id'), 'storefront_request_lines', ['tenant_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_storefront_request_lines_tenant_id'), table_name='storefront_request_lines')
    op.drop_table('storefront_request_lines')
    op.drop_index(op.f('ix_storefront_requests_tenant_id'), table_name='storefront_requests')
    op.drop_table('storefront_requests')
