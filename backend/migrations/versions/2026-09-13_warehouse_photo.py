"""warehouses.photo — необязательный логотип склада (тот же паттерн что
products.photo)

Revision ID: 7c4e9a1d8f36
Revises: 5f1a9c3e7d42
Create Date: 2026-09-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c4e9a1d8f36'
down_revision: Union[str, Sequence[str], None] = '5f1a9c3e7d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'warehouses',
        sa.Column('photo', sa.String(500), nullable=False, server_default=''),
    )


def downgrade() -> None:
    op.drop_column('warehouses', 'photo')
