"""storefront_requests.customer_telegram_chat_id — заявка из Telegram-бота витрины

Revision ID: 4c8e1a6b3d7f
Revises: 8b1e4f6c2a9d
Create Date: 2026-09-04 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c8e1a6b3d7f'
down_revision: Union[str, Sequence[str], None] = '8b1e4f6c2a9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'storefront_requests',
        sa.Column('customer_telegram_chat_id', sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('storefront_requests', 'customer_telegram_chat_id')
