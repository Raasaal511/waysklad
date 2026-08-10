"""add debt_repayments.note and debt_extensions table

Revision ID: b3f7e1a9c4d2
Revises: a1e4f9c2b8d6
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f7e1a9c4d2'
down_revision: Union[str, Sequence[str], None] = 'a1e4f9c2b8d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'debt_repayments', sa.Column('note', sa.Text(), nullable=False, server_default='')
    )
    op.alter_column('debt_repayments', 'note', server_default=None)

    op.create_table(
        'debt_extensions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('debt_id', sa.Integer(), nullable=False),
        sa.Column('old_due_date', sa.Date(), nullable=True),
        sa.Column('new_due_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False, server_default=''),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']),
        sa.ForeignKeyConstraint(['debt_id'], ['debts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('debt_extensions', 'reason', server_default=None)
    op.create_index(
        op.f('ix_debt_extensions_tenant_id'), 'debt_extensions', ['tenant_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_debt_extensions_tenant_id'), table_name='debt_extensions')
    op.drop_table('debt_extensions')
    op.drop_column('debt_repayments', 'note')
