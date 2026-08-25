"""debts.receipt_document_id — долг поставщику из приёмки товара

Revision ID: a1b2c3d4e5f6
Revises: c3d8e1a4f620
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c3d8e1a4f620'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'debts',
        sa.Column('receipt_document_id', sa.Integer(), sa.ForeignKey('stock_documents.id'), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('debts', 'receipt_document_id')
