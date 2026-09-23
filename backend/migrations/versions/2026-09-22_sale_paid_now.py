"""sales.paid_now — часть суммы, оплаченная сразу при продаже в долг.

Остаток (total − paid_now) уходит в Debt. Не смешивается с prepayment
(предоплата по заказу): paid_now не уменьшает Sale.total и выручку.

Revision ID: b3c7e1a9d204
Revises: a1c9e2f4b806
Create Date: 2026-09-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c7e1a9d204"
down_revision: Union[str, Sequence[str], None] = "a1c9e2f4b806"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sales",
        sa.Column("paid_now", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("sales", "paid_now")
