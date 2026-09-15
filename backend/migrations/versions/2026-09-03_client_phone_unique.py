"""clients: телефон уникален в пределах магазина (непустой) — заявки с витрины находят клиента по телефону

Revision ID: c3e9a1d4f6b8
Revises: a1c6e0f3b7d2
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3e9a1d4f6b8'
down_revision: Union[str, Sequence[str], None] = 'a1c6e0f3b7d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'uq_clients_tenant_phone', 'clients', ['tenant_id', 'phone'],
        unique=True, postgresql_where="phone != ''",
    )


def downgrade() -> None:
    op.drop_index('uq_clients_tenant_phone', table_name='clients')
