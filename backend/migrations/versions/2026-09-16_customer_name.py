"""customers.name — необязательное имя покупателя для личного профиля
(GET/PUT /auth/customer/me). Заполняется покупателем один раз, подставляется
на фронте в новые заявки вместо ручного ввода каждый раз.

Revision ID: 7bf239d6b97b
Revises: 7625414d2dbb
Create Date: 2026-09-16 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7bf239d6b97b'
down_revision: Union[str, Sequence[str], None] = '7625414d2dbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'customers',
        sa.Column('name', sa.String(200), nullable=False, server_default=''),
    )


def downgrade() -> None:
    op.drop_column('customers', 'name')
