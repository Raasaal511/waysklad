"""personal_data_consent_at on users and customers

Фиксация момента согласия на обработку телефона при регистрации (152-ФЗ).
Существующие аккаунты — NULL (не блокируем).

Revision ID: a1c9e2f4b806
Revises: f2b6c8d4a731
Create Date: 2026-09-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c9e2f4b806"
down_revision: Union[str, Sequence[str], None] = "f2b6c8d4a731"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("personal_data_consent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("personal_data_consent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("customers", "personal_data_consent_at")
    op.drop_column("users", "personal_data_consent_at")
