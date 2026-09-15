"""debts.warehouse_id — обязательный склад долга (для scoped-фильтрации manager/seller/storekeeper)

Revision ID: 25dbfc78eebc
Revises: e2a6c9f4b1d8
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25dbfc78eebc'
down_revision: Union[str, Sequence[str], None] = 'e2a6c9f4b1d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('debts', sa.Column('warehouse_id', sa.Integer(), nullable=True))

    # Приоритет источника истины: долг из продажи -> склад продажи; долг из
    # приёмки -> склад документа приёмки; ручной долг без документа -> первый
    # склад тенанта (тот же фолбэк, что уже применялся для orders.warehouse_id).
    op.execute(
        """
        UPDATE debts
        SET warehouse_id = sales.warehouse_id
        FROM sales
        WHERE debts.sale_id = sales.id AND debts.warehouse_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE debts
        SET warehouse_id = stock_documents.warehouse_id
        FROM stock_documents
        WHERE debts.receipt_document_id = stock_documents.id AND debts.warehouse_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE debts
        SET warehouse_id = (
            SELECT id FROM warehouses
            WHERE warehouses.tenant_id = debts.tenant_id
            ORDER BY id LIMIT 1
        )
        WHERE warehouse_id IS NULL
        """
    )

    op.alter_column('debts', 'warehouse_id', existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key('fk_debts_warehouse_id', 'debts', 'warehouses', ['warehouse_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_debts_warehouse_id', 'debts', type_='foreignkey')
    op.drop_column('debts', 'warehouse_id')
