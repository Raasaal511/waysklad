from decimal import Decimal
from io import BytesIO
import openpyxl
import pytest
from PIL import Image
from app.application.auth.create_employee import CreateEmployeeCommand, CreateEmployeeUseCase
from app.application.auth.login import LoginCommand, LoginUseCase
from app.application.auth.register_shop import RegisterShopCommand, RegisterShopUseCase
from app.application.inventory.common import LineInput
from app.application.inventory.receive_goods import ReceiveGoodsCommand, ReceiveGoodsUseCase
from app.application.products.create_product import (
    CreateProductCommand,
    CreateProductUseCase,
    VariantInput,
)
from app.application.products.add_storefront_photo import (
    AddStorefrontPhotoCommand,
    AddStorefrontPhotoUseCase,
)
from app.application.products.create_unit import CreateUnitCommand, CreateUnitUseCase
from app.application.products.delete_product import DeleteProductCommand, DeleteProductUseCase
from app.application.products.import_excel import ImportProductsCommand, ImportProductsUseCase
from app.application.products.set_product_photo import (
    SetProductPhotoCommand,
    SetProductPhotoUseCase,
)
from app.application.products.set_variant_photo import (
    SetVariantPhotoCommand,
    SetVariantPhotoUseCase,
)
from app.application.products.update_product import (
    UpdateProductCommand,
    UpdateProductUseCase,
    UpdateVariantInput,
)
from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import ProductVariant
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
from app.infrastructure.files import LocalFileStorage


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


def _test_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (800, 600), color=(10, 200, 120)).save(buffer, "PNG")
    return buffer.getvalue()


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
            phone=random_phone(), personal_data_consent=True, password="secret123",
        )
    )
    second = await RegisterShopUseCase(make_uow(), hasher).execute(
        RegisterShopCommand(
            shop_name="Магазин Беркат", owner_name="Муса",
            phone=random_phone(), personal_data_consent=True, password="secret123",
        )
    )
    assert first.shop_slug == "magazin-berkat"
    assert second.shop_slug == "magazin-berkat-2"


async def test_duplicate_phone_registration_fails(make_uow, hasher, registered_shop):
    _, phone, _ = registered_shop
    with pytest.raises(DomainError):
        await RegisterShopUseCase(make_uow(), hasher).execute(
            RegisterShopCommand("Другой", "Муса", phone, "secret123", personal_data_consent=True)
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


async def test_delete_product_without_activity_removes_it_completely(
    make_uow, registered_shop, create_product
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Ода")

    await DeleteProductUseCase(make_uow(tenant_id)).execute(
        owner, DeleteProductCommand(product.id)
    )

    async with make_uow(tenant_id) as uow:
        products, _ = await uow.products.list_filtered({})
        assert product.id not in [p.id for p in products]
        # товар без единого движения — удаляется физически, не просто скрывается
        with pytest.raises(NotFoundError):
            await uow.products.get(product.id)


async def test_delete_product_with_activity_soft_deletes_it(
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

    await DeleteProductUseCase(make_uow(tenant_id)).execute(
        owner, DeleteProductCommand(product.id)
    )

    async with make_uow(tenant_id) as uow:
        products, _ = await uow.products.list_filtered({})
        assert product.id not in [p.id for p in products]
        # с историей (тут — приёмка) — не стирается, доступна по прямому запросу
        still_there = await uow.products.get(product.id)
        assert still_there.name == "Духи 6мл"


async def test_seller_cannot_delete_product(
    make_uow, hasher, registered_shop, create_product, random_phone
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Ода")
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )
    with pytest.raises(AccessDeniedError):
        await DeleteProductUseCase(make_uow(tenant_id)).execute(
            Actor(id=seller.id, role=seller.role), DeleteProductCommand(product.id)
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


async def test_create_product_sets_variant_price(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    product = await CreateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        CreateProductCommand(
            name="Носки", unit_code="pcs",
            purchase_price=Decimal("50"), retail_price=Decimal("100"),
            variants=[
                VariantInput(size="M", price=Decimal("90")),
                VariantInput(size="L"),
            ],
        ),
    )
    by_size = {v.size: v for v in product.variants}
    assert by_size["M"].price == Money.of("90")
    # цена не задана — вариант не переопределяет retail_price товара
    assert by_size["L"].price is None


async def test_update_product_changes_variant_price(make_uow, registered_shop, create_product):
    tenant_id, _, owner = registered_shop
    product = await create_product(
        tenant_id, name="Носки",
        variants=[ProductVariant(id=None, size="M", price=Money.of("90"))],
    )
    variant_id = product.variants[0].id

    updated = await UpdateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        UpdateProductCommand(
            product_id=product.id, name=product.name, unit_code="pcs",
            purchase_price=Decimal("50"), retail_price=Decimal("100"),
            variants=[UpdateVariantInput(id=variant_id, size="M", price=Decimal("80"))],
        ),
    )
    assert updated.variants[0].price == Money.of("80")


async def test_set_variant_photo_updates_variant(make_uow, registered_shop, create_product, tmp_path):
    tenant_id, _, owner = registered_shop
    product = await create_product(
        tenant_id, name="Носки", variants=[ProductVariant(id=None, size="M")]
    )
    variant_id = product.variants[0].id
    storage = LocalFileStorage(tmp_path)

    updated = await SetVariantPhotoUseCase(make_uow(tenant_id), storage).execute(
        owner, SetVariantPhotoCommand(product.id, variant_id, "photo.png", _test_png_bytes())
    )
    variant = next(v for v in updated.variants if v.id == variant_id)
    assert variant.photo.startswith("/uploads/") and variant.photo.endswith(".webp")
    assert (tmp_path / variant.photo.removeprefix("/uploads/")).exists()


async def test_set_variant_photo_rejects_unknown_variant(
    make_uow, registered_shop, create_product, tmp_path
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Носки")
    with pytest.raises(DomainError):
        await SetVariantPhotoUseCase(make_uow(tenant_id), LocalFileStorage(tmp_path)).execute(
            owner, SetVariantPhotoCommand(product.id, 999999, "photo.png", _test_png_bytes())
        )


async def test_update_product_persists_description(make_uow, registered_shop, create_product):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Кружка")

    updated = await UpdateProductUseCase(make_uow(tenant_id)).execute(
        owner,
        UpdateProductCommand(
            product_id=product.id, name=product.name, unit_code="pcs",
            purchase_price=Decimal("50"), retail_price=Decimal("100"),
            description="Керамическая кружка 350 мл",
        ),
    )
    assert updated.description == "Керамическая кружка 350 мл"

    async with make_uow(tenant_id) as uow:
        fresh = await uow.products.get(product.id)
        assert fresh.description == "Керамическая кружка 350 мл"


async def test_add_storefront_photo_accumulates_across_calls(
    make_uow, registered_shop, create_product, tmp_path
):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Кружка")
    storage = LocalFileStorage(tmp_path)
    use_case = AddStorefrontPhotoUseCase(make_uow(tenant_id), storage)

    first = await use_case.execute(
        owner, AddStorefrontPhotoCommand(product.id, "a.png", _test_png_bytes())
    )
    assert len(first.storefront_photos) == 1

    second = await use_case.execute(
        owner, AddStorefrontPhotoCommand(product.id, "b.png", _test_png_bytes())
    )
    # каждый вызов добавляет фото к уже сохранённым, а не перезаписывает список
    assert len(second.storefront_photos) == 2
    assert second.storefront_photos[0] == first.storefront_photos[0]

    async with make_uow(tenant_id) as uow:
        fresh = await uow.products.get(product.id)
        assert len(fresh.storefront_photos) == 2
