from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select, update
from app.application.analytics.dashboard import GetDashboardUseCase
from app.application.analytics.dead_stock import (
    DeadStockQuery,
    GetDeadStockUseCase,
    GetStockValueUseCase,
)
from app.application.analytics.top_products import (
    CategoryProfitQuery,
    GetCategoryProfitUseCase,
    GetTopProductsUseCase,
    TopProductsQuery,
)
from app.application.auth.create_employee import CreateEmployeeCommand, CreateEmployeeUseCase
from app.application.inventory.common import LineInput
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
from app.application.sync.apply_offline_ops import (
    ApplyOfflineSalesCommand,
    ApplyOfflineSalesUseCase,
)
from app.domain.sales.payment import PaymentMethod
from app.infrastructure.db.models.identity import TenantModel
from app.domain.analytics.period import SummaryPeriod
from app.infrastructure.notifications.telegram import _send_summaries_async


async def test_dashboard_counts_sales_and_profit(
    make_uow, registered_shop, warehouse_id, create_product, hasher
):
    tenant_id, _, owner = registered_shop
    product = await create_product(
        tenant_id, name="Товар", purchase_price=Money.of("150"), retail_price=Money.of("250")
    )
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"), cost=Decimal("150"))],
        ),
    )
    await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("2"), price=Decimal("250"))],
        ),
    )

    dashboard = await GetDashboardUseCase(make_uow(tenant_id)).execute(owner)
    assert dashboard.today.sales_count == 1
    assert dashboard.today.revenue == Decimal("500")
    assert dashboard.today.profit == Decimal("200")  # (250-150)*2
    assert dashboard.month.sales_count == 1

    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand(name="Продавец", phone="+79280001122",
                                      password="secret123", role=Role.SELLER)
    )
    with pytest.raises(AccessDeniedError):
        await GetDashboardUseCase(make_uow(tenant_id)).execute(
            Actor(id=seller.id, role=seller.role)
        )


async def test_top_products_and_category_profit(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    popular = await create_product(
        tenant_id, name="Хит продаж", purchase_price=Money.of("100"), retail_price=Money.of("200")
    )
    rare = await create_product(
        tenant_id, name="Редкий товар", purchase_price=Money.of("50"), retail_price=Money.of("80")
    )
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[
                LineInput(product_id=popular.id, quantity=Decimal("20"), cost=Decimal("100")),
                LineInput(product_id=rare.id, quantity=Decimal("20"), cost=Decimal("50")),
            ],
        ),
    )
    await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[
                SaleItemInput(product_id=popular.id, quantity=Decimal("5"), price=Decimal("200")),
                SaleItemInput(product_id=rare.id, quantity=Decimal("1"), price=Decimal("80")),
            ],
        ),
    )

    now = datetime.now(timezone.utc)
    period = (now - timedelta(days=1), now + timedelta(days=1))

    top = await GetTopProductsUseCase(make_uow(tenant_id)).execute(
        owner, TopProductsQuery(date_from=period[0], date_to=period[1])
    )
    assert top[0].product_name == "Хит продаж"
    assert top[0].quantity_sold == Decimal("5")

    profit_by_category = await GetCategoryProfitUseCase(make_uow(tenant_id)).execute(
        owner, CategoryProfitQuery(date_from=period[0], date_to=period[1])
    )
    assert len(profit_by_category) == 1  # оба товара без категории — одна группа
    assert profit_by_category[0].category_id is None
    assert profit_by_category[0].profit == Decimal("530")  # (200-100)*5 + (80-50)*1


async def test_dead_stock_and_stock_value(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    stale = await create_product(
        tenant_id, name="Залежался", purchase_price=Money.of("100"), retail_price=Money.of("150")
    )
    fresh = await create_product(
        tenant_id, name="Свежий", purchase_price=Money.of("50"), retail_price=Money.of("90")
    )
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[
                LineInput(product_id=stale.id, quantity=Decimal("3"), cost=Decimal("100")),
                LineInput(product_id=fresh.id, quantity=Decimal("4"), cost=Decimal("50")),
            ],
        ),
    )
    await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=fresh.id, quantity=Decimal("1"), price=Decimal("90"))],
        ),
    )

    dead_stock = await GetDeadStockUseCase(make_uow(tenant_id)).execute(
        owner, DeadStockQuery(stale_days=0)
    )
    dead_names = {item.product_name for item in dead_stock}
    assert "Залежался" in dead_names  # никогда не продавался, остаток есть
    assert "Свежий" not in dead_names  # продавался только что

    stock_value = await GetStockValueUseCase(make_uow(tenant_id)).execute(owner)
    values = {item.product_name: item.value for item in stock_value}
    assert values["Залежался"] == Decimal("300")  # 3 * 100
    assert values["Свежий"] == Decimal("150")  # 3 (осталось) * 50


async def test_telegram_daily_summary(
    make_uow, registered_shop, warehouse_id, create_product, db_session_factory, monkeypatch
):
    tenant_id, _, owner = registered_shop
    product = await create_product(
        tenant_id, name="Товар", purchase_price=Money.of("100"), retail_price=Money.of("200")
    )
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"), cost=Decimal("100"))],
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

    async with db_session_factory() as session:
        model = (
            await session.execute(select(TenantModel).where(TenantModel.id == tenant_id))
        ).scalar_one()
        model.owner_telegram_chat_id = "12345"
        await session.commit()

    monkeypatch.setattr(
        "app.infrastructure.notifications.telegram.SqlAlchemyUnitOfWork",
        lambda tid: make_uow(tid) if tid is not None else make_uow(None),
    )

    sent = []
    documents = []

    class FakeNotifier:
        def send(self, chat_id: str, text: str) -> None:
            sent.append((chat_id, text))

        def send_document(self, chat_id: str, filename: str, content: bytes, caption: str = "") -> None:
            documents.append((chat_id, filename))

    # дефолт tenant.summary_daily_hour_msk = 20 (МСК) -> now в UTC должен быть 17:00
    await _send_summaries_async(SummaryPeriod.DAY, FakeNotifier(), now=datetime(2026, 8, 25, 17, tzinfo=timezone.utc))

    assert len(sent) == 1
    chat_id, text = sent[0]
    assert chat_id == "12345"
    assert "Продаж: <b>1</b>" in text
    assert "Выручка: <b>200" in text
    assert "Прибыль: <b>100" in text
    assert len(documents) == 1
    assert documents[0][0] == "12345"


async def test_notify_low_stock(
    make_uow, registered_shop, warehouse_id, create_product, monkeypatch
):
    from app.application.inventory.notify_low_stock import _run_async

    tenant_id, _, owner = registered_shop
    hot = await create_product(
        tenant_id, name="Ходовой", purchase_price=Money.of("100"), retail_price=Money.of("200"),
        min_stock=Decimal("5"),
    )
    cold = await create_product(
        tenant_id, name="Незнакомец", purchase_price=Money.of("50"), retail_price=Money.of("100"),
        min_stock=Decimal("5"),
    )
    for product, qty in ((hot, "5"), (cold, "1")):
        await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
            owner,
            ReceiveGoodsCommand(
                warehouse_id=warehouse_id,
                lines=[LineInput(product_id=product.id, quantity=Decimal(qty), cost=Decimal("10"))],
            ),
        )

    await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=hot.id, quantity=Decimal("3"), price=Decimal("200"))],
        ),
    )

    monkeypatch.setattr(
        "app.application.inventory.notify_low_stock.SqlAlchemyUnitOfWork",
        lambda tid: make_uow(tid) if tid is not None else make_uow(None),
    )

    sent = []

    class FakeNotifier:
        def send(self, chat_id: str, text: str) -> None:
            sent.append((chat_id, text))

    await _run_async(FakeNotifier())

    async with make_uow(tenant_id) as uow:
        notifications = await uow.notifications.list_for_user(owner.id)
    texts = [n.text for n in notifications]
    assert any("Ходовой" in t for t in texts)  # продавался и остаток <= min_stock
    assert not any("Незнакомец" in t for t in texts)  # никогда не продавался

    # повторный запуск без изменения остатка не плодит дубликат уведомления
    await _run_async(FakeNotifier())
    async with make_uow(tenant_id) as uow:
        notifications_again = await uow.notifications.list_for_user(owner.id)
    assert len(notifications_again) == len(notifications)

    # пополнили немного, но товар всё ещё ниже порога — новое уведомление уместно
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=hot.id, quantity=Decimal("1"), cost=Decimal("10"))],
        ),
    )
    await _run_async(FakeNotifier())
    async with make_uow(tenant_id) as uow:
        notifications_after_restock = await uow.notifications.list_for_user(owner.id)
    assert len(notifications_after_restock) == len(notifications) + 1


async def test_notify_low_stock_scoped_by_manager_warehouse(
    make_uow, registered_shop, warehouse_id, create_product, hasher, monkeypatch
):
    """Manager с ограниченным доступом к складу должен получать LOW_STOCK
    только по товарам на СВОЁМ складе, не по всему tenant'у — тот же принцип,
    что у GetRestockRecommendationsUseCase для обычных HTTP-запросов."""
    from app.application.inventory.notify_low_stock import _run_async
    from app.application.auth.create_employee import CreateEmployeeCommand, CreateEmployeeUseCase
    from app.application.inventory.create_warehouse import CreateWarehouseCommand, CreateWarehouseUseCase

    tenant_id, _, owner = registered_shop

    other_warehouse = await CreateWarehouseUseCase(make_uow(tenant_id)).execute(
        owner, CreateWarehouseCommand(name="Второй склад")
    )

    own_product = await create_product(
        tenant_id, name="На своём складе", purchase_price=Money.of("100"),
        retail_price=Money.of("200"), min_stock=Decimal("5"),
    )
    foreign_product = await create_product(
        tenant_id, name="На чужом складе", purchase_price=Money.of("100"),
        retail_price=Money.of("200"), min_stock=Decimal("5"),
    )
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=own_product.id, quantity=Decimal("5"), cost=Decimal("10"))],
        ),
    )
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=other_warehouse.id,
            lines=[LineInput(product_id=foreign_product.id, quantity=Decimal("5"), cost=Decimal("10"))],
        ),
    )
    # оба товара продавались — проходят фильтр «раскупают», отличаются только складом
    await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=own_product.id, quantity=Decimal("1"), price=Decimal("200"))],
        ),
    )
    await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=other_warehouse.id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=foreign_product.id, quantity=Decimal("1"), price=Decimal("200"))],
        ),
    )

    manager = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner,
        CreateEmployeeCommand(
            name="Управляющий", phone="+79280009911", password="secret123",
            role=Role.MANAGER, warehouse_ids=[warehouse_id],
        ),
    )

    monkeypatch.setattr(
        "app.application.inventory.notify_low_stock.SqlAlchemyUnitOfWork",
        lambda tid: make_uow(tid) if tid is not None else make_uow(None),
    )

    class FakeNotifier:
        def send(self, chat_id: str, text: str) -> None:
            pass

    await _run_async(FakeNotifier())

    async with make_uow(tenant_id) as uow:
        owner_notifications = await uow.notifications.list_for_user(owner.id)
        manager_notifications = await uow.notifications.list_for_user(manager.id)

    owner_texts = [n.text for n in owner_notifications]
    manager_texts = [n.text for n in manager_notifications]

    # owner видит оба склада целиком
    assert any("На своём складе" in t for t in owner_texts)
    assert any("На чужом складе" in t for t in owner_texts)

    # manager видит только свой склад — товар с чужого склада не должен просочиться
    assert any("На своём складе" in t for t in manager_texts)
    assert not any("На чужом складе" in t for t in manager_texts)


async def test_create_sale_is_idempotent_by_client_op_id(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, retail_price=Money.of("250"))

    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"))],
        ),
    )

    cmd = CreateSaleCommand(
        warehouse_id=warehouse_id,
        payment_method=PaymentMethod.CASH,
        items=[SaleItemInput(product_id=product.id, quantity=Decimal("2"), price=Decimal("250"))],
        client_op_id="device-1-op-42",
    )

    first = await CreateSaleUseCase(make_uow(tenant_id)).execute(owner, cmd)
    second = await CreateSaleUseCase(make_uow(tenant_id)).execute(owner, cmd)

    assert first.sale.id == second.sale.id  # повторная отправка не создала вторую продажу

    async with make_uow(tenant_id) as uow:
        remaining = await uow.stock.get(product.id, warehouse_id)
    assert remaining == Decimal("8")  # остаток списан один раз, не дважды


async def test_apply_offline_sales_isolates_failures(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, retail_price=Money.of("100"))

    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("3"))],
        ),
    )

    ok_sale = CreateSaleCommand(
        warehouse_id=warehouse_id,
        payment_method=PaymentMethod.CASH,
        items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("100"))],
        client_op_id="op-ok",
    )
    failing_sale = CreateSaleCommand(
        warehouse_id=warehouse_id,
        payment_method=PaymentMethod.CASH,
        items=[SaleItemInput(product_id=product.id, quantity=Decimal("100"), price=Decimal("100"))],
        client_op_id="op-fail",
    )

    result = await ApplyOfflineSalesUseCase(make_uow(tenant_id)).execute(
        owner, ApplyOfflineSalesCommand(sales=[ok_sale, failing_sale])
    )

    assert len(result.applied) == 1
    assert len(result.errors) == 1
    assert result.errors[0].client_op_id == "op-fail"
