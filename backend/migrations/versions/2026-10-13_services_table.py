"""Услуги: поля, которых не бывает у товара, — в своей таблице services.

Позиция услуги остаётся в products (kind='service'): строка чека, возврат,
аналитика и офлайн-очередь ссылаются на products и не меняются. Здесь —
только длительность и исполнитель, 1:1 по product_id.

Строки для уже созданных услуг не досеиваем: нет строки — значит
длительность не указана и исполнитель не закреплён, код это так и читает.

Revision ID: e7b3c5d2a814
Revises: d4f1a9c3b762
Create Date: 2026-10-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7b3c5d2a814"
down_revision: Union[str, Sequence[str], None] = "d4f1a9c3b762"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "performer_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "product_id"),
    )
    op.create_index("ix_services_tenant_id", "services", ["tenant_id"])
    op.create_index("ix_services_product_id", "services", ["product_id"])


def downgrade() -> None:
    op.drop_table("services")
