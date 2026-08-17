"""order.due_date becomes required — backfill existing NULLs with today

Revision ID: c3d8e1a4f620
Revises: f2a7c5e9d340
Create Date: 2026-08-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d8e1a4f620'
down_revision: Union[str, Sequence[str], None] = 'f2a7c5e9d340'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE orders SET due_date = CURRENT_DATE WHERE due_date IS NULL")
    op.alter_column('orders', 'due_date', existing_type=sa.Date(), nullable=False)


def downgrade() -> None:
    op.alter_column('orders', 'due_date', existing_type=sa.Date(), nullable=True)
