"""Услуги: вид позиции (товар/услуга), допы и единицы час/услуга/день/выезд.

1. products.kind — 'product' | 'service'. Услуга не отдельная таблица, а вид
   товара: иначе удвоились бы продажа, корзина, заказ с витрины и аналитика.
2. product_variants.addon — доп к услуге («+500 ₽»), складывается с ценой,
   в отличие от обычного варианта (размер S *или* M).
3. Единицы час / услуга / день / выезд.

Обе колонки с server_default, существующие строки остаются товарами —
деплой без простоя.

Про единицы: предустановленные копируются в таблицу units при регистрации
магазина (TenantRepository.add), а список для выпадающего списка в форме
товара читается только из этой таблицы. Значит магазинам, созданным до
появления новых единиц, они сами по себе не достанутся — досеиваем.

Вставляем только недостающие: у магазина может быть своя единица с таким
же кодом (справочник tenant-уровневый, UniqueConstraint на tenant_id+code).

Revision ID: d4f1a9c3b762
Revises: c8a2f6b4d913
Create Date: 2026-10-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4f1a9c3b762"
down_revision: Union[str, Sequence[str], None] = "c8a2f6b4d913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# код, название, дробная ли — то же, что в app.domain.common.quantity.UNITS
_SERVICE_UNITS = (
    ("hour", "час", True),  # «полтора часа» — обычный случай
    ("service", "услуга", False),
    ("day", "день", False),
    ("visit", "выезд", False),
)


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="product"),
    )
    op.add_column(
        "product_variants",
        sa.Column("addon", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    for code, name, fractional in _SERVICE_UNITS:
        op.execute(
            f"""
            INSERT INTO units (tenant_id, code, name, fractional)
            SELECT t.id, '{code}', '{name}', {str(fractional).lower()}
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM units u WHERE u.tenant_id = t.id AND u.code = '{code}'
            )
            """
        )


def downgrade() -> None:
    op.drop_column("product_variants", "addon")
    op.drop_column("products", "kind")

    # удаляем только единицы, которыми никто не пользуется: товар с такой
    # единицей остался бы со ссылкой в никуда
    codes = ", ".join(f"'{code}'" for code, _, _ in _SERVICE_UNITS)
    op.execute(
        f"""
        DELETE FROM units u
        WHERE u.code IN ({codes})
          AND NOT EXISTS (
              SELECT 1 FROM products p
              WHERE p.tenant_id = u.tenant_id AND p.unit_code = u.code
          )
        """
    )
