"""platform_banners — баннеры платформы (карусель hero / промо-плитки главной
маркетплейса), без tenant_id, ведёт только админ (M-B2 п.1)

Revision ID: dfb4ef46f27a
Revises: 2be3bd705bb6
Create Date: 2026-09-18 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dfb4ef46f27a'
down_revision: Union[str, Sequence[str], None] = '2be3bd705bb6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'platform_banners',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('placement', sa.String(20), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('subtitle', sa.String(500), nullable=False, server_default=''),
        sa.Column('button_text', sa.String(100), nullable=False, server_default=''),
        sa.Column('link', sa.String(500), nullable=False, server_default=''),
        sa.Column('image', sa.String(500), nullable=False, server_default=''),
        sa.Column('image_mobile', sa.String(500), nullable=False, server_default=''),
        sa.Column('theme', sa.String(20), nullable=False, server_default='light'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('starts_at', sa.Date(), nullable=True),
        sa.Column('ends_at', sa.Date(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index('ix_platform_banners_placement', 'platform_banners', ['placement'])


def downgrade() -> None:
    op.drop_index('ix_platform_banners_placement', table_name='platform_banners')
    op.drop_table('platform_banners')
