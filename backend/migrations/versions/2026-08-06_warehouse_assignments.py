"""add warehouse_assignments table + backfill existing storekeepers

Revision ID: d5b9f3a2c7e1
Revises: c4a8e2f1b6d3
Create Date: 2026-08-06 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5b9f3a2c7e1'
down_revision: Union[str, Sequence[str], None] = 'c4a8e2f1b6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'warehouse_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_warehouse_assignments_warehouse_id'),
        'warehouse_assignments', ['warehouse_id'],
    )
    op.create_index(
        op.f('ix_warehouse_assignments_user_id'),
        'warehouse_assignments', ['user_id'],
    )

    # Существующие кладовщики (storekeeper) пока не привязаны ни к одному складу —
    # без бэкафилла они мгновенно потеряли бы доступ ко всем складам своего
    # tenant при включении ограничения. Назначаем их на все склады их магазина.
    connection = op.get_bind()
    connection.execute(sa.text(
        """
        INSERT INTO warehouse_assignments (warehouse_id, user_id)
        SELECT w.id, u.id
        FROM users u
        JOIN warehouses w ON w.tenant_id = u.tenant_id
        WHERE u.role = 'storekeeper'
        """
    ))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_warehouse_assignments_user_id'), table_name='warehouse_assignments')
    op.drop_index(
        op.f('ix_warehouse_assignments_warehouse_id'), table_name='warehouse_assignments'
    )
    op.drop_table('warehouse_assignments')
