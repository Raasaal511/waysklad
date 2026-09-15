"""Чат по заявке с витрины: storefront_requests.access_token + storefront_messages

Revision ID: e2a6c9f4b1d8
Revises: d5f0b2c8a1e7
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2a6c9f4b1d8'
down_revision: Union[str, Sequence[str], None] = 'd5f0b2c8a1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'storefront_requests',
        sa.Column('access_token', sa.String(length=43), nullable=True),
    )
    # существующие строки (созданы до этой миграции) получают случайный токен
    # каждая — иначе все они остались бы с NULL/одинаковым значением и unique
    # index ниже упал бы на второй такой строке
    op.execute(
        "UPDATE storefront_requests SET access_token = replace(gen_random_uuid()::text, '-', '') "
        "WHERE access_token IS NULL"
    )
    op.alter_column('storefront_requests', 'access_token', nullable=False)
    op.create_index(
        op.f('ix_storefront_requests_access_token'), 'storefront_requests', ['access_token'], unique=True
    )

    op.create_table(
        'storefront_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column(
            'author',
            sa.Enum('customer', 'staff', name='messageauthor', native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['request_id'], ['storefront_requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_storefront_messages_tenant_id'), 'storefront_messages', ['tenant_id'], unique=False
    )
    op.create_index(
        op.f('ix_storefront_messages_request_id'), 'storefront_messages', ['request_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_storefront_messages_request_id'), table_name='storefront_messages')
    op.drop_index(op.f('ix_storefront_messages_tenant_id'), table_name='storefront_messages')
    op.drop_table('storefront_messages')
    op.drop_index(op.f('ix_storefront_requests_access_token'), table_name='storefront_requests')
    op.drop_column('storefront_requests', 'access_token')
