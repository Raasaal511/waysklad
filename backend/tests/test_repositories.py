import asyncio
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Product, ProductVariant
from app.domain.common.exceptions import DomainError, NotFoundError
from app.domain.common.money import Money
from app.domain.common.phone import Phone
from app.domain.common.quantity import UNITS, Quantity
from app.domain.counterparties.entities import Client, Supplier
from app.domain.debts.entities import Debt, InstallmentPayment
from app.domain.identity.entities import Role, Warehouse
from app.domain.orders.entities import Order, OrderLine, OrderStatus
from app.domain.sales.entities import Sale, SaleLine
from app.domain.sales.payment import PaymentMethod
from app.infrastructure.db.models.catalog import UnitModel


async def test_shop_registration_seeds_units_and_login_works(make_uow, create_shop):
    tenant_id, phone, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        user = await uow.users.get_by_phone(phone)
        assert user is not None
        assert user.tenant_id == tenant_id
        assert user.role is Role.OWNER

        units = await uow.session.get(UnitModel, 1)
        assert units is not None  # предустановленные единицы посеяны


async def test_product_roundtrip_and_barcode_search(make_uow, create_shop):
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        product = Product(
            id=None,
            name="Платье вечернее",
            unit=UNITS["pcs"],
            purchase_price=Money.of("1200"),
            retail_price=Money.of("2500"),
            barcode=Barcode("4600000000017"),
            variants=[
                ProductVariant(id=None, size="M", color="чёрный", barcode=Barcode("4600000000024"))
            ],
        )
        await uow.products.add(product)
        await uow.commit()
        product_id = product.id

    async with make_uow(tenant_id) as uow:
        loaded = await uow.products.get(product_id)
        assert loaded.retail_price == Money.of("2500")
        assert loaded.margin == Money.of("1300")
        assert loaded.variants[0].size == "M"

        by_variant = await uow.products.get_by_barcode(Barcode("4600000000024"))
        assert by_variant is not None and by_variant.id == product_id

        found, total = await uow.products.search("плать")
        assert [p.id for p in found] == [product_id]
        assert total == 1


async def test_product_save_syncs_variants(make_uow, create_shop):
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        product = Product(
            id=None,
            name="Платье",
            unit=UNITS["pcs"],
            purchase_price=Money.of("1000"),
            retail_price=Money.of("2000"),
            variants=[ProductVariant(id=None, size="M", color="чёрный")],
        )
        await uow.products.add(product)
        await uow.commit()
        product_id = product.id
        variant_id = product.variants[0].id

    # переименование + смена цвета существующего варианта + добавление нового
    async with make_uow(tenant_id) as uow:
        loaded = await uow.products.get(product_id)
        loaded.name = "Платье вечернее"
        loaded.variants = [
            ProductVariant(id=variant_id, size="M", color="изумрудный"),
            ProductVariant(id=None, size="L", color="изумрудный"),
        ]
        await uow.products.save(loaded)
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        reloaded = await uow.products.get(product_id)
        assert reloaded.name == "Платье вечернее"
        assert len(reloaded.variants) == 2
        assert {v.color for v in reloaded.variants} == {"изумрудный"}

    # убираем размер M — старый вариант должен удалиться (delete-orphan), не просто отвязаться
    async with make_uow(tenant_id) as uow:
        loaded = await uow.products.get(product_id)
        loaded.variants = [v for v in loaded.variants if v.size == "L"]
        await uow.products.save(loaded)
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        final = await uow.products.get(product_id)
        assert [v.size for v in final.variants] == ["L"]


async def test_stock_change_accumulates(make_uow, create_shop, create_product):
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        warehouse = await uow.warehouses.add(Warehouse(id=None, name="Основной"))
        await uow.commit()
        warehouse_id = warehouse.id

    product = await create_product(
        tenant_id, name="Мёд горный", unit=UNITS["kg"],
        purchase_price=Money.of("400"), retail_price=Money.of("700"),
    )

    async with make_uow(tenant_id) as uow:
        await uow.stock.change(product.id, warehouse_id, Decimal("10.5"))
        quantity = await uow.stock.change(product.id, warehouse_id, Decimal("-3"))
        assert quantity == Decimal("7.5")
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("7.5")
        await uow.commit()


async def test_stock_reserve_and_release(make_uow, create_shop, create_product):
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        warehouse = await uow.warehouses.add(Warehouse(id=None, name="Основной"))
        await uow.commit()
        warehouse_id = warehouse.id

    product = await create_product(tenant_id, name="Платье")

    async with make_uow(tenant_id) as uow:
        await uow.stock.change(product.id, warehouse_id, Decimal("5"))
        reserved = await uow.stock.reserve(product.id, warehouse_id, Decimal("2"))
        assert reserved == Decimal("2")
        assert await uow.stock.get_reserved(product.id, warehouse_id) == Decimal("2")
        # физический остаток не тронут резервом
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("5")

        released = await uow.stock.reserve(product.id, warehouse_id, Decimal("-2"))
        assert released == Decimal("0")
        assert await uow.stock.get_reserved(product.id, warehouse_id) == Decimal("0")
        await uow.commit()


async def test_stock_change_concurrent_first_write_no_duplicate_row(
    make_uow, create_shop, create_product
):
    # первая операция над товаром/складом создаёт строку остатка — если два
    # запроса делают это одновременно (например, две приёмки на разные склады
    # сразу после заведения товара), второй INSERT бьётся об уникальный индекс;
    # без savepoint-фикса это IntegrityError наружу вместо применения остатка
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        warehouse = await uow.warehouses.add(Warehouse(id=None, name="Основной"))
        await uow.commit()
        warehouse_id = warehouse.id

    product = await create_product(tenant_id, name="Товар гонка")

    async def change_in_own_transaction(delta: Decimal) -> Decimal:
        async with make_uow(tenant_id) as uow:
            quantity = await uow.stock.change(product.id, warehouse_id, delta)
            await uow.commit()
            return quantity

    results = await asyncio.gather(
        change_in_own_transaction(Decimal("5")),
        change_in_own_transaction(Decimal("3")),
    )
    # порядок, в котором две конкурентные транзакции создают строку, не детерминирован —
    # важно лишь то, что обе дельты применились ровно по разу (сумма = 8), без дубля строки
    assert sorted(results) == [Decimal("3"), Decimal("8")] or sorted(results) == [Decimal("5"), Decimal("8")]

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("8")


async def test_stock_change_concurrent_decrement_serializes_not_races(
    make_uow, create_shop, create_product
):
    # два продавца одновременно продают последнюю единицу товара: SELECT FOR
    # UPDATE должен сериализовать списания, а не допустить, чтобы оба прочитали
    # один и тот же остаток и оба списали независимо (потерянное обновление)
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        warehouse = await uow.warehouses.add(Warehouse(id=None, name="Основной"))
        await uow.commit()
        warehouse_id = warehouse.id

    product = await create_product(tenant_id, name="Товар последний")

    async with make_uow(tenant_id) as uow:
        await uow.stock.change(product.id, warehouse_id, Decimal("1"))
        await uow.commit()

    async def sell_one() -> Decimal:
        async with make_uow(tenant_id) as uow:
            quantity = await uow.stock.change(product.id, warehouse_id, Decimal("-1"))
            await uow.commit()
            return quantity

    results = await asyncio.gather(sell_one(), sell_one())
    assert sorted(results) == [Decimal("-1"), Decimal("0")]

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("-1")


async def test_tenant_isolation(make_uow, create_shop, create_product):
    tenant_a, _, _ = await create_shop()
    tenant_b, _, _ = await create_shop()

    product = await create_product(
        tenant_a, name="Цемент М500", unit=UNITS["bag"],
        purchase_price=Money.of("350"), retail_price=Money.of("450"),
    )

    async with make_uow(tenant_b) as uow:
        with pytest.raises(NotFoundError):
            await uow.products.get(product.id)
        found, total = await uow.products.search("Цемент")
        assert found == [] and total == 0


async def test_warehouse_assignment_scoped_to_tenant(make_uow, create_shop):
    # WarehouseAssignmentModel — чисто связующая таблица, у неё физически нет
    # tenant_id; изоляция держится на явном JOIN на WarehouseModel.tenant_id
    # в репозитории. Проверяем, что чужой склад не получится ни назначить, ни
    # прочитать назначения через методы, которые раньше не фильтровали tenant.
    tenant_a, _, owner_a = await create_shop()
    tenant_b, _, _ = await create_shop()

    async with make_uow(tenant_b) as uow:
        foreign_warehouse = await uow.warehouses.add(Warehouse(id=None, name="Чужой склад"))
        await uow.commit()
        foreign_warehouse_id = foreign_warehouse.id

    async with make_uow(tenant_a) as uow:
        with pytest.raises(NotFoundError):
            await uow.warehouses.set_assignments(foreign_warehouse_id, [owner_a])

        with pytest.raises(NotFoundError):
            await uow.warehouses.add_assignment(foreign_warehouse_id, owner_a)

        assert await uow.warehouses.is_assigned(foreign_warehouse_id, owner_a) is False

        # id чужого склада в списке — тихо игнорируется, не создаёт назначение
        await uow.warehouses.set_user_assignments(owner_a, [foreign_warehouse_id])
        await uow.commit()
        assert await uow.warehouses.list_for_user(owner_a) == []


async def test_sale_roundtrip(make_uow, create_shop, create_product):
    tenant_id, _, seller_id = await create_shop()
    product = await create_product(tenant_id, name="Духи масляные 6мл")

    async with make_uow(tenant_id) as uow:
        warehouse = await uow.warehouses.add(Warehouse(id=None, name="Точка"))

        sale = Sale(
            id=None,
            warehouse_id=warehouse.id,
            seller_id=seller_id,
            payment_method=PaymentMethod.CASH,
            lines=[
                SaleLine(
                    product_id=product.id,
                    quantity=Quantity(Decimal("2"), UNITS["pcs"]),
                    price=Money.of("250"),
                )
            ],
        )
        sale.validate()
        await uow.sales.add(sale)
        await uow.commit()
        sale_id = sale.id

    async with make_uow(tenant_id) as uow:
        loaded = await uow.sales.get(sale_id)
        assert loaded.total == Money.of("500")
        assert loaded.payment_method is PaymentMethod.CASH
        assert loaded.lines[0].quantity.unit.code == "pcs"


async def test_debt_with_installments(make_uow, create_shop):
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        client = await uow.clients.add(Client(id=None, name="Ахмед", phone=Phone("+79280000001")))
        debt = Debt(
            id=None,
            client_id=client.id,
            amount=Money.of("3500"),
            issued_at=date.today(),
            due_date=date.today() + timedelta(days=30),
            schedule=[
                InstallmentPayment(date.today() + timedelta(days=7), Money.of("1750")),
                InstallmentPayment(date.today() + timedelta(days=14), Money.of("1750")),
            ],
        )
        await uow.debts.add(debt)
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        debts = await uow.debts.list_by_client(client.id)
        assert len(debts) == 1
        assert debts[0].balance == Money.of("3500")
        assert not debts[0].is_closed
        assert len(debts[0].schedule) == 2

        due = await uow.debts.list_due(date.today() + timedelta(days=30))
        assert [d.id for d in due] == [debts[0].id]


async def test_debt_save_appends_repayment_and_replaces_schedule(make_uow, create_shop):
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        client = await uow.clients.add(Client(id=None, name="Тамара", phone=Phone("+79280009988")))
        debt = await uow.debts.add(
            Debt(id=None, client_id=client.id, amount=Money.of("1000"), issued_at=date.today())
        )
        await uow.commit()
        debt_id = debt.id

    async with make_uow(tenant_id) as uow:
        debt = await uow.debts.get(debt_id)
        debt.repay(Money.of("400"), on=date.today())
        await uow.debts.save(debt)
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        debt = await uow.debts.get(debt_id)
        assert debt.balance == Money.of("600")
        assert len(debt.repayments) == 1

        debt.schedule = [InstallmentPayment(date.today() + timedelta(days=10), Money.of("600"))]
        await uow.debts.save(debt)
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        debt = await uow.debts.get(debt_id)
        assert len(debt.schedule) == 1
        assert len(debt.repayments) == 1  # погашения не пострадали от замены графика


async def test_order_save_updates_status_and_lines(make_uow, create_shop, create_product):
    tenant_id, _, _ = await create_shop()
    product = await create_product(tenant_id, name="Торт на заказ")

    async with make_uow(tenant_id) as uow:
        warehouse = await uow.warehouses.add(Warehouse(id=None, name="Склад"))
        client = await uow.clients.add(Client(id=None, name="Милана"))
        order = await uow.orders.add(
            Order(
                id=None,
                client_id=client.id,
                warehouse_id=warehouse.id,
                lines=[
                    OrderLine(
                        product_id=product.id,
                        quantity=Quantity(Decimal("1"), UNITS["pcs"]),
                        price=Money.of("3000"),
                    )
                ],
                due_date=date.today(),
            )
        )
        await uow.commit()
        order_id = order.id

    async with make_uow(tenant_id) as uow:
        order = await uow.orders.get(order_id)
        order.change_status(OrderStatus.IN_PROGRESS)
        order.note = "готовим"
        order.lines = [
            OrderLine(
                product_id=product.id,
                quantity=Quantity(Decimal("2"), UNITS["pcs"]),
                price=Money.of("3000"),
            )
        ]
        await uow.orders.save(order)
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        order = await uow.orders.get(order_id)
        assert order.status is OrderStatus.IN_PROGRESS
        assert order.note == "готовим"
        assert len(order.lines) == 1
        assert order.lines[0].quantity.value == Decimal("2")  # save() теперь заменяет состав


async def test_supplier_roundtrip(make_uow, create_shop):
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        await uow.suppliers.add(
            Supplier(id=None, name="Оптовая база Беркат", contact="+79280000002")
        )
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        suppliers = await uow.suppliers.list()
        assert [s.name for s in suppliers] == ["Оптовая база Беркат"]


async def test_client_search_and_debt_limit_persists(make_uow, create_shop):
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        await uow.clients.add(
            Client(id=None, name="Ахмед", phone=Phone("+79280001122"), debt_limit=Money.of("5000"))
        )
        await uow.clients.add(Client(id=None, name="Милана", phone=Phone("+79280003344")))
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        found = await uow.clients.search("+79280001")
        assert len(found) == 1
        assert found[0].name == "Ахмед"
        assert found[0].debt_limit == Money.of("5000")

        milana = await uow.clients.search("Милана")
        assert milana[0].debt_limit is None


async def test_debts_list_filtered_status_query_and_pagination(make_uow, create_shop):
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        ahmed = await uow.clients.add(Client(id=None, name="Ахмед", phone=Phone("+79280005511")))
        milana = await uow.clients.add(Client(id=None, name="Милана", phone=Phone("+79280005522")))
        # просроченный долг Ахмеда — остаток есть, срок в прошлом
        overdue_debt = await uow.debts.add(
            Debt(
                id=None, client_id=ahmed.id, amount=Money.of("1000"), issued_at=date.today(),
                due_date=date.today() - timedelta(days=5),
            )
        )
        # активный долг Миланы — остаток есть, срок далеко
        await uow.debts.add(
            Debt(
                id=None, client_id=milana.id, amount=Money.of("2000"), issued_at=date.today(),
                due_date=date.today() + timedelta(days=60),
            )
        )
        # закрытый долг Ахмеда — погашен полностью
        closed_debt = await uow.debts.add(
            Debt(id=None, client_id=ahmed.id, amount=Money.of("500"), issued_at=date.today())
        )
        await uow.commit()
        closed_debt.repay(Money.of("500"), on=date.today())
        await uow.debts.save(closed_debt)
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        # active-запрос (balance__gt=0) не должен вернуть закрытый долг
        debts, total = await uow.debts.list_filtered({"balance__gt": 0})
        assert total == 2
        assert closed_debt.id not in {d.id for d in debts}

        # closed-запрос видит только погашенный
        closed_only, closed_total = await uow.debts.list_filtered({"balance__lte": 0})
        assert closed_total == 1
        assert [d.id for d in closed_only] == [closed_debt.id]

        # фильтр по статусу overdue
        overdue_only, overdue_total = await uow.debts.list_filtered(
            {"balance__gt": 0, "status": "overdue"}
        )
        assert overdue_total == 1
        assert overdue_only[0].id == overdue_debt.id

        # поиск по имени контрагента
        by_name, by_name_total = await uow.debts.list_filtered(
            {"balance__gt": 0, "counterparty_name__ilike": "Мила"}
        )
        assert by_name_total == 1
        assert by_name[0].client_id == milana.id

        # пагинация: limit=1 всё равно возвращает верный total
        page, page_total = await uow.debts.list_filtered({"balance__gt": 0, "limit": 1, "offset": 0})
        assert len(page) == 1
        assert page_total == 2

        # сортировка по severity (overdue выше active)
        sorted_debts, _ = await uow.debts.list_filtered({"balance__gt": 0, "order_by": "-severity"})
        assert sorted_debts[0].id == overdue_debt.id


async def test_debts_list_filtered_tenant_isolation(make_uow, create_shop):
    tenant_a, _, _ = await create_shop()
    tenant_b, _, _ = await create_shop()

    async with make_uow(tenant_a) as uow:
        client = await uow.clients.add(Client(id=None, name="Ахмед", phone=Phone("+79280006611")))
        await uow.debts.add(Debt(id=None, client_id=client.id, amount=Money.of("1000"), issued_at=date.today()))
        await uow.commit()

    async with make_uow(tenant_b) as uow:
        debts, total = await uow.debts.list_filtered({})
        assert debts == []
        assert total == 0


async def test_debts_list_filtered_rejects_unknown_field(make_uow, create_shop):
    tenant_id, _, _ = await create_shop()

    async with make_uow(tenant_id) as uow:
        with pytest.raises(DomainError):
            await uow.debts.list_filtered({"bogus_field": 1})
