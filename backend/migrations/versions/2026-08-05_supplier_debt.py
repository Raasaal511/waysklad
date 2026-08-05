"""debt supports supplier counterparty

Revision ID: 8f1c2e4a7b3d
Revises: 677649b86b38
Create Date: 2026-08-05 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f1c2e4a7b3d'
down_revision: Union[str, Sequence[str], None] = '677649b86b38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('debts', 'client_id', existing_type=sa.Integer(), nullable=True)
    op.add_column('debts', sa.Column('supplier_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_debts_supplier_id', 'debts', 'suppliers', ['supplier_id'], ['id']
    )
    op.create_index(op.f('ix_debts_supplier_id'), 'debts', ['supplier_id'], unique=False)
    op.create_check_constraint(
        'ck_debts_one_counterparty', 'debts',
        '(client_id IS NOT NULL) != (supplier_id IS NOT NULL)',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_debts_one_counterparty', 'debts', type_='check')
    op.drop_index(op.f('ix_debts_supplier_id'), table_name='debts')
    op.drop_constraint('fk_debts_supplier_id', 'debts', type_='foreignkey')
    op.drop_column('debts', 'supplier_id')
    op.alter_column('debts', 'client_id', existing_type=sa.Integer(), nullable=False)
