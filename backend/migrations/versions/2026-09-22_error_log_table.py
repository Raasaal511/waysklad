"""error_log table

Ошибки переезжают из Redis в БД: группировка по сигнатуре, счётчики за 7 дней
и пометка «решено» требуют персистентности — после перезапуска Redis эти данные
врали бы. Redis остаётся буфером для алертов.

Персональных данных таблица не хранит: ни тела запроса, ни заголовков, ни
телефонов — только время, путь, метод, тип, статус, сообщение, стек и tenant_id.

Revision ID: f2b6c8d4a731
Revises: e5a1b3c7d902
Create Date: 2026-09-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f2b6c8d4a731'
down_revision: Union[str, Sequence[str], None] = 'e5a1b3c7d902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "error_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("signature", sa.String(length=64), nullable=False),
        sa.Column("error_type", sa.String(length=100), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("stack", sa.Text(), nullable=False, server_default=""),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    # группировка по сигнатуре за период — основной запрос админки
    op.create_index("ix_error_log_signature_created", "error_log", ["signature", "created_at"])
    op.create_index("ix_error_log_created", "error_log", ["created_at"])
    op.create_index("ix_error_log_resolved", "error_log", ["resolved_at"])


def downgrade() -> None:
    op.drop_table("error_log")
