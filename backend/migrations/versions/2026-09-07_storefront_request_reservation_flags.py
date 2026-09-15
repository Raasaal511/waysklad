"""storefront_requests.insufficient_stock_at_request/reservation_released — мягкий
резерв под заявку с витрины (см. CreateStorefrontRequestUseCase / scheduler)

Revision ID: 1530d46dd2f5
Revises: 6d2f8a1c4b93
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1530d46dd2f5'
down_revision: Union[str, Sequence[str], None] = '6d2f8a1c4b93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'storefront_requests',
        sa.Column('insufficient_stock_at_request', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'storefront_requests',
        sa.Column('reservation_released', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # существующие заявки не в NEW уже фактически "разрешены" — обновление
    # резерва их больше не касается; не даём авто-освобождению трогать их снова
    op.execute(
        "UPDATE storefront_requests SET reservation_released = true WHERE status != 'new'"
    )


def downgrade() -> None:
    op.drop_column('storefront_requests', 'reservation_released')
    op.drop_column('storefront_requests', 'insufficient_stock_at_request')
