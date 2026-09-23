"""pg_trgm расширение (промпт B4 п.2) — похожесть названий товаров для добора
похожих товаров маркетплейса, когда совпадений по категории меньше limit.

Revision ID: a3f8c1d9e0b4
Revises: 15c062d170cd
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.exc import DBAPIError


# revision identifiers, used by Alembic.
revision: str = 'a3f8c1d9e0b4'
down_revision: Union[str, Sequence[str], None] = '15c062d170cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # На managed Postgres роль приложения обычно не суперпользователь и не может
    # создавать расширения — тогда CREATE EXTENSION падает InsufficientPrivilege.
    # Оборачиваем в SAVEPOINT (nested transaction) и глотаем ошибку: без pg_trgm
    # похожие товары маркетплейса просто используют ILIKE-фолбэк (см.
    # list_similar_cross_shop), миграция не должна валить деплой из-за этого.
    connection = op.get_bind()
    nested = connection.begin_nested()
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        nested.commit()
    except DBAPIError:
        nested.rollback()


def downgrade() -> None:
    # Не роняем downgrade, если расширения не было (например, не было прав на upgrade).
    connection = op.get_bind()
    nested = connection.begin_nested()
    try:
        op.execute("DROP EXTENSION IF EXISTS pg_trgm")
        nested.commit()
    except DBAPIError:
        nested.rollback()
