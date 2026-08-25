"""tenants.summary_* — настройки расписания Telegram-сводки

Revision ID: c8f1d5a2e4b7
Revises: b7e2c4f9a1d3
Create Date: 2026-08-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f1d5a2e4b7'
down_revision: Union[str, Sequence[str], None] = 'b7e2c4f9a1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column('summary_daily_enabled', sa.Boolean(), nullable=False, server_default='true'),
    )
    op.add_column(
        'tenants',
        sa.Column('summary_weekly_enabled', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column(
        'tenants',
        sa.Column('summary_monthly_enabled', sa.Boolean(), nullable=False, server_default='false'),
    )
    op.add_column(
        'tenants',
        sa.Column('summary_daily_hour_utc', sa.SmallInteger(), nullable=False, server_default='18'),
    )


def downgrade() -> None:
    op.drop_column('tenants', 'summary_daily_hour_utc')
    op.drop_column('tenants', 'summary_monthly_enabled')
    op.drop_column('tenants', 'summary_weekly_enabled')
    op.drop_column('tenants', 'summary_daily_enabled')
