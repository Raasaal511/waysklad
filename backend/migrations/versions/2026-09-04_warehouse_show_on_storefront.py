"""warehouses.show_on_storefront — видимость склада на публичной витрине

Revision ID: 3f7a2c9d1b6e
Revises: 25dbfc78eebc
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f7a2c9d1b6e'
down_revision: Union[str, Sequence[str], None] = '25dbfc78eebc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'warehouses',
        sa.Column('show_on_storefront', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('warehouses', 'show_on_storefront')
