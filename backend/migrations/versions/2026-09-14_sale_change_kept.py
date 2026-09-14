"""sales.change_kept — клиент не забрал сдачу (округление в пользу магазина),
учитывается отдельно от discount/цены строк, не искажает revenue по товару.

Revision ID: 4b6e1f8a3d52
Revises: 8e7d4a2f6c91
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b6e1f8a3d52'
down_revision: Union[str, Sequence[str], None] = '8e7d4a2f6c91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'sales',
        sa.Column('change_kept', sa.Numeric(12, 2), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('sales', 'change_kept')
