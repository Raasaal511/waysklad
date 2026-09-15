"""notifications.snapshot_value — числовой снимок сущности на момент отправки
(остаток товара для LOW_STOCK), защита от ежедневного повтора, пока значение
не улучшится

Revision ID: 5f1a9c3e7d42
Revises: 36dd267585ac
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f1a9c3e7d42'
down_revision: Union[str, Sequence[str], None] = '36dd267585ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'notifications',
        sa.Column('snapshot_value', sa.Numeric(14, 3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('notifications', 'snapshot_value')
