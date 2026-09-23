"""customer phone verification

Подтверждение телефона покупателя кодом: флаг на аккаунте и таблица кодов.
Код хранится только хешем — в логах и дампах шестизначного кода быть не должно.

Revision ID: d4c7b1a9e526
Revises: b7e2d4a1c8f5
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4c7b1a9e526'
down_revision: Union[str, Sequence[str], None] = 'b7e2d4a1c8f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "customers",
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "customer_phone_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_via", sa.String(length=16), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_customer_phone_codes_customer_id", "customer_phone_codes", ["customer_id"]
    )
    # лимит «не больше N кодов в час» — самый частый запрос к таблице
    op.create_index(
        "ix_customer_phone_codes_customer_created",
        "customer_phone_codes",
        ["customer_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("customer_phone_codes")
    op.drop_column("customers", "phone_verified_at")
    op.drop_column("customers", "phone_verified")
