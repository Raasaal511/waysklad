"""Слияние двух веток миграций: Web Push и регистрация владельца через Telegram.

Обе выросли из d5e9a3b7f024 и независимы (push_subscriptions и
telegram_verifications не пересекаются), поэтому ревизия пустая — она
только сводит две головы в одну.

Revision ID: a1b4e7c2d508
Revises: e6f1b4c8a935, f7a2c5d9b146
Create Date: 2026-10-02
"""

from typing import Sequence, Union

revision: str = "a1b4e7c2d508"
down_revision: Union[str, Sequence[str], None] = ("e6f1b4c8a935", "f7a2c5d9b146")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
