"""Создать по одному демо-товару на каждую единицу измерения со средним остатком.

Запуск:
    docker compose exec backend python -m scripts.seed_units_demo --phone +79280000001
"""

import argparse
import asyncio
from decimal import Decimal

from app.application.inventory.common import LineInput
from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.products.create_product import CreateProductCommand, CreateProductUseCase
from app.domain.identity.permissions import Actor
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

# code, название товара, sku, средний остаток, закупка, розница
UNIT_PRODUCTS = [
    ("pcs", "Ручка шариковая", "UNT-PCS", "24", "15", "30"),
    ("kg", "Сахар весовой", "UNT-KG", "18.5", "55", "80"),
    ("g", "Ваниль молотая", "UNT-G", "250", "0.8", "1.5"),
    ("l", "Масло подсолнечное", "UNT-L", "12.5", "90", "140"),
    ("ml", "Эфирное масло лаванды", "UNT-ML", "300", "3", "6"),
    ("m", "Кабель электрический", "UNT-M", "45", "20", "35"),
    ("m2", "Линолеум", "UNT-M2", "16.5", "300", "450"),
    ("m3", "Песок строительный", "UNT-M3", "8.2", "800", "1200"),
    ("pack", "Салфетки бумажные", "UNT-PACK", "14", "60", "100"),
    ("bag", "Цемент", "UNT-BAG", "9", "350", "500"),
    ("roll", "Скотч упаковочный", "UNT-ROLL", "22", "40", "70"),
]


async def seed(phone: str) -> None:
    async with SqlAlchemyUnitOfWork(None) as uow:
        user = await uow.users.get_by_phone(phone)
        if user is None:
            raise SystemExit(f"Пользователь с телефоном {phone} не найден")
        tenant_id = user.tenant_id
        actor = Actor(id=user.id, role=user.role)

    print(f"Наполняю магазин tenant_id={tenant_id} (пользователь {phone})")

    def uow() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(tenant_id)

    async with uow() as u:
        warehouses = await u.warehouses.list()
    if not warehouses:
        raise SystemExit("В магазине нет складов — сначала создайте склад")
    warehouse = warehouses[0]

    for unit_code, name, sku, qty, purchase_price, retail_price in UNIT_PRODUCTS:
        product = await CreateProductUseCase(uow()).execute(
            actor,
            CreateProductCommand(
                name=name,
                unit_code=unit_code,
                sku=sku,
                purchase_price=Decimal(purchase_price),
                retail_price=Decimal(retail_price),
            ),
        )
        await ReceiveGoodsUseCase(uow()).execute(
            actor,
            ReceiveGoodsCommand(
                warehouse_id=warehouse.id,
                lines=[LineInput(product_id=product.id, quantity=Decimal(qty), cost=Decimal(purchase_price))],
            ),
        )
        print(f"  {name} ({unit_code}): остаток {qty} на складе «{warehouse.name}»")

    print("Готово.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", required=True, help="телефон владельца магазина")
    args = parser.parse_args()
    asyncio.run(seed(args.phone))
