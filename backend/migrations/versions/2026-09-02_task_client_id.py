"""tasks.client_id — привязка задачи к клиенту (CRM: лента событий клиента)

Revision ID: f4d8b2a6c9e3
Revises: e7c5a3f9d1b4
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4d8b2a6c9e3'
down_revision: Union[str, Sequence[str], None] = 'e7c5a3f9d1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('client_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_tasks_client_id', 'tasks', 'clients', ['client_id'], ['id'],
    )
    op.create_index('ix_tasks_client_id', 'tasks', ['client_id'])


def downgrade() -> None:
    op.drop_index('ix_tasks_client_id', table_name='tasks')
    op.drop_constraint('fk_tasks_client_id', 'tasks', type_='foreignkey')
    op.drop_column('tasks', 'client_id')
