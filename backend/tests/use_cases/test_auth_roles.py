from decimal import Decimal
import pytest
from app.application.analytics.dashboard import GetDashboardUseCase
from app.application.analytics.dead_stock import (
    DeadStockQuery,
    GetDeadStockUseCase,
    GetStockValueUseCase,
)
from app.application.auth.create_employee import CreateEmployeeCommand, CreateEmployeeUseCase
from app.application.auth.update_employee import UpdateEmployeeCommand, UpdateEmployeeUseCase
from app.application.inventory.common import LineInput
from app.application.inventory.create_warehouse import (
    CreateWarehouseCommand,
    CreateWarehouseUseCase,
)
from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.sales.create_sale import (
    CreateSaleCommand,
    CreateSaleUseCase,
    SaleItemInput,
)
from app.domain.common.exceptions import (
    AccessDeniedError,
    ClientHasDebtError,
    DomainError,
    InsufficientStockError,
    NotFoundError,
)
from app.domain.common.money import Money
from app.domain.identity.entities import Role, Warehouse
from app.domain.identity.permissions import Actor
from app.domain.sales.payment import PaymentMethod


async def test_create_employee_auto_assigns_single_warehouse(
    make_uow, hasher, registered_shop, warehouse_id, random_phone
):
    """Магазин с одним складом: seller/manager/storekeeper привязываются к нему
    автоматически, даже если фронт не прислал warehouse_ids."""
    tenant_id, _, owner = registered_shop

    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )

    async with make_uow(tenant_id) as uow:
        warehouses = await uow.warehouses.list_for_user(seller.id)
    assert [w.id for w in warehouses] == [warehouse_id]


async def test_create_employee_requires_warehouse_when_multiple_exist(
    make_uow, hasher, registered_shop, warehouse_id, random_phone
):
    """Как только у магазина больше одного склада, для seller/manager/storekeeper
    нужно явно выбрать хотя бы один — иначе DomainError."""
    tenant_id, _, owner = registered_shop
    second = await CreateWarehouseUseCase(make_uow(tenant_id)).execute(
        owner, CreateWarehouseCommand(name="Склад Б")
    )

    with pytest.raises(DomainError):
        await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
            owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
        )

    # с явным списком — успех, и в списке ровно переданные склады
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner,
        CreateEmployeeCommand(
            "Зара", random_phone(), "secret123", Role.SELLER,
            warehouse_ids=[warehouse_id, second.id],
        ),
    )
    async with make_uow(tenant_id) as uow:
        assigned = {w.id for w in await uow.warehouses.list_for_user(seller.id)}
    assert assigned == {warehouse_id, second.id}


async def test_create_employee_rejects_foreign_warehouse(
    make_uow, hasher, registered_shop, random_phone
):
    tenant_id, _, owner = registered_shop
    await CreateWarehouseUseCase(make_uow(tenant_id)).execute(
        owner, CreateWarehouseCommand(name="Склад Б")
    )
    with pytest.raises(DomainError):
        await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
            owner,
            CreateEmployeeCommand(
                "Зара", random_phone(), "secret123", Role.SELLER, warehouse_ids=[999999],
            ),
        )


async def test_manager_and_seller_are_limited_to_their_warehouses(
    make_uow, hasher, registered_shop, warehouse_id, create_product, random_phone
):
    """Продавец, привязанный только к одному из двух складов, не может продавать
    и не видит продажи с чужого склада — новое правило из ТЗ (ранее только для storekeeper)."""
    tenant_id, _, owner = registered_shop
    second = await CreateWarehouseUseCase(make_uow(tenant_id)).execute(
        owner, CreateWarehouseCommand(name="Склад Б")
    )
    product = await create_product(tenant_id, name="Товар")

    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner,
        CreateEmployeeCommand(
            "Зара", random_phone(), "secret123", Role.SELLER, warehouse_ids=[warehouse_id],
        ),
    )
    async with make_uow(tenant_id) as uow:
        seller_warehouse_ids = [w.id for w in await uow.warehouses.list_for_user(seller.id)]
    seller_actor = Actor(id=seller.id, role=seller.role, warehouse_ids=seller_warehouse_ids)

    for wid in (warehouse_id, second.id):
        await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
            owner,
            ReceiveGoodsCommand(
                warehouse_id=wid,
                lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
            ),
        )

    # продажа со своего склада — можно
    await CreateSaleUseCase(make_uow(tenant_id)).execute(
        seller_actor,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("100"))],
        ),
    )

    # продажа с чужого (не назначенного) склада — запрещена
    with pytest.raises(AccessDeniedError):
        await CreateSaleUseCase(make_uow(tenant_id)).execute(
            seller_actor,
            CreateSaleCommand(
                warehouse_id=second.id,
                payment_method=PaymentMethod.CASH,
                items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("100"))],
            ),
        )


async def test_analytics_filtered_by_actor_warehouses(
    make_uow, hasher, registered_shop, warehouse_id, create_product, random_phone
):
    """Аналитика (dashboard/top-products/dead-stock/stock-value) считается только
    по складам, к которым привязан управляющий — новое правило из ТЗ."""
    tenant_id, _, owner = registered_shop
    second = await CreateWarehouseUseCase(make_uow(tenant_id)).execute(
        owner, CreateWarehouseCommand(name="Склад Б")
    )
    product = await create_product(
        tenant_id, name="Товар", purchase_price=Money.of("100"), retail_price=Money.of("200")
    )

    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"), cost=Decimal("100"))],
        ),
    )
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=second.id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"), cost=Decimal("100"))],
        ),
    )
    await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("200"))],
        ),
    )
    await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=second.id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("200"))],
        ),
    )

    manager = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner,
        CreateEmployeeCommand(
            "Умар", random_phone(), "secret123", Role.MANAGER, warehouse_ids=[warehouse_id],
        ),
    )
    manager_actor = Actor(id=manager.id, role=manager.role, warehouse_ids=[warehouse_id])

    # владелец видит обе продажи, управляющий — только свою (по своему складу)
    owner_dashboard = await GetDashboardUseCase(make_uow(tenant_id)).execute(owner)
    assert owner_dashboard.today.sales_count == 2

    manager_dashboard = await GetDashboardUseCase(make_uow(tenant_id)).execute(manager_actor)
    assert manager_dashboard.today.sales_count == 1
    assert manager_dashboard.today.revenue == Decimal("200")

    stock_value = await GetStockValueUseCase(make_uow(tenant_id)).execute(manager_actor)
    assert {item.product_id for item in stock_value} == {product.id}
    assert stock_value[0].quantity == Decimal("9")  # 10 принято - 1 продано на своём складе


async def test_update_employee_changes_role_and_warehouses(
    make_uow, hasher, registered_shop, warehouse_id, random_phone
):
    tenant_id, _, owner = registered_shop
    second = await CreateWarehouseUseCase(make_uow(tenant_id)).execute(
        owner, CreateWarehouseCommand(name="Склад Б")
    )
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner,
        CreateEmployeeCommand(
            "Зара", random_phone(), "secret123", Role.SELLER, warehouse_ids=[warehouse_id],
        ),
    )

    updated = await UpdateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner,
        UpdateEmployeeCommand(
            user_id=seller.id, name="Зара Х.", role=Role.SELLER, is_active=True,
            warehouse_ids=[second.id],
        ),
    )
    assert updated.name == "Зара Х."

    async with make_uow(tenant_id) as uow:
        assigned = {w.id for w in await uow.warehouses.list_for_user(seller.id)}
    assert assigned == {second.id}


async def test_update_employee_rejects_role_escalation_by_manager(
    make_uow, hasher, registered_shop, random_phone
):
    tenant_id, _, owner = registered_shop
    manager = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Умар", random_phone(), "secret123", Role.MANAGER)
    )
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )
    manager_actor = Actor(id=manager.id, role=manager.role)

    with pytest.raises(AccessDeniedError):
        await UpdateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
            manager_actor,
            UpdateEmployeeCommand(
                user_id=seller.id, name="Зара", role=Role.MANAGER, is_active=True,
            ),
        )
