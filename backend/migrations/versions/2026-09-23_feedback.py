"""feedback — обращения из кабинета (вопрос / ошибка / рекомендация) для админки.

Только новая таблица: существующие данные не трогаются, старый код с новой
схемой работает, пока перезапускаются контейнеры.

Revision ID: c4d8f2a6e913
Revises: b3c7e1a9d204
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "c4d8f2a6e913"
down_revision: Union[str, Sequence[str], None] = "b3c7e1a9d204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("topic", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("photos", JSONB(), nullable=False, server_default="[]"),
        sa.Column("page", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("user_agent", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("app_version", sa.String(length=50), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_feedback_tenant_id", "feedback", ["tenant_id"])
    op.create_index("ix_feedback_created", "feedback", ["created_at"])
    op.create_index("ix_feedback_resolved", "feedback", ["resolved_at"])
    op.create_index("ix_feedback_user_created", "feedback", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_feedback_user_created", table_name="feedback")
    op.drop_index("ix_feedback_resolved", table_name="feedback")
    op.drop_index("ix_feedback_created", table_name="feedback")
    op.drop_index("ix_feedback_tenant_id", table_name="feedback")
    op.drop_table("feedback")
