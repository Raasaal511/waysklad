from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO

import openpyxl
import pytest
from PIL import Image
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
from app.application.auth.login import LoginCommand, LoginUseCase
from app.application.auth.register_shop import RegisterShopCommand, RegisterShopUseCase
from app.application.auth.update_employee import UpdateEmployeeCommand, UpdateEmployeeUseCase
from app.application.counterparties.create_client import (
    CreateClientCommand,
    CreateClientUseCase,
)
from app.application.counterparties.create_supplier import (
    CreateSupplierCommand,
    CreateSupplierUseCase,
)
from app.application.counterparties.update_client import (
    UpdateClientCommand,
    UpdateClientUseCase,
)
from app.application.debts.create_installment import (
    CreateInstallmentCommand,
    CreateInstallmentUseCase,
    InstallmentInput,
)
from app.application.debts.issue_debt import IssueDebtCommand, IssueDebtUseCase
from app.application.debts.issue_supplier_debt import (
    IssueSupplierDebtCommand,
    IssueSupplierDebtUseCase,
)
from app.application.debts.extend_debt import ExtendDebtCommand, ExtendDebtUseCase
from app.application.debts.repay_debt import RepayDebtCommand, RepayDebtUseCase
from app.application.inventory.common import LineInput
from app.application.inventory.create_warehouse import (
    CreateWarehouseCommand,
    CreateWarehouseUseCase,
)
from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.inventory.set_warehouse_assignments import (
    SetWarehouseAssignmentsCommand,
    SetWarehouseAssignmentsUseCase,
)
from app.application.inventory.stocktake import StocktakeCommand, StocktakeUseCase
from app.application.inventory.transfer import TransferCommand, TransferUseCase
from app.application.inventory.write_off import WriteOffCommand, WriteOffUseCase
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
from app.application.products.create_product import (
    CreateProductCommand,
    CreateProductUseCase,
    VariantInput,
)
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
from app.application.sales.delete_sale import DeleteSaleCommand, DeleteSaleUseCase
from app.application.sales.edit_sale import EditSaleCommand, EditSaleUseCase
from app.application.sales.return_sale import (
    ReturnItemInput,
    ReturnSaleCommand,
    ReturnSaleUseCase,
)
from app.domain.catalog.barcode import Barcode
from app.domain.common.exceptions import (
    AccessDeniedError,
    DomainError,
    InsufficientStockError,
)
from app.domain.common.money import Money
from app.domain.debts.entities import Debt, DebtStatus, total_balance
from app.domain.identity.entities import Role, Warehouse
from app.domain.identity.permissions import Actor
from app.domain.inventory.entities import StockDocType
from app.domain.orders.entities import OrderStatus
from app.application.auth.connect_telegram import (
    ConnectTelegramCommand,
    ConnectTelegramUseCase,
)
from app.application.sync.apply_offline_ops import (
    ApplyOfflineSalesCommand,
    ApplyOfflineSalesUseCase,
)
from app.domain.sales.payment import PaymentMethod
from app.infrastructure.db.models.identity import TenantModel
from app.infrastructure.db.models.sales import SaleModel
from app.infrastructure.files import LocalFileStorage
from app.infrastructure.telegram import _send_summaries_async


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


async def test_create_product_with_initial_stock_posts_receipt(
    make_uow, registered_shop, warehouse_id
):
    tenant_id, _, owner = registered_shop
    product = await CreateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateProductCommand(
            name="Вода питьевая 0.5л", unit_code="pcs",
            purchase_price=Decimal("20"), retail_price=Decimal("40"),
            initial_stock_warehouse_id=warehouse_id,
            initial_stock_quantity=Decimal("100"),
        ),
    )

    uow = make_uow(tenant_id)
    async with uow:
        item = await uow.stock.get(product.id, warehouse_id)
        assert item == Decimal("100")


async def test_create_product_without_initial_stock_leaves_zero_stock(
    make_uow, registered_shop, warehouse_id
):
    tenant_id, _, owner = registered_shop
    product = await CreateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateProductCommand(
            name="Товар без остатка", unit_code="pcs",
            purchase_price=Decimal("10"), retail_price=Decimal("20"),
        ),
    )

    uow = make_uow(tenant_id)
    async with uow:
        item = await uow.stock.get(product.id, warehouse_id)
        assert item == Decimal("0")


async def test_seller_cannot_create_product_with_initial_stock(
    make_uow, hasher, registered_shop, random_phone, warehouse_id
):
    tenant_id, _, owner = registered_shop
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )
    with pytest.raises(AccessDeniedError):
        await CreateProductUseCase(make_uow(tenant_id)).execute(
            Actor(id=seller.id, role=seller.role),
            CreateProductCommand(
                name="Товар", unit_code="pcs",
                purchase_price=Decimal("10"), retail_price=Decimal("20"),
                initial_stock_warehouse_id=warehouse_id,
                initial_stock_quantity=Decimal("5"),
            ),
        )


async def test_create_product_rejects_duplicate_barcode(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    await CreateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateProductCommand(
            name="Первый товар", unit_code="pcs",
            purchase_price=Decimal("100"), retail_price=Decimal("150"),
            barcode="4600000000017",
        ),
    )

    with pytest.raises(DomainError):
        await CreateProductUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateProductCommand(
                name="Второй товар", unit_code="pcs",
                purchase_price=Decimal("200"), retail_price=Decimal("300"),
                barcode="4600000000017",
            ),
        )


async def test_create_product_rejects_barcode_reused_across_own_variants(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    with pytest.raises(DomainError):
        await CreateProductUseCase(make_uow(tenant_id)).execute(
            owner,
            CreateProductCommand(
                name="Футболка", unit_code="pcs",
                purchase_price=Decimal("300"), retail_price=Decimal("500"),
                variants=[
                    VariantInput(size="S", barcode="4600000000031"),
                    VariantInput(size="M", barcode="4600000000031"),
                ],
            ),
        )


def test_barcode_accepts_alphanumeric_codes():
    assert Barcode("4600000000017").value == "4600000000017"
    assert Barcode("ABC-abc-123").value == "ABC-ABC-123"
    assert Barcode(" code128-1 ").value == "CODE128-1"


def test_barcode_rejects_invalid_values():
    with pytest.raises(DomainError):
        Barcode("ab")  # короче 4 символов
    with pytest.raises(DomainError):
        Barcode("has space")
    with pytest.raises(DomainError):
        Barcode("плохой_штрихкод")  # кириллица и подчёркивание не допускаются


async def test_create_product_accepts_alphanumeric_barcode(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    product = await CreateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateProductCommand(
            name="Товар с внутренним кодом", unit_code="pcs",
            purchase_price=Decimal("100"), retail_price=Decimal("150"),
            barcode="ABC-123-45",
        ),
    )
    assert product.barcode.value == "ABC-123-45"

    async with make_uow(tenant_id) as uow:
        result = await uow.products.get_by_barcode(Barcode("abc-123-45"))
        assert result is not None
        assert result.id == product.id


async def test_update_product_rejects_duplicate_barcode_from_other_product(
    make_uow, registered_shop, create_product
):
    tenant_id, _, owner = registered_shop
    await CreateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateProductCommand(
            name="Товар А", unit_code="pcs",
            purchase_price=Decimal("100"), retail_price=Decimal("150"),
            barcode="4600000000048",
        ),
    )
    product_b = await create_product(tenant_id, name="Товар Б")

    with pytest.raises(DomainError):
        await UpdateProductUseCase(make_uow(tenant_id)).execute(
            owner,
            UpdateProductCommand(
                product_id=product_b.id,
                name=product_b.name,
                unit_code="pcs",
                purchase_price=Decimal("100"),
                retail_price=Decimal("150"),
                barcode="4600000000048",
            ),
        )


async def test_update_product_allows_keeping_its_own_barcode(make_uow, registered_shop, create_product):
    tenant_id, _, owner = registered_shop
    product = await CreateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateProductCommand(
            name="Товар с ШК", unit_code="pcs",
            purchase_price=Decimal("100"), retail_price=Decimal("150"),
            barcode="4600000000055",
        ),
    )

    updated = await UpdateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        UpdateProductCommand(
            product_id=product.id,
            name="Товар с ШК (обновлён)",
            unit_code="pcs",
            purchase_price=Decimal("100"),
            retail_price=Decimal("150"),
            barcode="4600000000055",
        ),
    )
    assert updated.barcode.value == "4600000000055"


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


def _test_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (800, 600), color=(10, 200, 120)).save(buffer, "PNG")
    return buffer.getvalue()


async def test_set_product_photo_updates_product(
    make_uow, registered_shop, create_product, tmp_path
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Плитка")
    storage = LocalFileStorage(tmp_path)

    updated = await SetProductPhotoUseCase(make_uow(tenant_id), storage).execute(
        owner, SetProductPhotoCommand(product.id, "photo.png", _test_png_bytes())
    )
    # оригинал переупаковывается в WebP, а не сохраняется как есть
    assert updated.photo.startswith("/uploads/") and updated.photo.endswith(".webp")
    full_path = tmp_path / updated.photo.removeprefix("/uploads/")
    assert full_path.exists()


async def test_set_product_photo_removes_previous_files(
    make_uow, registered_shop, create_product, tmp_path
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Плитка")
    storage = LocalFileStorage(tmp_path)

    first = await SetProductPhotoUseCase(make_uow(tenant_id), storage).execute(
        owner, SetProductPhotoCommand(product.id, "photo.png", _test_png_bytes())
    )
    first_full = tmp_path / first.photo.removeprefix("/uploads/")
    assert first_full.exists()

    second = await SetProductPhotoUseCase(make_uow(tenant_id), storage).execute(
        owner, SetProductPhotoCommand(product.id, "photo.png", _test_png_bytes())
    )
    # старый файл предыдущей загрузки не должен оставаться мусором на диске
    assert not first_full.exists()
    second_full = tmp_path / second.photo.removeprefix("/uploads/")
    assert second_full.exists()


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
        sales = await uow.sales.list()
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


def test_debt_requires_exactly_one_counterparty():
    both = Debt(id=None, amount=Money.of("100"), issued_at=date.today(), client_id=1, supplier_id=2)
    with pytest.raises(DomainError):
        both.validate()

    neither = Debt(id=None, amount=Money.of("100"), issued_at=date.today())
    with pytest.raises(DomainError):
        neither.validate()

    Debt(id=None, amount=Money.of("100"), issued_at=date.today(), client_id=1).validate()
    Debt(id=None, amount=Money.of("100"), issued_at=date.today(), supplier_id=1).validate()


def test_total_balance_sums_debts():
    debts = [
        Debt(id=1, amount=Money.of("500"), issued_at=date.today(), client_id=1),
        Debt(id=2, amount=Money.of("300"), issued_at=date.today(), client_id=1),
    ]
    assert total_balance(debts) == Money.of("800")
    assert total_balance([]) == Money.zero()


async def test_issue_supplier_debt_and_list_by_supplier(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    supplier = await CreateSupplierUseCase(make_uow(tenant_id)).execute(
        owner, CreateSupplierCommand(name="ООО СтройПоставка")
    )

    debt = await IssueSupplierDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueSupplierDebtCommand(supplier_id=supplier.id, amount=Decimal("50000"), note="партия цемента"),
    )
    assert debt.supplier_id == supplier.id
    assert debt.client_id is None
    assert debt.balance == Money.of("50000")

    async with make_uow(tenant_id) as uow:
        debts = await uow.debts.list_by_supplier(supplier.id)
        assert len(debts) == 1
        assert total_balance(debts) == Money.of("50000")


async def test_storekeeper_cannot_issue_supplier_debt(
    make_uow, hasher, registered_shop, random_phone
):
    tenant_id, _, owner = registered_shop
    supplier = await CreateSupplierUseCase(make_uow(tenant_id)).execute(
        owner, CreateSupplierCommand(name="Поставщик")
    )
    storekeeper = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Руслан", random_phone(), "secret123", Role.STOREKEEPER)
    )
    with pytest.raises(AccessDeniedError):
        await IssueSupplierDebtUseCase(make_uow(tenant_id)).execute(
            Actor(id=storekeeper.id, role=storekeeper.role),
            IssueSupplierDebtCommand(supplier_id=supplier.id, amount=Decimal("1000")),
        )


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


async def test_extend_debt_records_history_and_changes_due_date(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Тимур")
    )
    original_due = date.today() + timedelta(days=3)
    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(client_id=client.id, amount=Decimal("1000"), due_date=original_due),
    )

    new_due = date.today() + timedelta(days=10)
    updated = await ExtendDebtUseCase(make_uow(tenant_id)).execute(
        owner, ExtendDebtCommand(debt_id=debt.id, new_due_date=new_due, reason="попросил ещё неделю"),
    )
    assert updated.due_date == new_due
    assert len(updated.extensions) == 1
    assert updated.extensions[0].old_due_date == original_due
    assert updated.extensions[0].new_due_date == new_due
    assert updated.extensions[0].reason == "попросил ещё неделю"
    assert updated.extensions[0].author_id == owner.id


async def test_extend_debt_fails_when_already_closed(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Рустам")
    )
    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner, IssueDebtCommand(client_id=client.id, amount=Decimal("500")),
    )
    await RepayDebtUseCase(make_uow(tenant_id)).execute(
        owner, RepayDebtCommand(debt_id=debt.id, amount=Decimal("500")),
    )

    with pytest.raises(DomainError):
        await ExtendDebtUseCase(make_uow(tenant_id)).execute(
            owner,
            ExtendDebtCommand(debt_id=debt.id, new_due_date=date.today() + timedelta(days=5)),
        )


async def test_repay_debt_records_note_and_author(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Иса")
    )
    debt = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner, IssueDebtCommand(client_id=client.id, amount=Decimal("800")),
    )

    updated = await RepayDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        RepayDebtCommand(debt_id=debt.id, amount=Decimal("300"), note="занёс наличкой"),
    )
    assert updated.repayments[-1].note == "занёс наличкой"
    assert updated.repayments[-1].author_id == owner.id
    assert updated.balance == Money.of("500")


async def test_debt_status_transitions(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    client = await CreateClientUseCase(make_uow(tenant_id)).execute(
        owner, CreateClientCommand(name="Магомед")
    )

    active = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(client_id=client.id, amount=Decimal("100"), due_date=date.today() + timedelta(days=30)),
    )
    assert active.status() == DebtStatus.ACTIVE

    due_soon = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(client_id=client.id, amount=Decimal("100"), due_date=date.today() + timedelta(days=2)),
    )
    assert due_soon.status() == DebtStatus.DUE_SOON

    overdue = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(client_id=client.id, amount=Decimal("100"), due_date=date.today() - timedelta(days=1)),
    )
    assert overdue.status() == DebtStatus.OVERDUE

    partially_paid = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner,
        IssueDebtCommand(client_id=client.id, amount=Decimal("100"), due_date=date.today() + timedelta(days=30)),
    )
    partially_paid = await RepayDebtUseCase(make_uow(tenant_id)).execute(
        owner, RepayDebtCommand(debt_id=partially_paid.id, amount=Decimal("40")),
    )
    assert partially_paid.status() == DebtStatus.PARTIALLY_PAID

    closed = await IssueDebtUseCase(make_uow(tenant_id)).execute(
        owner, IssueDebtCommand(client_id=client.id, amount=Decimal("100")),
    )
    closed = await RepayDebtUseCase(make_uow(tenant_id)).execute(
        owner, RepayDebtCommand(debt_id=closed.id, amount=Decimal("100")),
    )
    assert closed.status() == DebtStatus.CLOSED


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
        ),
    )
    assert result.sale.total == Money.of("2000")  # доплата (3000 - 1000), не полная сумма
    assert result.order.status is OrderStatus.ISSUED
    assert result.order.sale_id == result.sale.id
    assert result.sale.order_id == order.id

    async with make_uow(tenant_id) as uow:
        assert await uow.stock.get(product.id, warehouse_id) == Decimal("0")
        assert await uow.stock.get_reserved(product.id, warehouse_id) == Decimal("0")
        debts = await uow.debts.list_by_client(client.id)
        assert len(debts) == 1
        assert debts[0].balance == Money.of("2000")
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
        "app.infrastructure.telegram.SqlAlchemyUnitOfWork",
        lambda tid: make_uow(tid) if tid is not None else make_uow(None),
    )

    sent = []

    class FakeNotifier:
        def send(self, chat_id: str, text: str) -> None:
            sent.append((chat_id, text))

    await _send_summaries_async(FakeNotifier())

    assert len(sent) == 1
    chat_id, text = sent[0]
    assert chat_id == "12345"
    assert "Продаж: 1" in text
    assert "Выручка: 200" in text
    assert "Прибыль: 100" in text


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


async def test_connect_telegram_owner_only(make_uow, registered_shop, hasher):
    tenant_id, _, owner = registered_shop

    tenant = await ConnectTelegramUseCase(make_uow(tenant_id)).execute(
        owner, ConnectTelegramCommand(chat_id="98765")
    )
    assert tenant.owner_telegram_chat_id == "98765"

    async with make_uow(tenant_id) as uow:
        stored = await uow.tenants.get(tenant_id)
    assert stored.owner_telegram_chat_id == "98765"

    manager = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand(name="Управляющий", phone="+79280009911",
                                      password="secret123", role=Role.MANAGER)
    )
    with pytest.raises(AccessDeniedError):
        await ConnectTelegramUseCase(make_uow(tenant_id)).execute(
            Actor(id=manager.id, role=manager.role), ConnectTelegramCommand(chat_id="11111")
        )


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

    updated = await UpdateEmployeeUseCase(make_uow(tenant_id)).execute(
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
        await UpdateEmployeeUseCase(make_uow(tenant_id)).execute(
            manager_actor,
            UpdateEmployeeCommand(
                user_id=seller.id, name="Зара", role=Role.MANAGER, is_active=True,
            ),
        )


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
