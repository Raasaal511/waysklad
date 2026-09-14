"""sales.prepayment — предоплата, уже полученная ранее (при приёме заказа),
отделена от discount. Уменьшает только Sale.total (сумму к доплате), не
revenue — раньше предоплата ошибочно кодировалась как discount и после
введения вычета discount из аналитики (2026-09-14) стала искажать выручку.

Revision ID: 7d3a9c5e2f14
Revises: 4b6e1f8a3d52
Create Date: 2026-09-14 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d3a9c5e2f14'
down_revision: Union[str, Sequence[str], None] = '4b6e1f8a3d52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'sales',
        sa.Column('prepayment', sa.Numeric(12, 2), nullable=False, server_default='0'),
    )
    # исторические продажи из выдачи заказа (order_id заполнен) кодировали
    # предоплату как discount — переносим значение в новое поле, чтобы
    # прошлая аналитика тоже не оказалась искажённой задним числом
    op.execute(
        "UPDATE sales SET prepayment = discount, discount = 0 WHERE order_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE sales SET discount = prepayment WHERE order_id IS NOT NULL"
    )
    op.drop_column('sales', 'prepayment')
