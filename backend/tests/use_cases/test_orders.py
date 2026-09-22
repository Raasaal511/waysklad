from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from app.application.analytics.dashboard import GetDashboardUseCase
from app.application.auth.create_employee import CreateEmployeeCommand, CreateEmployeeUseCase
from app.application.counterparties.create_client import (
    CreateClientCommand,
    CreateClientUseCase,
)
from app.application.counterparties.create_supplier import (
    CreateSupplierCommand,
    CreateSupplierUseCase,
)
from app.application.inventory.common import LineInput
from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.inventory.set_warehouse_assignments import (
    SetWarehouseAssignmentsCommand,
    SetWarehouseAssignmentsUseCase,
)
from app.application.orders.cancel_order import CancelOrderCommand, CancelOrderUseCase
from app.application.orders.change_status import (
    ChangeOrderStatusCommand,
    ChangeOrderStatusUseCase,
)
from app.application.orders.create_order import (
    CreateOrderCommand,
    CreateOrderUseCase,
    OrderItemInput,
)
from app.application.orders.issue_order import IssueOrderCommand, IssueOrderUseCase
from app.application.orders.update_order import UpdateOrderCommand, UpdateOrderUseCase
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
from app.domain.orders.entities import OrderStatus
from app.domain.sales.payment import PaymentMethod


async def test_storekeeper_cannot_create_sale_but_can_receive_goods(
    make_uow, hasher, registered_shop, warehouse_id, create_product, random_phone
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Мешок цемента")
    storekeeper = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Руслан", random_phone(), "secret123", Role.STOREKEEPER)
    )
    storekeeper_actor = Actor(id=storekeeper.id, role=storekeeper.role)

    await SetWarehouseAssignmentsUseCase(make_uow(tenant_id)).execute(
        owner,
        SetWarehouseAssignmentsCommand(warehouse_id=warehouse_id, user_ids=[storekeeper.id]),
    )

    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        storekeeper_actor,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("30"))],
        ),
    )

    with pytest.raises(AccessDeniedError):
        await CreateSaleUseCase(make_uow(tenant_id)).execute(
            storekeeper_actor,
            CreateSaleCommand(
                warehouse_id=warehouse_id,
                payment_method=PaymentMethod.CASH,
                items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("500"))],
            ),
        )


async def test_create_supplier_and_search_clients_use_cases(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    await CreateSupplierUseCase(make_uow(tenant_id)).execute(
        owner, CreateSupplierCommand(name="База Беркат", contact="+79280000009")
    )
    await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Хава", phone="+79280005566")
    )

    async with make_uow(tenant_id) as uow:
        suppliers = await uow.suppliers.list()
        assert suppliers[0].name == "База Беркат"
        clients = await uow.clients.search("Хава")
        assert str(clients[0].phone) == "+79280005566"


async def test_order_lifecycle(make_uow, registered_shop, warehouse_id, create_product):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Торт на заказ", retail_price=Money.of("3000"))
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("1"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Милана")
    )

    order = await CreateOrderUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateOrderCommand(
            client_id=client.id,
            warehouse_id=warehouse_id,
            items=[OrderItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("3000"))],
            due_date=date.today() + timedelta(days=3),
            prepayment=Decimal("1000"),
            note="из директа, надпись «С юбилеем»",
        ),
    )
    assert order.to_pay == Money.of("2000")

    async with make_uow(tenant_id) as uow:
        # создание заказа резервирует остаток
        assert await uow.stock.get_reserved(product.id, warehouse_id) == Decimal("1")

    order = await ChangeOrderStatusUseCase(make_uow(tenant_id)).execute(
        owner, ChangeOrderStatusCommand(order.id, OrderStatus.IN_PROGRESS)
    )
    assert order.status is OrderStatus.IN_PROGRESS

    # выдача — не смена статуса, а отдельный сценарий (IssueOrderUseCase)
    with pytest.raises(DomainError):
        await ChangeOrderStatusUseCase(make_uow(tenant_id)).execute(
            owner, ChangeOrderStatusCommand(order.id, OrderStatus.ISSUED)
        )


async def test_order_reservation_blocks_sale_of_reserved_stock(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Платье", retail_price=Money.of("250"))
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("3"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Хава")
    )
    await CreateOrderUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateOrderCommand(
            client_id=client.id,
            warehouse_id=warehouse_id,
            items=[OrderItemInput(product_id=product.id, quantity=Decimal("3"), price=Decimal("250"))],
            due_date=date.today(),
        ),
    )

    # весь остаток зарезервирован под заказ — обычная продажа не пройдёт
    with pytest.raises(InsufficientStockError):
        await CreateSaleUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateSaleCommand(
                warehouse_id=warehouse_id,
                payment_method=PaymentMethod.CASH,
                items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("250"))],
            ),
        )


async def test_order_cancel_releases_reservation(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Платье", retail_price=Money.of("250"))
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("2"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Хава")
    )
    order = await CreateOrderUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateOrderCommand(
            client_id=client.id,
            warehouse_id=warehouse_id,
            items=[OrderItemInput(product_id=product.id, quantity=Decimal("2"), price=Decimal("250"))],
            due_date=date.today(),
        ),
    )

    order = await CancelOrderUseCase(make_uow(tenant_id)).execute(
        owner, CancelOrderCommand(order_id=order.id, reason="передумал")
    )
    assert order.status is OrderStatus.CANCELLED

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get_reserved(product.id, warehouse_id) == Decimal("0")

    # повторная отмена уже отменённого заказа — ошибка
    with pytest.raises(DomainError):
        await CancelOrderUseCase(make_uow(tenant_id)).execute(
            owner, CancelOrderCommand(order_id=order.id)
        )

    # остаток снова свободно продаётся
    await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("2"), price=Decimal("250"))],
        ),
    )


async def test_order_update_recalculates_reservation(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Платье", retail_price=Money.of("250"))
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Хава")
    )
    order = await CreateOrderUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateOrderCommand(
            client_id=client.id,
            warehouse_id=warehouse_id,
            items=[OrderItemInput(product_id=product.id, quantity=Decimal("2"), price=Decimal("250"))],
            due_date=date.today(),
        ),
    )

    order = await UpdateOrderUseCase(make_uow(tenant_id)).execute(
        owner,
        UpdateOrderCommand(
            order_id=order.id,
            client_id=client.id,
            warehouse_id=warehouse_id,
            items=[OrderItemInput(product_id=product.id, quantity=Decimal("4"), price=Decimal("250"))],
            due_date=date.today(),
        ),
    )
    assert order.total == Money.of("1000")

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get_reserved(product.id, warehouse_id) == Decimal("4")

    # правка сверх остатка — InsufficientStockError, старый резерв не пострадал (откат)
    with pytest.raises(InsufficientStockError):
        await UpdateOrderUseCase(make_uow(tenant_id)).execute(
            owner,
            UpdateOrderCommand(
                order_id=order.id,
                client_id=client.id,
                warehouse_id=warehouse_id,
                items=[
                    OrderItemInput(product_id=product.id, quantity=Decimal("10"), price=Decimal("250"))
                ],
            ),
        )

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get_reserved(product.id, warehouse_id) == Decimal("4")


async def test_order_issue_creates_sale_and_settles_debt(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(
        tenant_id, name="Торт на заказ", purchase_price=Money.of("1200"), retail_price=Money.of("3000")
    )
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("1"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Милана", debt_limit=Decimal("5000"))
    )
    order = await CreateOrderUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateOrderCommand(
            client_id=client.id,
            warehouse_id=warehouse_id,
            items=[OrderItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("3000"))],
            due_date=date.today(),
            prepayment=Decimal("1000"),
        ),
    )

    # выдать нельзя, пока заказ не «готов»
    with pytest.raises(DomainError):
        await IssueOrderUseCase(make_uow(tenant_id)).execute(
            owner,
            IssueOrderCommand(order_id=order.id, payment_method=PaymentMethod.CASH),
        )

    await ChangeOrderStatusUseCase(make_uow(tenant_id)).execute(
        owner, ChangeOrderStatusCommand(order.id, OrderStatus.READY)
    )

    result = await IssueOrderUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueOrderCommand(
            order_id=order.id,
            payment_method=PaymentMethod.CREDIT,
            debt_due_date=date.today() + timedelta(days=5),
            paid_now=Decimal("500"),
        ),
    )
    assert result.sale.total == Money.of("2000")  # доплата (3000 - 1000), не полная сумма
    assert result.sale.paid_now == Money.of("500")
    assert result.sale.debt_amount == Money.of("1500")
    assert result.order.status is OrderStatus.ISSUED
    assert result.order.sale_id == result.sale.id
    assert result.sale.order_id == order.id

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("0")
        assert await uow.stock.get_reserved(product.id, warehouse_id) == Decimal("0")
        debts = await uow.debts.list_by_client(client.id)
        assert len(debts) == 1
        assert debts[0].balance == Money.of("1500")
        assert debts[0].sale_id == result.sale.id

    # аналитика считает выручку по полной сумме заказа, а не по доплате —
    # предоплата не теряется из отчётов
    dashboard = await GetDashboardUseCase(make_uow(tenant_id)).execute(owner)
    assert dashboard.today.revenue == Decimal("3000")
    assert dashboard.today.profit == Decimal("1800")  # 3000 - 1200


async def test_order_issue_cash_payment_computes_change_from_balance_due(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Торт на заказ", retail_price=Money.of("3000"))
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("1"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Милана")
    )
    order = await CreateOrderUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateOrderCommand(
            client_id=client.id,
            warehouse_id=warehouse_id,
            items=[OrderItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("3000"))],
            due_date=date.today(),
            prepayment=Decimal("1000"),
        ),
    )
    await ChangeOrderStatusUseCase(make_uow(tenant_id)).execute(
        owner, ChangeOrderStatusCommand(order.id, OrderStatus.READY)
    )

    result = await IssueOrderUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueOrderCommand(
            order_id=order.id, payment_method=PaymentMethod.CASH, cash_received=Decimal("2500")
        ),
    )
    assert result.sale.total == Money.of("2000")
    assert result.change == Money.of("500")  # сдача с доплаты, не с полной суммы
