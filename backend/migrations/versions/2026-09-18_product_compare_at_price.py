"""products.compare_at_price — старая цена для обычной розничной скидки на
витрине (не оптовая), NULL значит скидки нет (M-B1 п.4)

Revision ID: 2be3bd705bb6
Revises: 19e6010ad1f2
Create Date: 2026-09-18 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2be3bd705bb6'
down_revision: Union[str, Sequence[str], None] = '19e6010ad1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('compare_at_price', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'compare_at_price')
