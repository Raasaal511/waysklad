"""tenants: описание магазина, контакты (телефон/WhatsApp/Telegram),
минимальная сумма заказа, тексты политик (возврат денег/оплата/доставка/
возврат товаров) — публичный профиль магазина (промпт B2 п.1).

Revision ID: c1a9f0e3b7d2
Revises: aae7ba8019cc
Create Date: 2026-09-18 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a9f0e3b7d2'
down_revision: Union[str, Sequence[str], None] = 'aae7ba8019cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tenants', sa.Column('storefront_description', sa.String(500), nullable=False, server_default='')
    )
    op.add_column('tenants', sa.Column('contact_phone', sa.String(20), nullable=False, server_default=''))
    op.add_column('tenants', sa.Column('contact_whatsapp', sa.String(20), nullable=False, server_default=''))
    op.add_column('tenants', sa.Column('contact_telegram', sa.String(32), nullable=False, server_default=''))
    op.add_column('tenants', sa.Column('storefront_min_order_total', sa.Numeric(12, 2), nullable=True))
    op.add_column('tenants', sa.Column('policy_refund_money', sa.Text(), nullable=False, server_default=''))
    op.add_column('tenants', sa.Column('policy_payment', sa.Text(), nullable=False, server_default=''))
    op.add_column('tenants', sa.Column('policy_delivery', sa.Text(), nullable=False, server_default=''))
    op.add_column('tenants', sa.Column('policy_returns', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('tenants', 'policy_returns')
    op.drop_column('tenants', 'policy_delivery')
    op.drop_column('tenants', 'policy_payment')
    op.drop_column('tenants', 'policy_refund_money')
    op.drop_column('tenants', 'storefront_min_order_total')
    op.drop_column('tenants', 'contact_telegram')
    op.drop_column('tenants', 'contact_whatsapp')
    op.drop_column('tenants', 'contact_phone')
    op.drop_column('tenants', 'storefront_description')
