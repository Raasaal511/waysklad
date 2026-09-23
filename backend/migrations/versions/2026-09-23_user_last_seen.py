"""users.last_seen_at — когда пользователь последний раз работал в кабинете.

last_login_at меняется только при вводе пароля, а токен живёт до 30 дней:
владелец может работать каждый день и при этом «входить» раз в месяц.
Админке платформы нужно именно последнее обращение, поэтому отдельное поле.

Revision ID: d5e9a3b7f024
Revises: c4d8f2a6e913
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e9a3b7f024"
down_revision: Union[str, Sequence[str], None] = "c4d8f2a6e913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    # вход — тоже активность: до первого запроса после выката показываем его
    op.execute("UPDATE users SET last_seen_at = last_login_at")


def downgrade() -> None:
    op.drop_column("users", "last_seen_at")
