from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import openpyxl
import pytest

from app.application.auth.create_employee import CreateEmployeeCommand, CreateEmployeeUseCase
from app.application.auth.login import LoginCommand, LoginUseCase
from app.application.auth.register_shop import RegisterShopCommand, RegisterShopUseCase
from app.application.counterparties.create_client import (
    CreateClientCommand,
    CreateClientUseCase,
)
from app.application.counterparties.create_supplier import (
    CreateSupplierCommand,
    CreateSupplierUseCase,
)
from app.application.debts.create_installment import (
    CreateInstallmentCommand,
    CreateInstallmentUseCase,
    InstallmentInput,
)
from app.application.debts.issue_debt import IssueDebtCommand, IssueDebtUseCase
from app.application.debts.repay_debt import RepayDebtCommand, RepayDebtUseCase
from app.application.inventory.common import LineInput
from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.inventory.stocktake import StocktakeCommand, StocktakeUseCase
from app.application.inventory.transfer import TransferCommand, TransferUseCase
from app.application.inventory.write_off import WriteOffCommand, WriteOffUseCase
from app.application.orders.change_status import (
    ChangeOrderStatusCommand,
    ChangeOrderStatusUseCase,
)
from app.application.orders.create_order import (
    CreateOrderCommand,
    CreateOrderUseCase,
    OrderItemInput,
)
from app.application.products.create_product import CreateProductCommand, CreateProductUseCase
from app.application.products.create_unit import CreateUnitCommand, CreateUnitUseCase
from app.application.products.import_excel import ImportProductsCommand, ImportProductsUseCase
from app.application.products.set_product_photo import (
    SetProductPhotoCommand,
    SetProductPhotoUseCase,
)
from app.application.products.update_product import UpdateProductCommand, UpdateProductUseCase
from app.application.sales.create_sale import (
    CreateSaleCommand,
    CreateSaleUseCase,
    SaleItemInput,
)
from app.application.sales.return_sale import (
    ReturnItemInput,
    ReturnSaleCommand,
    ReturnSaleUseCase,
)
from app.domain.common.exceptions import (
    AccessDeniedError,
    DomainError,
    InsufficientStockError,
)
from app.domain.common.money import Money
from app.domain.identity.entities import Role, Warehouse
from app.domain.identity.permissions import Actor
from app.domain.inventory.entities import StockDocType
from app.domain.orders.entities import OrderStatus
from app.domain.sales.payment import PaymentMethod
from app.infrastructure.files import LocalFileStorage


async def test_register_login_and_wrong_password(make_uow, hasher, registered_shop):
    tenant_id, phone, _ = registered_shop

    user = await LoginUseCase(make_uow(), hasher).execute(
        LoginCommand(phone=phone, password="secret123")
    )
    assert user.tenant_id == tenant_id
    assert user.role is Role.OWNER

    with pytest.raises(AccessDeniedError):
        await LoginUseCase(make_uow(), hasher).execute(
            LoginCommand(phone=phone, password="wrong")
        )


async def test_register_shop_generates_unique_slug_on_name_collision(
    make_uow, hasher, random_phone
):
    first = await RegisterShopUseCase(make_uow(), hasher).execute(
        RegisterShopCommand(
            shop_name="Магазин Беркат", owner_name="Ахмед",
            phone=random_phone(), password="secret123",
        )
    )
    second = await RegisterShopUseCase(make_uow(), hasher).execute(
        RegisterShopCommand(
            shop_name="Магазин Беркат", owner_name="Муса",
            phone=random_phone(), password="secret123",
        )
    )
    assert first.shop_slug == "magazin-berkat"
    assert second.shop_slug == "magazin-berkat-2"


async def test_duplicate_phone_registration_fails(make_uow, hasher, registered_shop):
    _, phone, _ = registered_shop
    with pytest.raises(DomainError):
        await RegisterShopUseCase(make_uow(), hasher).execute(
            RegisterShopCommand("Другой", "Муса", phone, "secret123")
        )


async def test_manager_cannot_create_manager(make_uow, hasher, registered_shop, random_phone):
    tenant_id, _, owner = registered_shop

    manager = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Умар", random_phone(), "secret123", Role.MANAGER)
    )
    manager_actor = Actor(id=manager.id, role=manager.role)

    # управляющий может создать продавца…
    await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        manager_actor, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )
    # …но не другого управляющего
    with pytest.raises(AccessDeniedError):
        await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
            manager_actor, CreateEmployeeCommand("Иса", random_phone(), "secret123", Role.MANAGER)
        )


async def test_seller_cannot_create_product(make_uow, hasher, registered_shop, random_phone):
    tenant_id, _, owner = registered_shop
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )
    with pytest.raises(AccessDeniedError):
        await CreateProductUseCase(make_uow(tenant_id)).execute(
            Actor(id=seller.id, role=seller.role),
            CreateProductCommand(
                name="Товар", unit_code="pcs",
                purchase_price=Decimal("150"), retail_price=Decimal("250"),
            ),
        )


async def test_update_product_use_case_updates_and_seller_forbidden(
    make_uow, hasher, registered_shop, create_product, random_phone
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Мёд")

    updated = await UpdateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        UpdateProductCommand(
            product_id=product.id,
            name="Мёд горный",
            unit_code="pcs",
            purchase_price=Decimal("420"),
            retail_price=Decimal("750"),
        ),
    )
    assert updated.name == "Мёд горный"
    assert updated.retail_price == Money.of("750")

    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )
    with pytest.raises(AccessDeniedError):
        await UpdateProductUseCase(make_uow(tenant_id)).execute(
            Actor(id=seller.id, role=seller.role),
            UpdateProductCommand(
                product_id=product.id,
                name="Хак",
                unit_code="pcs",
                purchase_price=Decimal("1"),
                retail_price=Decimal("2"),
            ),
        )


async def test_create_custom_unit_and_use_it_in_product(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop

    unit = await CreateUnitUseCase(make_uow(tenant_id)).execute(
        owner, CreateUnitCommand(code="box", name="коробка")
    )
    assert unit.code == "box"

    product = await CreateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateProductCommand(
            name="Плитка облицовочная", unit_code="box",
            purchase_price=Decimal("500"), retail_price=Decimal("800"),
        ),
    )
    assert product.unit.code == "box"
    assert product.unit.name == "коробка"


async def test_create_unit_rejects_duplicate_code(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    with pytest.raises(DomainError):
        await CreateUnitUseCase(make_uow(tenant_id)).execute(
            owner, CreateUnitCommand(code="pcs", name="дубликат предустановленной")
        )


async def test_seller_cannot_create_unit(make_uow, hasher, registered_shop, random_phone):
    tenant_id, _, owner = registered_shop
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )
    with pytest.raises(AccessDeniedError):
        await CreateUnitUseCase(make_uow(tenant_id)).execute(
            Actor(id=seller.id, role=seller.role), CreateUnitCommand(code="box", name="коробка")
        )


async def test_create_product_rejects_unknown_unit_code(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    with pytest.raises(DomainError):
        await CreateProductUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateProductCommand(
                name="Товар", unit_code="unknown",
                purchase_price=Decimal("1"), retail_price=Decimal("2"),
            ),
        )


def _build_workbook(rows: list[tuple]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(
        ["Название", "Артикул", "Штрихкод", "Ед. изм.", "Закупочная цена", "Розничная цена", "Мин. остаток"]
    )
    for row in rows:
        sheet.append(list(row))
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


async def test_import_products_from_excel_creates_all_valid_rows(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    file_bytes = _build_workbook(
        [
            ("Мёд горный", "", "", "kg", 400, 700, 2),
            ("Орехи грецкие", "NUT-1", "", "kg", 600, 900, 0),
            ("Плитка облицовочная", "", "", "box", 500, 800, 0),
        ]
    )
    result = await ImportProductsUseCase(make_uow(tenant_id)).execute(
        owner, ImportProductsCommand(file_bytes)
    )
    assert result.created == 2  # третья строка (unit_code="box") не существует
    assert len(result.errors) == 1
    assert result.errors[0].row == 4


async def test_import_products_skips_bad_rows_but_keeps_good_ones(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    file_bytes = _build_workbook(
        [
            ("Мёд горный", "", "", "kg", 400, 700, 0),
            ("Без цены", "", "", "pcs", "не число", 700, 0),
            ("Орехи грецкие", "", "", "kg", 600, 900, 0),
        ]
    )
    result = await ImportProductsUseCase(make_uow(tenant_id)).execute(
        owner, ImportProductsCommand(file_bytes)
    )
    assert result.created == 2
    assert len(result.errors) == 1
    assert result.errors[0].row == 3


async def test_seller_cannot_import_products(make_uow, hasher, registered_shop, random_phone):
    tenant_id, _, owner = registered_shop
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )
    file_bytes = _build_workbook([("Товар", "", "", "pcs", 1, 2, 0)])
    with pytest.raises(AccessDeniedError):
        await ImportProductsUseCase(make_uow(tenant_id)).execute(
            Actor(id=seller.id, role=seller.role), ImportProductsCommand(file_bytes)
        )


async def test_set_product_photo_updates_product(
    make_uow, registered_shop, create_product, tmp_path
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Плитка")
    storage = LocalFileStorage(tmp_path)

    updated = await SetProductPhotoUseCase(make_uow(tenant_id), storage).execute(
        owner, SetProductPhotoCommand(product.id, "photo.png", b"fake-png-bytes")
    )
    assert updated.photo.startswith("/uploads/") and updated.photo.endswith(".png")
    assert (tmp_path / updated.photo.removeprefix("/uploads/")).read_bytes() == b"fake-png-bytes"


async def test_set_product_photo_rejects_bad_extension(make_uow, registered_shop, create_product, tmp_path):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Плитка")
    with pytest.raises(DomainError):
        await SetProductPhotoUseCase(make_uow(tenant_id), LocalFileStorage(tmp_path)).execute(
            owner, SetProductPhotoCommand(product.id, "virus.exe", b"data")
        )


async def test_seller_cannot_set_product_photo(
    make_uow, hasher, registered_shop, create_product, random_phone, tmp_path
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Плитка")
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )
    with pytest.raises(AccessDeniedError):
        await SetProductPhotoUseCase(make_uow(tenant_id), LocalFileStorage(tmp_path)).execute(
            Actor(id=seller.id, role=seller.role),
            SetProductPhotoCommand(product.id, "photo.jpg", b"data"),
        )


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


async def test_issue_debt_respects_debt_limit_without_sale(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Ибрагим", debt_limit=Decimal("2000"))
    )

    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(client_id=client.id, amount=Decimal("1500"), note="стройматериалы в долг"),
    )
    assert debt.balance == Money.of("1500")

    with pytest.raises(DomainError):
        await IssueDebtUseCase(make_uow(tenant_id)).execute(
            owner, IssueDebtCommand(client_id=client.id, amount=Decimal("1000"))
        )


async def test_create_installment_schedule_must_match_balance(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Заур")
    )
    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner, IssueDebtCommand(client_id=client.id, amount=Decimal("3000"))
    )

    with pytest.raises(DomainError):
        await CreateInstallmentUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateInstallmentCommand(
                debt_id=debt.id,
                schedule=[
                    InstallmentInput(due_date=date.today() + timedelta(days=7), amount=Decimal("1000"))
                ],
            ),
        )

    updated = await CreateInstallmentUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateInstallmentCommand(
            debt_id=debt.id,
            schedule=[
                InstallmentInput(due_date=date.today() + timedelta(days=7), amount=Decimal("1500")),
                InstallmentInput(due_date=date.today() + timedelta(days=14), amount=Decimal("1500")),
            ],
        ),
    )
    assert len(updated.schedule) == 2


async def test_storekeeper_cannot_create_sale_but_can_receive_goods(
    make_uow, hasher, registered_shop, warehouse_id, create_product, random_phone
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Мешок цемента")
    storekeeper = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Руслан", random_phone(), "secret123", Role.STOREKEEPER)
    )
    storekeeper_actor = Actor(id=storekeeper.id, role=storekeeper.role)

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


async def test_order_lifecycle(make_uow, registered_shop, create_product):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Торт на заказ", retail_price=Money.of("3000"))
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Милана")
    )

    order = await CreateOrderUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateOrderCommand(
            client_id=client.id,
            items=[OrderItemInput(product_id=product.id, quantity=Decimal("1"), price=Decimal("3000"))],
            due_date=date.today() + timedelta(days=3),
            prepayment=Decimal("1000"),
            note="из директа, надпись «С юбилеем»",
        ),
    )
    assert order.to_pay == Money.of("2000")

    order = await ChangeOrderStatusUseCase(make_uow(tenant_id)).execute(
        owner, ChangeOrderStatusCommand(order.id, OrderStatus.IN_PROGRESS)
    )
    assert order.status is OrderStatus.IN_PROGRESS

    # из «в работе» нельзя сразу «выдан»
    with pytest.raises(DomainError):
        await ChangeOrderStatusUseCase(make_uow(tenant_id)).execute(
            owner, ChangeOrderStatusCommand(order.id, OrderStatus.ISSUED)
        )
