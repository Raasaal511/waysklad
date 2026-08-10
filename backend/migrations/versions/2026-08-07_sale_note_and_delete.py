"""add sales.note and sales.deleted_at (soft-delete)

Revision ID: a1e4f9c2b8d6
Revises: d5b9f3a2c7e1
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1e4f9c2b8d6'
down_revision: Union[str, Sequence[str], None] = 'd5b9f3a2c7e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('sales', sa.Column('note', sa.Text(), nullable=False, server_default=''))
    op.add_column('sales', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.alter_column('sales', 'note', server_default=None)
    op.create_index(
        op.f('ix_audit_log_entity_entity_id'), 'audit_log', ['entity', 'entity_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_audit_log_entity_entity_id'), table_name='audit_log')
    op.drop_column('sales', 'deleted_at')
    op.drop_column('sales', 'note')
