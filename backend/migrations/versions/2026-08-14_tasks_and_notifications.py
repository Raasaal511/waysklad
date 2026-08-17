"""add tasks and notifications tables

Revision ID: a91f3c6d8b02
Revises: e6b4c8a2f7d1
Create Date: 2026-08-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a91f3c6d8b02'
down_revision: Union[str, Sequence[str], None] = 'e6b4c8a2f7d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('type', sa.Enum('general', 'restock', name='tasktype', native_enum=False, length=20), nullable=False),
        sa.Column('status', sa.Enum('new', 'in_progress', 'done', name='taskstatus', native_enum=False, length=20), nullable=False),
        sa.Column('assigned_user_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('warehouse_id', sa.Integer(), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'number'),
    )
    op.create_index(op.f('ix_tasks_tenant_id'), 'tasks', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tasks_assigned_user_id'), 'tasks', ['assigned_user_id'], unique=False)

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.Enum('task_assigned', 'task_done', name='notificationkind', native_enum=False, length=30), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('link', sa.String(length=200), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_tenant_id'), 'notifications', ['tenant_id'], unique=False)
    op.create_index(
        'ix_notifications_user_unread', 'notifications', ['tenant_id', 'user_id', 'is_read'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_notifications_user_unread', table_name='notifications')
    op.drop_index(op.f('ix_notifications_tenant_id'), table_name='notifications')
    op.drop_table('notifications')

    op.drop_index(op.f('ix_tasks_assigned_user_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_tenant_id'), table_name='tasks')
    op.drop_table('tasks')
