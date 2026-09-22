from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select, update
from app.application.auth.create_employee import CreateEmployeeCommand, CreateEmployeeUseCase
from app.application.counterparties.create_client import (
    CreateClientCommand,
    CreateClientUseCase,
)
from app.application.debts.repay_debt import RepayDebtCommand, RepayDebtUseCase
from app.application.inventory.common import LineInput
from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.inventory.stocktake import StocktakeCommand, StocktakeUseCase
from app.application.inventory.transfer import TransferCommand, TransferUseCase
from app.application.inventory.write_off import WriteOffCommand, WriteOffUseCase
from app.application.sales.create_sale import (
    CreateSaleCommand,
    CreateSaleUseCase,
    SaleItemInput,
)
from app.application.sales.delete_sale import DeleteSaleCommand, DeleteSaleUseCase
from app.application.sales.edit_sale import EditSaleCommand, EditSaleUseCase
from app.application.sales.return_sale import (
    ReturnItemInput,
    ReturnSaleCommand,
    ReturnSaleUseCase,
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
from app.domain.inventory.entities import StockDocType
from app.domain.sales.payment import PaymentMethod
from app.infrastructure.db.models.sales import SaleModel


async def test_sale_flow_stock_and_credit_debt(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Духи 6мл")

    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"), cost=Decimal("150"))],
        ),
    )

    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Ахмед", debt_limit=Decimal("1000"))
    )

    result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CREDIT,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("2"), price=Decimal("250"))],
            client_id=client.id,
            debt_due_date=date.today() + timedelta(days=7),
        ),
    )
    assert result.sale.total == Money.of("500")

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("8")
        debts = await uow.debts.list_by_client(client.id)
        assert len(debts) == 1
        assert debts[0].balance == Money.of("500")
        assert debts[0].sale_id == result.sale.id

    # вторая продажа в долг на 750 превысила бы лимит 1000 (500 + 750)
    with pytest.raises(DomainError):
        await CreateSaleUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateSaleCommand(
                warehouse_id=warehouse_id,
                payment_method=PaymentMethod.CREDIT,
                items=[SaleItemInput(product_id=product.id, quantity=Decimal("3"), price=Decimal("250"))],
                client_id=client.id,
                debt_due_date=date.today() + timedelta(days=7),
            ),
        )

    debt = await RepayDebtUseCase(make_uow(tenant_id)).execute(
        owner, RepayDebtCommand(debt_id=debts[0].id, amount=Decimal("200"))
    )
    assert debt.balance == Money.of("300")


async def test_sale_fails_on_insufficient_stock(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id)

    with pytest.raises(InsufficientStockError):
        await CreateSaleUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateSaleCommand(
                warehouse_id=warehouse_id,
                payment_method=PaymentMethod.CASH,
                items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("250"))],
            ),
        )


async def test_sale_change_calculation(make_uow, registered_shop, warehouse_id, create_product):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id)
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )

    result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("250"))],
            cash_received=Decimal("1000"),
        ),
    )
    assert result.change == Money.of("750")


async def test_return_sale_restocks_and_computes_refund(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Платье")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"))],
        ),
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("3"), price=Decimal("250"))],
        ),
    )
    sale_line_id = sale_result.sale.lines[0].id

    return_result = await ReturnSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        ReturnSaleCommand(
            sale_id=sale_result.sale.id,
            items=[ReturnItemInput(sale_line_id=sale_line_id, quantity=Decimal("2"))],
        ),
    )
    assert return_result.refund == Money.of("500")

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("9")  # 10 - 3 + 2


async def test_return_sale_reduces_linked_debt(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Куртка")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Ахмед", debt_limit=Decimal("10000"))
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CREDIT,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("2"), price=Decimal("1000"))],
            client_id=client.id,
            debt_due_date=date.today() + timedelta(days=7),
        ),
    )
    sale_line_id = sale_result.sale.lines[0].id

    await ReturnSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        ReturnSaleCommand(
            sale_id=sale_result.sale.id,
            items=[ReturnItemInput(sale_line_id=sale_line_id, quantity=Decimal("1"))],
        ),
    )

    async with make_uow(tenant_id) as uow:
        debts = await uow.debts.list_by_client(client.id)
        assert debts[0].balance == Money.of("1000")  # было 2000, возврат на 1000 уменьшил долг


async def test_return_sale_rejects_quantity_over_remaining(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Тарелка")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"))],
        ),
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("2"), price=Decimal("100"))],
        ),
    )
    sale_line_id = sale_result.sale.lines[0].id

    await ReturnSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        ReturnSaleCommand(
            sale_id=sale_result.sale.id,
            items=[ReturnItemInput(sale_line_id=sale_line_id, quantity=Decimal("1"))],
        ),
    )
    with pytest.raises(DomainError):
        await ReturnSaleUseCase(make_uow(tenant_id)).execute(
            owner,
            ReturnSaleCommand(
                sale_id=sale_result.sale.id,
                items=[ReturnItemInput(sale_line_id=sale_line_id, quantity=Decimal("2"))],
            ),
        )


async def test_storekeeper_cannot_return_sale(
    make_uow, hasher, registered_shop, warehouse_id, create_product, random_phone
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Обувь")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("100"))],
        ),
    )
    storekeeper = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Руслан", random_phone(), "secret123", Role.STOREKEEPER)
    )
    with pytest.raises(AccessDeniedError):
        await ReturnSaleUseCase(make_uow(tenant_id)).execute(
            Actor(id=storekeeper.id, role=storekeeper.role),
            ReturnSaleCommand(
                sale_id=sale_result.sale.id,
                items=[ReturnItemInput(sale_line_id=sale_result.sale.lines[0].id, quantity=Decimal("1"))],
            ),
        )


async def test_delete_sale_restocks_and_annuls_debt(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Сумка")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Ахмед", debt_limit=Decimal("10000"))
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CREDIT,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("3"), price=Decimal("500"))],
            client_id=client.id,
            debt_due_date=date.today() + timedelta(days=7),
        ),
    )

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("7")  # 10 - 3

    await DeleteSaleUseCase(make_uow(tenant_id)).execute(
        owner, DeleteSaleCommand(sale_id=sale_result.sale.id)
    )

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("10")  # остаток вернулся
        debts = await uow.debts.list_by_client(client.id)
        assert debts[0].balance == Money.zero()  # долг аннулирован
        deleted_sale = await uow.sales.get(sale_result.sale.id)
        assert deleted_sale.deleted_at is not None


async def test_deleted_sale_excluded_from_list(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Ремень")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("100"))],
        ),
    )
    await DeleteSaleUseCase(make_uow(tenant_id)).execute(
        owner, DeleteSaleCommand(sale_id=sale_result.sale.id)
    )

    async with make_uow(tenant_id) as uow:
        sales, _ = await uow.sales.list()
        assert all(s.id != sale_result.sale.id for s in sales)


async def test_seller_cannot_delete_sale(
    make_uow, hasher, registered_shop, warehouse_id, create_product, random_phone
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Кепка")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("100"))],
        ),
    )
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Марат", random_phone(), "secret123", Role.SELLER)
    )
    with pytest.raises(AccessDeniedError):
        await DeleteSaleUseCase(make_uow(tenant_id)).execute(
            Actor(id=seller.id, role=seller.role),
            DeleteSaleCommand(sale_id=sale_result.sale.id),
        )


async def test_edit_sale_updates_client_and_note(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Зонт")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Заур", debt_limit=Decimal("10000"))
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("100"))],
        ),
    )

    await EditSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        EditSaleCommand(sale_id=sale_result.sale.id, client_id=client.id, note="Забрал сам"),
    )

    async with make_uow(tenant_id) as uow:
        sale = await uow.sales.get(sale_result.sale.id)
        assert sale.client_id == client.id
        assert sale.note == "Забрал сам"


async def test_seller_cannot_edit_sale_after_window(
    make_uow, hasher, registered_shop, warehouse_id, create_product, random_phone
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Шарф")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Ислам", random_phone(), "secret123", Role.SELLER)
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        Actor(id=seller.id, role=seller.role),
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CASH,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("100"))],
        ),
    )

    async with make_uow(tenant_id) as uow:
        await uow.session.execute(
            update(SaleModel)
            .where(SaleModel.id == sale_result.sale.id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(hours=25))
        )
        await uow.commit()

    with pytest.raises(AccessDeniedError):
        await EditSaleUseCase(make_uow(tenant_id)).execute(
            Actor(id=seller.id, role=seller.role),
            EditSaleCommand(sale_id=sale_result.sale.id, client_id=None, note="поздно"),
        )


async def test_write_off_reduces_stock(make_uow, registered_shop, warehouse_id, create_product):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Стекло витринное")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("20"))],
        ),
    )

    document = await WriteOffUseCase(make_uow(tenant_id)).execute(
        owner,
        WriteOffCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("3"))],
            note="бой при разгрузке",
        ),
    )
    assert document.type is StockDocType.WRITE_OFF

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("17")


async def test_transfer_moves_stock_between_warehouses(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Кроссовки 42")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"))],
        ),
    )

    async with make_uow(tenant_id) as uow:
        second_warehouse = await uow.warehouses.add(Warehouse(id=None, name="Точка на Беркате"))
        await uow.commit()
        second_warehouse_id = second_warehouse.id

    await TransferUseCase(make_uow(tenant_id)).execute(
        owner,
        TransferCommand(
            warehouse_id=warehouse_id,
            to_warehouse_id=second_warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("4"))],
        ),
    )

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("6")
        assert await uow.stock.get(product.id, second_warehouse_id) == Decimal("4")


async def test_stocktake_detects_and_corrects_discrepancy(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Орехи грецкие")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("50"))],
        ),
    )

    result = await StocktakeUseCase(make_uow(tenant_id)).execute(
        owner,
        StocktakeCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("46"))],  # недостача 4
        ),
    )
    assert len(result.discrepancies) == 1
    assert result.discrepancies[0].delta == Decimal("-4")

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("46")


async def test_credit_sale_with_paid_now_creates_residual_debt(
    make_uow, registered_shop, warehouse_id, create_product
):
    """Долг = total − paid_now; выручка по полной сумме (total не уменьшается)."""
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Куртка")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Ахмед", debt_limit=Decimal("10000"))
    )

    result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CREDIT,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("5000"))],
            client_id=client.id,
            debt_due_date=date.today() + timedelta(days=7),
            paid_now=Decimal("3000"),
        ),
    )
    assert result.sale.total == Money.of("5000")
    assert result.sale.paid_now == Money.of("3000")
    assert result.sale.debt_amount == Money.of("2000")

    async with make_uow(tenant_id) as uow:
        debts = await uow.debts.list_by_client(client.id)
        assert len(debts) == 1
        assert debts[0].amount == Money.of("2000")
        assert debts[0].balance == Money.of("2000")


async def test_paid_now_rejects_when_covers_full_total(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id)
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Клиент")
    )

    with pytest.raises(DomainError, match="заплатил всю сумму"):
        await CreateSaleUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateSaleCommand(
                warehouse_id=warehouse_id,
                payment_method=PaymentMethod.CREDIT,
                items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("500"))],
                client_id=client.id,
                debt_due_date=date.today() + timedelta(days=7),
                paid_now=Decimal("500"),
            ),
        )


async def test_paid_now_rejects_on_cash_payment(
    make_uow, registered_shop, warehouse_id, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id)
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )

    with pytest.raises(DomainError, match="Заплатил сейчас"):
        await CreateSaleUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateSaleCommand(
                warehouse_id=warehouse_id,
                payment_method=PaymentMethod.CASH,
                items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("500"))],
                paid_now=Decimal("100"),
            ),
        )


async def test_debt_limit_checked_against_residual_not_full_total(
    make_uow, registered_shop, warehouse_id, create_product
):
    """Лимит 2500: продажа 5000 с paid_now 3000 → долг 2000 — проходит."""
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id)
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Лимит", debt_limit=Decimal("2500"))
    )

    result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CREDIT,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("5000"))],
            client_id=client.id,
            debt_due_date=date.today() + timedelta(days=7),
            paid_now=Decimal("3000"),
        ),
    )
    assert result.sale.debt_amount == Money.of("2000")

    # без paid_now полная сумма 3000 превысила бы лимит 2500
    with pytest.raises(DomainError, match="лимит долга"):
        await CreateSaleUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateSaleCommand(
                warehouse_id=warehouse_id,
                payment_method=PaymentMethod.CREDIT,
                items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("3000"))],
                client_id=client.id,
                debt_due_date=date.today() + timedelta(days=7),
            ),
        )


async def test_return_after_partial_paid_now_refunds_cash_excess(
    make_uow, registered_shop, warehouse_id, create_product
):
    """Продажа 5000, paid_now 3000, долг 2000. Возврат на 1000 → только долг, клиенту 0."""
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Товар")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Клиент", debt_limit=Decimal("50000"))
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CREDIT,
            items=[SaleItemInput(product_id=product.id, quantity=Decimal("5"), price=Decimal("1000"))],
            client_id=client.id,
            debt_due_date=date.today() + timedelta(days=7),
            paid_now=Decimal("3000"),
        ),
    )
    sale_line_id = sale_result.sale.lines[0].id

    partial = await ReturnSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        ReturnSaleCommand(
            sale_id=sale_result.sale.id,
            items=[ReturnItemInput(sale_line_id=sale_line_id, quantity=Decimal("1"))],
        ),
    )
    assert partial.refund == Money.of("1000")
    assert partial.cash_to_client == Money.zero()
    async with make_uow(tenant_id) as uow:
        debts = await uow.debts.list_by_client(client.id)
        assert debts[0].balance == Money.of("1000")


async def test_return_full_goods_after_paid_now_gives_cash_to_client(
    make_uow, registered_shop, warehouse_id, create_product
):
    """Продажа 5000 (paid_now 3000, долг 2000). Возврат на 4000 → долг 0, клиенту 2000."""
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Большой")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("10"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Клиент2", debt_limit=Decimal("50000"))
    )
    p2 = await create_product(tenant_id, name="Малый")
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=p2.id, quantity=Decimal("10"))],
        ),
    )
    sale_result = await CreateSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateSaleCommand(
            warehouse_id=warehouse_id,
            payment_method=PaymentMethod.CREDIT,
            items=[
                SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("3000")),
                SaleItemInput(product_id=p2.id, quantity=Decimal("2"), price=Decimal("1000")),
            ],
            client_id=client.id,
            debt_due_date=date.today() + timedelta(days=7),
            paid_now=Decimal("3000"),
        ),
    )
    lines = {line.product_id: line for line in sale_result.sale.lines}
    ret = await ReturnSaleUseCase(make_uow(tenant_id)).execute(
        owner,
        ReturnSaleCommand(
            sale_id=sale_result.sale.id,
            items=[
                ReturnItemInput(sale_line_id=lines[product.id].id, quantity=Decimal("1")),  # 3000
                ReturnItemInput(sale_line_id=lines[p2.id].id, quantity=Decimal("1")),  # 1000
            ],
        ),
    )
    assert ret.refund == Money.of("4000")
    assert ret.cash_to_client == Money.of("2000")
    async with make_uow(tenant_id) as uow:
        debts = await uow.debts.list_by_client(client.id)
        assert debts[0].balance == Money.zero()


async def test_edit_sale_client_note_after_paid_now(
    make_uow, registered_shop, warehouse_id, create_product
):
    """edit_sale по-прежнему только клиент/заметка — суммы и paid_now не трогает."""
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id)
    await ReceiveGoodsUseCase(make_uow(tenant_id)).execute(
        owner,
        ReceiveGoodsCommand(
            warehouse_id=warehouse_id,
            lines=[LineInput(product_id=product.id, quantity=Decimal("5"))],
        ),
    )
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="А", debt_limit=Decimal("10000"))
    )
    other = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Б")
    )
    sale = (
        await CreateSaleUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateSaleCommand(
                warehouse_id=warehouse_id,
                payment_method=PaymentMethod.CREDIT,
                items=[SaleItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("1000"))],
                client_id=client.id,
                debt_due_date=date.today() + timedelta(days=7),
                paid_now=Decimal("400"),
            ),
        )
    ).sale

    await EditSaleUseCase(make_uow(tenant_id)).execute(
        owner, EditSaleCommand(sale_id=sale.id, client_id=other.id, note="правка")
    )
    async with make_uow(tenant_id) as uow:
        updated = await uow.sales.get(sale.id)
        assert updated.client_id == other.id
        assert updated.note == "правка"
        assert updated.paid_now == Money.of("400")
        debts = await uow.debts.list_by_client(client.id)
        assert debts[0].balance == Money.of("600")
