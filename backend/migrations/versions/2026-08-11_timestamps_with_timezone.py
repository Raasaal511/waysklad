"""convert all timestamp columns to TIMESTAMP WITH TIME ZONE (values are UTC already)

Revision ID: e6b4c8a2f7d1
Revises: d3e7a1f9b4c2
Create Date: 2026-08-11 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6b4c8a2f7d1'
down_revision: Union[str, Sequence[str], None] = 'd3e7a1f9b4c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column) — все timestamp-колонки без часового пояса, хранящие данные в UTC
_COLUMNS = [
    ('audit_log', 'created_at'),
    ('categories', 'created_at'),
    ('categories', 'updated_at'),
    ('clients', 'created_at'),
    ('clients', 'updated_at'),
    ('debts', 'created_at'),
    ('debts', 'updated_at'),
    ('orders', 'created_at'),
    ('orders', 'updated_at'),
    ('products', 'created_at'),
    ('products', 'updated_at'),
    ('sale_returns', 'created_at'),
    ('sale_returns', 'updated_at'),
    ('sales', 'created_at'),
    ('sales', 'deleted_at'),
    ('sales', 'updated_at'),
    ('stock_documents', 'created_at'),
    ('stock_documents', 'posted_at'),
    ('stock_documents', 'updated_at'),
    ('suppliers', 'created_at'),
    ('suppliers', 'updated_at'),
    ('tenants', 'created_at'),
    ('tenants', 'updated_at'),
    ('users', 'created_at'),
    ('users', 'updated_at'),
    ('warehouses', 'created_at'),
    ('warehouses', 'updated_at'),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, column in _COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.DateTime(timezone=True),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table, column in _COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.DateTime(timezone=False),
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
