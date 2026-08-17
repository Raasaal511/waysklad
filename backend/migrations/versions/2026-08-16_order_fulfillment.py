"""order reservation, warehouse/source, order<->sale link

Revision ID: f2a7c5e9d340
Revises: a91f3c6d8b02
Create Date: 2026-08-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a7c5e9d340'
down_revision: Union[str, Sequence[str], None] = 'a91f3c6d8b02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'stock_items',
        sa.Column('reserved', sa.Numeric(precision=14, scale=3), server_default='0', nullable=False),
    )

    op.add_column('orders', sa.Column('warehouse_id', sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE orders
        SET warehouse_id = (
            SELECT id FROM warehouses
            WHERE warehouses.tenant_id = orders.tenant_id
            ORDER BY id LIMIT 1
        )
        WHERE warehouse_id IS NULL
        """
    )
    op.alter_column('orders', 'warehouse_id', existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key('fk_orders_warehouse_id', 'orders', 'warehouses', ['warehouse_id'], ['id'])

    op.add_column(
        'orders',
        sa.Column(
            'source',
            sa.Enum('whatsapp', 'instagram', 'call', 'in_person', name='ordersource', native_enum=False, length=20),
            server_default='in_person',
            nullable=False,
        ),
    )

    op.add_column('orders', sa.Column('sale_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_orders_sale_id', 'orders', 'sales', ['sale_id'], ['id'])

    op.add_column('sales', sa.Column('order_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_sales_order_id', 'sales', 'orders', ['order_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_sales_order_id', 'sales', type_='foreignkey')
    op.drop_column('sales', 'order_id')

    op.drop_constraint('fk_orders_sale_id', 'orders', type_='foreignkey')
    op.drop_column('orders', 'sale_id')

    op.drop_column('orders', 'source')

    op.drop_constraint('fk_orders_warehouse_id', 'orders', type_='foreignkey')
    op.drop_column('orders', 'warehouse_id')

    op.drop_column('stock_items', 'reserved')
