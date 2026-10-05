"""customer_phone_changes — смена номера покупателем через Telegram.

Вошедший покупатель не мог сменить номер вообще никак: телефон приходит из
контакта Telegram при входе и служит идентичностью аккаунта. Заявка на смену
живёт отдельно от ссылки входа (CustomerLoginLink) — там вход в аккаунт,
здесь изменение существующего, и подтверждает её владелец НОВОГО номера.

Revision ID: c8a2f6b4d913
Revises: b3c7d2f1e846
Create Date: 2026-10-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8a2f6b4d913"
down_revision: Union[str, Sequence[str], None] = "b3c7d2f1e846"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_phone_changes",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("new_phone", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_customer_phone_changes_customer_id", "customer_phone_changes", ["customer_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_customer_phone_changes_customer_id", table_name="customer_phone_changes")
    op.drop_table("customer_phone_changes")
