"""telegram_bot_sessions — персистентное хранилище FSM-диалога Telegram-бота витрины

Revision ID: 9f2d5b8e4a1c
Revises: 4c8e1a6b3d7f
Create Date: 2026-09-04 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f2d5b8e4a1c'
down_revision: Union[str, Sequence[str], None] = '4c8e1a6b3d7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'telegram_bot_sessions',
        # aiogram StorageKey — bot_id+chat_id+user_id, а не только chat_id:
        # один и тот же бот может обслуживать несколько ботов (разные bot_id
        # при смене токена) и групповые чаты (chat_id != user_id) — составной
        # ключ соответствует контракту BaseStorage, не только текущему MVP-сценарию
        sa.Column('bot_id', sa.BigInteger(), primary_key=True),
        sa.Column('chat_id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), primary_key=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('data', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('telegram_bot_sessions')
