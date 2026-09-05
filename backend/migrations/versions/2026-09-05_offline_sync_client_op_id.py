"""sale_returns/stock_documents.client_op_id — идемпотентность офлайн-синка возвратов/приёмок/списаний

Revision ID: 1a7c3e9d2f45
Revises: 9f2d5b8e4a1c
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a7c3e9d2f45'
down_revision: Union[str, Sequence[str], None] = '9f2d5b8e4a1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('sale_returns', sa.Column('client_op_id', sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        'uq_sale_returns_tenant_id_client_op_id', 'sale_returns', ['tenant_id', 'client_op_id']
    )
    op.add_column('stock_documents', sa.Column('client_op_id', sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        'uq_stock_documents_tenant_id_client_op_id', 'stock_documents', ['tenant_id', 'client_op_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'uq_stock_documents_tenant_id_client_op_id', 'stock_documents', type_='unique'
    )
    op.drop_column('stock_documents', 'client_op_id')
    op.drop_constraint(
        'uq_sale_returns_tenant_id_client_op_id', 'sale_returns', type_='unique'
    )
    op.drop_column('sale_returns', 'client_op_id')
