from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select, update
from app.application.counterparties.create_client import (
    CreateClientCommand,
    CreateClientUseCase,
)
from app.application.counterparties.update_client import (
    UpdateClientCommand,
    UpdateClientUseCase,
)
from app.application.debts.issue_debt import IssueDebtCommand, IssueDebtUseCase
from app.application.inventory.common import LineInput
from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.storefront.create_request import (
    CreateStorefrontRequestCommand,
    CreateStorefrontRequestUseCase,
    StorefrontRequestItemInput,
)
from app.application.storefront.release_expired_reservations import _release_for_tenant
from app.application.inventory.update_warehouse_details import (
    UpdateWarehouseDetailsCommand,
    UpdateWarehouseDetailsUseCase,
)
from app.application.auth.update_shop import UpdateShopCommand, UpdateShopUseCase
from app.domain.common.exceptions import (
    AccessDeniedError,
    ClientHasDebtError,
    DomainError,
    InsufficientStockError,
    NotFoundError,
)
from app.domain.common.money import Money
from app.domain.common.phone import Phone
from app.domain.customers.entities import Customer
from app.infrastructure.db.models.storefront import StorefrontRequestModel


async def test_update_client_changes_fields(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Ахмед", debt_limit=Decimal("1000"))
    )

    updated = await UpdateClientUseCase(make_uow(tenant_id)).execute(
        owner,
        UpdateClientCommand(
            client_id=client.id, name="Ахмед Х.", city="Грозный", debt_limit=Decimal("2000"),
        ),
    )

    assert updated.name == "Ахмед Х."
    assert updated.city == "Грозный"
    assert updated.debt_limit == Money.of("2000")


async def test_deactivated_client_excluded_from_default_search(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Заур")
    )

    await UpdateClientUseCase(make_uow(tenant_id)).execute(
        owner,
        UpdateClientCommand(client_id=client.id, name="Заур", is_active=False),
    )

    async with make_uow(tenant_id) as uow:
        assert await uow.clients.search("Заур") == []
        visible_with_inactive = await uow.clients.search("Заур", include_inactive=True)
        assert visible_with_inactive[0].is_active is False


async def test_deactivate_client_without_debt_ok(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Без долга")
    )

    updated = await UpdateClientUseCase(make_uow(tenant_id)).execute(
        owner,
        UpdateClientCommand(client_id=client.id, name="Без долга", is_active=False),
    )
    assert updated.is_active is False


async def test_deactivate_client_with_debt_requires_force(
    make_uow, registered_shop, warehouse_id
):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Должник")
    )
    await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(client_id=client.id, warehouse_id=warehouse_id, amount=Decimal("1500")),
    )

    with pytest.raises(ClientHasDebtError, match="1\u202f500"):
        await UpdateClientUseCase(make_uow(tenant_id)).execute(
            owner,
            UpdateClientCommand(client_id=client.id, name="Должник", is_active=False),
        )

    async with make_uow(tenant_id) as uow:
        still_active = await uow.clients.get(client.id)
        assert still_active.is_active is True

    deactivated = await UpdateClientUseCase(make_uow(tenant_id)).execute(
        owner,
        UpdateClientCommand(client_id=client.id, name="Должник", is_active=False, force=True),
    )
    assert deactivated.is_active is False


async def test_release_expired_storefront_reservations_frees_stale_reserve(
    make_uow, registered_shop, warehouse_id, create_product, db_session_factory
):
    """Не ждём реальные 72 часа — искусственно состариваем created_at заявки
    и вызываем саму функцию освобождения напрямую."""
    tenant_id, _, owner = registered_shop
    product = await create_product(
        tenant_id, name="Резервируемый", retail_price=Money.of("100"), show_on_storefront=True
    )

    await UpdateWarehouseDetailsUseCase(make_uow(tenant_id)).execute(
        owner,
        UpdateWarehouseDetailsCommand(
            warehouse_id=warehouse_id, name="Основной склад", show_on_storefront=True
        ),
    )
    tenant = await UpdateShopUseCase(make_uow(tenant_id)).execute(
        owner, UpdateShopCommand(name="Магазин", storefront_enabled=True)
    )
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"), cost=Decimal("50"))],
        ),
    )

    async with make_uow() as public_uow:
        customer = await public_uow.customers.add(
            Customer(id=None, phone=Phone("+79991234567"))
        )
        await public_uow.commit()

    request = await CreateStorefrontRequestUseCase(db_session_factory).execute(
        CreateStorefrontRequestCommand(
            slug=tenant.slug,
            customer_id=customer.id,
            customer_name="Клиент",
            items=[StorefrontRequestItemInput(product_id=product.id, quantity=Decimal("5"))],
        )
    )
    assert request.insufficient_stock_at_request is False

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get_reserved(product.id, warehouse_id) == Decimal("5")

        # состариваем заявку так, будто она создана 4 дня назад (> 72ч)
        await uow.session.execute(
            update(StorefrontRequestModel)
            .where(StorefrontRequestModel.id == request.id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=4))
        )
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        await _release_for_tenant(uow)
        await uow.commit()

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get_reserved(product.id, warehouse_id) == Decimal("0")
        released_request = await uow.storefront_requests.get(request.id)
        assert released_request.status.value == "new"  # статус не тронут
        assert released_request.reservation_released is True
