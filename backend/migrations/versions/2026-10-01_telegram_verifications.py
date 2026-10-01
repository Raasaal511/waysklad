"""telegram_verifications + users.telegram_* — регистрация владельца через бота.

Магазин создаётся только после того, как бот получил контакт владельца
(номер совпал с указанным на сайте) и владелец ввёл код из чата на сайте.
До этого данные формы ждут здесь. Та же таблица — для привязки Telegram
уже зарегистрированным владельцем из кабинета.

Revision ID: f7a2c5d9b146
Revises: d5e9a3b7f024
Create Date: 2026-10-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f7a2c5d9b146"
down_revision: Union[str, Sequence[str], None] = "d5e9a3b7f024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("shop_name", sa.String(200), nullable=True),
        sa.Column("owner_name", sa.String(200), nullable=True),
        sa.Column("password_hash", sa.String(200), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("telegram_user_id", sa.String(32), nullable=True),
        sa.Column("telegram_chat_id", sa.String(32), nullable=True),
        sa.Column("telegram_username", sa.String(64), nullable=False, server_default=""),
        sa.Column("code_hash", sa.String(200), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("telegram_user_id", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("telegram_verified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "telegram_verified_at")
    op.drop_column("users", "telegram_user_id")
    op.drop_table("telegram_verifications")
