"""customer username + password_hash

Регистрация покупателя: username, телефон, пароль. Существующие аккаунты
заведены входом через Telegram — у них оба поля пустые.

Revision ID: b7e2d4a1c8f5
Revises: a3f8c1d9e0b4
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7e2d4a1c8f5'
down_revision: Union[str, Sequence[str], None] = 'a3f8c1d9e0b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("username", sa.String(length=32), nullable=False, server_default=""),
    )
    op.add_column(
        "customers",
        sa.Column("password_hash", sa.String(length=128), nullable=False, server_default=""),
    )
    # уникальность только среди заполненных: аккаунтов из Telegram-входа без
    # username может быть сколько угодно, обычный unique их бы запретил.
    # lower() — «Vasya» и «vasya» считаются одним логином (см. get_by_username).
    op.execute(
        "CREATE UNIQUE INDEX uq_customers_username_lower "
        "ON customers (lower(username)) WHERE username <> ''"
    )
    # данные регистрации ждут подтверждения номера ботом — до этого момента
    # аккаунта ещё нет (см. CustomerLoginLink.create_for_registration)
    op.add_column(
        "customer_login_links",
        sa.Column("username", sa.String(length=32), nullable=False, server_default=""),
    )
    op.add_column(
        "customer_login_links",
        sa.Column("password_hash", sa.String(length=128), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("customer_login_links", "password_hash")
    op.drop_column("customer_login_links", "username")
    op.execute("DROP INDEX IF EXISTS uq_customers_username_lower")
    op.drop_column("customers", "password_hash")
    op.drop_column("customers", "username")
