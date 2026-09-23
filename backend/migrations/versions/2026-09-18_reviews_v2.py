"""reviews v2 (промпт B3): уникальность по паре (заявка, товар) вместо
только заявки, несколько фото (JSONB), теги (JSONB), голоса
«полезно/не полезно» (review_votes), загрузки фото отзывов (review_uploads).

Revision ID: 15c062d170cd
Revises: c1a9f0e3b7d2
Create Date: 2026-09-18 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '15c062d170cd'
down_revision: Union[str, Sequence[str], None] = 'c1a9f0e3b7d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Уникальность по паре (storefront_request_id, product_id) — снимаем
    # старый unique-индекс (был unique=True на самом storefront_request_id),
    # создаём составной. Индекс просто на storefront_request_id (не unique)
    # оставляем — по нему всё ещё ищут заявку -> отзывы.
    op.drop_index('ix_reviews_storefront_request_id', table_name='reviews')
    op.create_index('ix_reviews_storefront_request_id', 'reviews', ['storefront_request_id'])
    op.create_unique_constraint(
        'uq_reviews_request_product', 'reviews', ['storefront_request_id', 'product_id']
    )

    # 2. Несколько фото + 3. Теги — JSONB, не JSON: публичный список считает
    # агрегаты (with_photos_count, счётчик по тегам) SQL-функциями по
    # содержимому массива (jsonb_array_length/jsonb_array_elements_text),
    # которых у обычного json нет.
    op.add_column('reviews', sa.Column('photos', JSONB, nullable=False, server_default='[]'))
    op.add_column('reviews', sa.Column('tags', JSONB, nullable=False, server_default='[]'))
    # существующие отзывы с одиночным photo получают photos=[photo] сразу —
    # иначе ReviewMapper.to_entity().normalize_photos() и так подставит его
    # на чтении, но публичные SQL-агрегаты (with_photos_count, лента фото)
    # читают колонку photos напрямую и не проходят через mapper/entity.
    op.execute(
        """
        UPDATE reviews SET photos = jsonb_build_array(photo)
        WHERE photo != '' AND (photos IS NULL OR photos = '[]'::jsonb)
        """
    )

    # 2. review_uploads — фото, загруженные покупателем до/для отзыва.
    op.create_table(
        'review_uploads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_review_uploads_customer_id', 'review_uploads', ['customer_id'])
    op.create_index('ix_review_uploads_url', 'review_uploads', ['url'])

    # 4. review_votes — «полезно/не полезно», один голос на покупателя на отзыв.
    op.create_table(
        'review_votes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('review_id', sa.Integer(), sa.ForeignKey('reviews.id'), nullable=False),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=False),
        sa.Column('value', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('review_id', 'customer_id', name='uq_review_votes_review_customer'),
    )
    op.create_index('ix_review_votes_tenant_id', 'review_votes', ['tenant_id'])
    op.create_index('ix_review_votes_review_id', 'review_votes', ['review_id'])
    op.create_index('ix_review_votes_customer_id', 'review_votes', ['customer_id'])


def downgrade() -> None:
    op.drop_index('ix_review_votes_customer_id', table_name='review_votes')
    op.drop_index('ix_review_votes_review_id', table_name='review_votes')
    op.drop_index('ix_review_votes_tenant_id', table_name='review_votes')
    op.drop_table('review_votes')

    op.drop_index('ix_review_uploads_url', table_name='review_uploads')
    op.drop_index('ix_review_uploads_customer_id', table_name='review_uploads')
    op.drop_table('review_uploads')

    op.drop_column('reviews', 'tags')
    op.drop_column('reviews', 'photos')

    op.drop_constraint('uq_reviews_request_product', 'reviews', type_='unique')
    op.drop_index('ix_reviews_storefront_request_id', table_name='reviews')
    op.create_index(
        'ix_reviews_storefront_request_id', 'reviews', ['storefront_request_id'], unique=True
    )
