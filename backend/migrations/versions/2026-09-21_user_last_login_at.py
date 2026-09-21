"""user last_login_at

Отметка последнего входа сотрудника — нужна админке платформы, чтобы
отличать живой магазин от заброшенного. NULL = ни разу не входил после
введения поля (историю входов задним числом восстановить неоткуда).

Revision ID: e5a1b3c7d902
Revises: d4c7b1a9e526
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5a1b3c7d902'
down_revision: Union[str, Sequence[str], None] = 'd4c7b1a9e526'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
