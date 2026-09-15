"""warehouse_client_links/warehouse_supplier_links — видимость Client/Supplier по складу для warehouse-scoped ролей

Revision ID: 6d2f8a1c4b93
Revises: 1a7c3e9d2f45
Create Date: 2026-09-05 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d2f8a1c4b93'
down_revision: Union[str, Sequence[str], None] = '1a7c3e9d2f45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'warehouse_client_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('warehouse_id', 'client_id'),
    )
    op.create_index(
        op.f('ix_warehouse_client_links_warehouse_id'),
        'warehouse_client_links', ['warehouse_id'],
    )
    op.create_index(
        op.f('ix_warehouse_client_links_client_id'),
        'warehouse_client_links', ['client_id'],
    )

    op.create_table(
        'warehouse_supplier_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('warehouse_id', 'supplier_id'),
    )
    op.create_index(
        op.f('ix_warehouse_supplier_links_warehouse_id'),
        'warehouse_supplier_links', ['warehouse_id'],
    )
    op.create_index(
        op.f('ix_warehouse_supplier_links_supplier_id'),
        'warehouse_supplier_links', ['supplier_id'],
    )

    # backfill: клиенты/поставщики уже засветившиеся на складе через
    # продажи/заказы/долги/приёмки до появления линк-таблиц
    op.execute(
        """
        INSERT INTO warehouse_client_links (warehouse_id, client_id)
        SELECT DISTINCT warehouse_id, client_id FROM sales WHERE client_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO warehouse_client_links (warehouse_id, client_id)
        SELECT DISTINCT warehouse_id, client_id FROM orders
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO warehouse_client_links (warehouse_id, client_id)
        SELECT DISTINCT warehouse_id, client_id FROM debts WHERE client_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO warehouse_supplier_links (warehouse_id, supplier_id)
        SELECT DISTINCT warehouse_id, supplier_id FROM stock_documents WHERE supplier_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO warehouse_supplier_links (warehouse_id, supplier_id)
        SELECT DISTINCT warehouse_id, supplier_id FROM debts WHERE supplier_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_warehouse_supplier_links_supplier_id'), table_name='warehouse_supplier_links'
    )
    op.drop_index(
        op.f('ix_warehouse_supplier_links_warehouse_id'), table_name='warehouse_supplier_links'
    )
    op.drop_table('warehouse_supplier_links')
    op.drop_index(
        op.f('ix_warehouse_client_links_client_id'), table_name='warehouse_client_links'
    )
    op.drop_index(
        op.f('ix_warehouse_client_links_warehouse_id'), table_name='warehouse_client_links'
    )
    op.drop_table('warehouse_client_links')
