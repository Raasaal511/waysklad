"""Индексы на родительский FK в строках документов.

Строки всегда читаются пачкой по родителю («покажи позиции этой продажи»),
но проиндексирован был только tenant_id — на каждый такой запрос шёл
seq scan. На деве это видно прямо в pg_stat_user_tables: у sale_lines
195k последовательных сканов и ни одного индексного. С ростом числа продаж
страница продажи и аналитика деградируют линейно.

Revision ID: b3c7d2f1e846
Revises: a1b4e7c2d508
Create Date: 2026-10-04
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b3c7d2f1e846"
down_revision: Union[str, Sequence[str], None] = "a1b4e7c2d508"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (таблица, колонка) — родитель, по которому строки читаются пачкой
_LINES = (
    ("sale_lines", "sale_id"),
    ("storefront_request_lines", "request_id"),
    ("stock_document_lines", "document_id"),
)


def upgrade() -> None:
    for table, column in _LINES:
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    for table, column in _LINES:
        op.drop_index(f"ix_{table}_{column}", table_name=table)
