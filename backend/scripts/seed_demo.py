"""Наполнить существующий магазин демо-данными: склады, товары, остатки,
продажи, долги, заказы, клиенты, поставщики.

Запуск:
    docker compose exec backend python -m scripts.seed_demo --phone +79280000001
"""

import argparse
import asyncio
from datetime import date, timedelta
from decimal import Decimal

from app.application.counterparties.create_client import (
    CreateClientCommand,
    CreateClientUseCase,
)
from app.application.counterparties.create_supplier import (
    CreateSupplierCommand,
    CreateSupplierUseCase,
)
from app.application.debts.issue_debt import IssueDebtCommand, IssueDebtUseCase
from app.application.inventory.common import LineInput
from app.application.inventory.create_warehouse import (
    CreateWarehouseCommand,
    CreateWarehouseUseCase,
)
from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.orders.create_order import (
    CreateOrderCommand,
    CreateOrderUseCase,
    OrderItemInput,
)
from app.application.products.create_product import CreateProductCommand, CreateProductUseCase
from app.application.sales.create_sale import (
    CreateSaleCommand,
    CreateSaleUseCase,
    SaleItemInput,
)
from app.domain.identity.permissions import Actor
from app.domain.sales.payment import PaymentMethod
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

PRODUCTS = [
    {"name": "Платье летнее", "sku": "PL-001", "purchase_price": "1500", "retail_price": "2900", "qty": "20"},
    {"name": "Джинсы классик", "sku": "DJ-002", "purchase_price": "1200", "retail_price": "2400", "qty": "15"},
    {"name": "Футболка базовая", "sku": "FB-003", "purchase_price": "350", "retail_price": "700", "qty": "40"},
    {"name": "Куртка утеплённая", "sku": "KU-004", "purchase_price": "3500", "retail_price": "6900", "qty": "8"},
    {"name": "Сумка кожаная", "sku": "SK-005", "purchase_price": "1800", "retail_price": "3500", "qty": "12"},
    {"name": "Кроссовки спорт", "sku": "KR-006", "purchase_price": "2200", "retail_price": "4200", "qty": "10"},
]

CLIENTS = [
    {"name": "Айна Магомедова", "phone": "+79280001111", "city": "Грозный", "debt_limit": "10000"},
    {"name": "Хава Ахмадова", "phone": "+79280002222", "city": "Гудермес"},
    {"name": "Ислам Юсупов", "phone": "+79280003333", "city": "Грозный"},
]

SUPPLIERS = [
    {"name": "База Беркат", "contact": "+79280009999"},
    {"name": "ОптТорг ЧР", "contact": "+79280008888"},
]


async def seed(phone: str) -> None:
    async with SqlAlchemyUnitOfWork(None) as uow:
        user = await uow.users.get_by_phone(phone)
        if user is None:
            raise SystemExit(f"Пользователь с телефоном {phone} не найден — сначала зарегистрируйте магазин")
        tenant_id = user.tenant_id
        actor = Actor(id=user.id, role=user.role)

    print(f"Наполняю магазин tenant_id={tenant_id} (пользователь {phone})")

    def uow() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(tenant_id)

    async with uow() as u:
        warehouses = await u.warehouses.list()
    main_warehouse = warehouses[0]

    second_warehouse = await CreateWarehouseUseCase(uow()).execute(
        actor, CreateWarehouseCommand(name="Склад на Кадырова", address="ул. Кадырова, 12")
    )
    print(f"Склады: {main_warehouse.name}, {second_warehouse.name}")

    products = []
    for item in PRODUCTS:
        product = await CreateProductUseCase(uow()).execute(
            actor,
            CreateProductCommand(
                name=item["name"], unit_code="pcs", sku=item["sku"],
                purchase_price=Decimal(item["purchase_price"]),
                retail_price=Decimal(item["retail_price"]),
            ),
        )
        products.append(product)
        await ReceiveGoodsUseCase(uow()).execute(
            actor,
            ReceiveGoodsCommand(
                warehouse_id=main_warehouse.id,
                lines=[LineInput(product_id=product.id, quantity=Decimal(item["qty"]),
                                  cost=Decimal(item["purchase_price"]))],
            ),
        )
    print(f"Товаров создано: {len(products)}, приёмка проведена")

    clients = []
    for c in CLIENTS:
        client = await CreateClientUseCase(uow()).execute(
            actor,
            CreateClientCommand(
                name=c["name"], phone=c.get("phone", ""), city=c.get("city", ""),
                debt_limit=Decimal(c["debt_limit"]) if "debt_limit" in c else None,
            ),
        )
        clients.append(client)
    print(f"Клиентов создано: {len(clients)}")

    for s in SUPPLIERS:
        await CreateSupplierUseCase(uow()).execute(
            actor, CreateSupplierCommand(name=s["name"], contact=s["contact"])
        )
    print(f"Поставщиков создано: {len(SUPPLIERS)}")

    sales_count = 0
    for i, product in enumerate(products[:4]):
        payment = PaymentMethod.CASH if i % 2 == 0 else PaymentMethod.TRANSFER
        await CreateSaleUseCase(uow()).execute(
            actor,
            CreateSaleCommand(
                warehouse_id=main_warehouse.id,
                payment_method=payment,
                items=[SaleItemInput(product_id=product.id, quantity=Decimal("2"),
                                      price=Decimal(PRODUCTS[i]["retail_price"]))],
            ),
        )
        sales_count += 1

    await CreateSaleUseCase(uow()).execute(
        actor,
        CreateSaleCommand(
            warehouse_id=main_warehouse.id,
            payment_method=PaymentMethod.CREDIT,
            client_id=clients[0].id,
            items=[SaleItemInput(product_id=products[0].id, quantity=Decimal("1"),
                                  price=Decimal(PRODUCTS[0]["retail_price"]))],
        ),
    )
    sales_count += 1
    print(f"Продаж проведено: {sales_count}")

    await IssueDebtUseCase(uow()).execute(
        actor,
        IssueDebtCommand(
            client_id=clients[1].id, amount=Decimal("1500"),
            due_date=date.today() + timedelta(days=3), note="записала долг за платье",
        ),
    )
    print("Долг выдан клиенту Хава Ахмадова")

    await CreateOrderUseCase(uow()).execute(
        actor,
        CreateOrderCommand(
            client_id=clients[2].id,
            items=[OrderItemInput(product_id=products[3].id, quantity=Decimal("1"),
                                   price=Decimal(PRODUCTS[3]["retail_price"]))],
            due_date=date.today() + timedelta(days=5),
            prepayment=Decimal("1000"),
            note="из директа, куртка на заказ",
        ),
    )
    print("Заказ создан для клиента Ислам Юсупов")

    print("Готово.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", required=True, help="телефон владельца магазина")
    args = parser.parse_args()
    asyncio.run(seed(args.phone))
