"""tenants.summary_daily_hour_utc -> summary_daily_hour_msk

Хранимое значение теперь трактуется как час по московскому времени (МСК,
UTC+3, без перехода на летнее — Россия его не использует с 2014 года),
а не UTC. Весь целевой рынок продукта (README §1) живёт в одном часовом
поясе, так что хранить/показывать час в МСК напрямую честнее и проще,
чем заставлять владельца магазина мысленно конвертировать UTC.

Revision ID: d3a9f6c1b8e2
Revises: c8f1d5a2e4b7
Create Date: 2026-08-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3a9f6c1b8e2'
down_revision: Union[str, Sequence[str], None] = 'c8f1d5a2e4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('tenants', 'summary_daily_hour_utc', new_column_name='summary_daily_hour_msk')
    op.alter_column(
        'tenants', 'summary_daily_hour_msk',
        server_default='20', existing_type=sa.SmallInteger(), existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'tenants', 'summary_daily_hour_msk',
        server_default='18', existing_type=sa.SmallInteger(), existing_nullable=False,
    )
    op.alter_column('tenants', 'summary_daily_hour_msk', new_column_name='summary_daily_hour_utc')
