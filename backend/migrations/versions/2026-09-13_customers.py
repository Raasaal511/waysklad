"""customers + customer_login_links — авторизация покупателей витрины по
телефону, подтверждение через Telegram-бота (deep-link + login_token).
Общие на платформу таблицы, без tenant_id (тот же паттерн, что tenants).

Revision ID: 6a1f3e9c5b28
Revises: 3f8a6c2d9b17
Create Date: 2026-09-13 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a1f3e9c5b28'
down_revision: Union[str, Sequence[str], None] = '3f8a6c2d9b17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('phone', sa.String(20), nullable=False, unique=True),
        sa.Column('telegram_chat_id', sa.String(32), nullable=False, server_default=''),
        sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index('ix_customers_phone', 'customers', ['phone'])

    op.create_table(
        'customer_login_links',
        sa.Column('token', sa.String(64), primary_key=True),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_customer_login_links_phone', 'customer_login_links', ['phone'])


def downgrade() -> None:
    op.drop_table('customer_login_links')
    op.drop_table('customers')
