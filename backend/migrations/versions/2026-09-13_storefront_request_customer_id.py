"""storefront_requests.customer_id — привязка к авторизованному Customer.
Nullable: старые (до перехода на авторизацию) заявки остаются без привязки,
новые заявки её обязаны иметь (см. CreateStorefrontRequestUseCase).

Revision ID: 8e7d4a2f6c91
Revises: 6a1f3e9c5b28
Create Date: 2026-09-13 00:00:04.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e7d4a2f6c91'
down_revision: Union[str, Sequence[str], None] = '6a1f3e9c5b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'storefront_requests',
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=True),
    )
    op.create_index(
        'ix_storefront_requests_customer_id', 'storefront_requests', ['customer_id']
    )


def downgrade() -> None:
    op.drop_index('ix_storefront_requests_customer_id', table_name='storefront_requests')
    op.drop_column('storefront_requests', 'customer_id')
