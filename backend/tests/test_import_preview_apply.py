from io import BytesIO

import openpyxl
import pytest

from app.application.auth.create_employee import CreateEmployeeCommand, CreateEmployeeUseCase
from app.application.products.apply_import import (
    ApplyImportCommand,
    ApplyImportRow,
    ApplyProductImportUseCase,
)
from app.application.products.create_category import CreateCategoryCommand, CreateCategoryUseCase
from app.application.products.import_preview import PreviewProductsCommand, PreviewProductsUseCase
from app.domain.catalog.barcode import Barcode
from app.domain.common.exceptions import AccessDeniedError
from app.domain.common.money import Money
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor


def _build_workbook(rows: list[tuple]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "Название",
            "Артикул",
            "Штрихкод",
            "Ед.изм.",
            "Категория",
            "Закупочная цена",
            "Розничная цена",
            "Маржа",
            "Мин.остаток",
        ]
    )
    for row in rows:
        # Маржа (индекс 7) — вычисляемая колонка, для теста несущественна, но
        # позиция должна быть занята, иначе сдвинутся Закуп./Розн./Мин.остаток
        padded = list(row[:7]) + [""] + list(row[7:])
        sheet.append(padded)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


async def test_preview_no_match_rows_default_to_create(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    file_bytes = _build_workbook([("Новый товар", "", "", "pcs", "", 100, 150, 0)])
    result = await PreviewProductsUseCase(make_uow(tenant_id)).execute(
        owner, PreviewProductsCommand(file_bytes)
    )
    assert len(result.rows) == 1
    assert result.rows[0].status == "no_match"
    assert result.rows[0].candidates == []


async def test_preview_matches_by_sku(make_uow, registered_shop, create_product):
    tenant_id, _, owner = registered_shop
    await create_product(tenant_id, name="Старое название", sku="SKU-1")
    file_bytes = _build_workbook([("Новое название", "SKU-1", "", "pcs", "", 100, 150, 0)])
    result = await PreviewProductsUseCase(make_uow(tenant_id)).execute(
        owner, PreviewProductsCommand(file_bytes)
    )
    assert result.rows[0].status == "match"
    assert result.rows[0].candidates[0].matched_by == "sku"
    assert result.rows[0].candidates[0].product.sku == "SKU-1"


async def test_preview_matches_by_barcode_priority_over_sku(make_uow, registered_shop, create_product):
    tenant_id, _, owner = registered_shop
    product_a = await create_product(
        tenant_id, name="Товар А", sku="SKU-A", barcode=Barcode("4600000000001")
    )
    await create_product(tenant_id, name="Товар Б", sku="SKU-B")
    file_bytes = _build_workbook(
        [("Строка файла", "SKU-B", "4600000000001", "pcs", "", 100, 150, 0)]
    )
    result = await PreviewProductsUseCase(make_uow(tenant_id)).execute(
        owner, PreviewProductsCommand(file_bytes)
    )
    row = result.rows[0]
    assert row.status == "ambiguous_match"
    assert len(row.candidates) == 2
    assert row.candidates[0].matched_by == "barcode"
    assert row.candidates[0].product.id == product_a.id


async def test_preview_parse_error_row_excluded_from_matching(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    file_bytes = _build_workbook([("Товар с ошибкой", "", "", "pcs", "", "не число", 150, 0)])
    result = await PreviewProductsUseCase(make_uow(tenant_id)).execute(
        owner, PreviewProductsCommand(file_bytes)
    )
    assert result.rows[0].parse_error is not None
    assert result.rows[0].status == "no_match"


async def test_preview_empty_name_is_parse_error(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    # строка со значением только в первой колонке (пробел) — единственный способ
    # проверить парсинг пустого имени: реальная пустая ячейка отфильтровывается ещё
    # на уровне чтения xlsx (`if row and row[0]`), до попадания в _parse_row
    file_bytes = _build_workbook([("   ", "", "", "pcs", "", 100, 150, 0)])
    result = await PreviewProductsUseCase(make_uow(tenant_id)).execute(
        owner, PreviewProductsCommand(file_bytes)
    )
    assert result.rows[0].parse_error is not None


async def test_preview_recognizes_unit_by_russian_name(make_uow, registered_shop):
    """Экспорт пишет unit.name ('шт', 'г'...), не unit.code — импорт того же
    файла обратно не должен падать с "Неизвестная единица измерения"."""
    tenant_id, _, owner = registered_shop
    file_bytes = _build_workbook([("Чай листовой", "SKU-T", "", "г", "", 100, 150, 0)])
    result = await PreviewProductsUseCase(make_uow(tenant_id)).execute(
        owner, PreviewProductsCommand(file_bytes)
    )
    assert result.rows[0].parse_error is None
    assert result.rows[0].unit_code == "g"


async def test_preview_recognizes_category_by_name(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    category = await CreateCategoryUseCase(make_uow(tenant_id)).execute(
        owner, CreateCategoryCommand(name="Напитки")
    )
    file_bytes = _build_workbook([("Чай листовой", "SKU-T", "", "pcs", "Напитки", 100, 150, 0)])
    result = await PreviewProductsUseCase(make_uow(tenant_id)).execute(
        owner, PreviewProductsCommand(file_bytes)
    )
    assert result.rows[0].category_id == category.id


async def test_preview_unknown_category_name_leaves_category_unset(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    file_bytes = _build_workbook([("Чай листовой", "SKU-T", "", "pcs", "Нет такой категории", 100, 150, 0)])
    result = await PreviewProductsUseCase(make_uow(tenant_id)).execute(
        owner, PreviewProductsCommand(file_bytes)
    )
    assert result.rows[0].category_id is None


async def test_apply_create_action(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    result = await ApplyProductImportUseCase(make_uow(tenant_id)).execute(
        owner,
        ApplyImportCommand(
            rows=[
                ApplyImportRow(
                    client_row_id="row-2",
                    action="create",
                    name="Новый товар",
                    unit_code="pcs",
                    purchase_price=100,
                    retail_price=150,
                )
            ]
        ),
    )
    assert result.created == 1
    assert result.updated == 0
    assert result.skipped == 0
    assert result.errors == []
    async with make_uow(tenant_id) as uow:
        products = await uow.products.search_all()
    assert any(p.name == "Новый товар" for p in products)


async def test_apply_update_action_overwrites_existing_product(make_uow, registered_shop, create_product):
    tenant_id, _, owner = registered_shop
    product = await create_product(tenant_id, name="Старое имя", retail_price=Money.of("100"))
    result = await ApplyProductImportUseCase(make_uow(tenant_id)).execute(
        owner,
        ApplyImportCommand(
            rows=[
                ApplyImportRow(
                    client_row_id="row-2",
                    action="update",
                    name="Новое имя",
                    unit_code="pcs",
                    purchase_price=100,
                    retail_price=200,
                    existing_product_id=product.id,
                )
            ]
        ),
    )
    assert result.updated == 1
    assert result.errors == []
    async with make_uow(tenant_id) as uow:
        updated = await uow.products.get(product.id)
    assert updated.name == "Новое имя"
    assert updated.retail_price.amount == 200


async def test_apply_skip_action_does_not_create(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    result = await ApplyProductImportUseCase(make_uow(tenant_id)).execute(
        owner,
        ApplyImportCommand(
            rows=[ApplyImportRow(client_row_id="row-2", action="skip", name="Пропущенный")]
        ),
    )
    assert result.skipped == 1
    assert result.created == 0
    async with make_uow(tenant_id) as uow:
        products = await uow.products.search_all()
    assert not any(p.name == "Пропущенный" for p in products)


async def test_apply_update_with_missing_product_id_reports_row_error(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    result = await ApplyProductImportUseCase(make_uow(tenant_id)).execute(
        owner,
        ApplyImportCommand(
            rows=[
                ApplyImportRow(
                    client_row_id="row-2",
                    action="update",
                    name="Без id",
                    unit_code="pcs",
                    purchase_price=100,
                    retail_price=150,
                    existing_product_id=None,
                )
            ]
        ),
    )
    assert result.updated == 0
    assert len(result.errors) == 1
    assert result.errors[0].client_row_id == "row-2"


async def test_apply_update_nonexistent_product_id_reports_row_error(make_uow, registered_shop):
    tenant_id, _, owner = registered_shop
    result = await ApplyProductImportUseCase(make_uow(tenant_id)).execute(
        owner,
        ApplyImportCommand(
            rows=[
                ApplyImportRow(
                    client_row_id="row-2",
                    action="update",
                    name="Не существует",
                    unit_code="pcs",
                    purchase_price=100,
                    retail_price=150,
                    existing_product_id=999999,
                ),
                ApplyImportRow(
                    client_row_id="row-3",
                    action="create",
                    name="Штатная строка",
                    unit_code="pcs",
                    purchase_price=100,
                    retail_price=150,
                ),
            ]
        ),
    )
    assert len(result.errors) == 1
    assert result.errors[0].client_row_id == "row-2"
    assert result.created == 1


async def test_seller_cannot_preview_or_apply_import(make_uow, hasher, registered_shop, random_phone):
    tenant_id, _, owner = registered_shop
    seller = await CreateEmployeeUseCase(make_uow(tenant_id), hasher).execute(
        owner, CreateEmployeeCommand("Зара", random_phone(), "secret123", Role.SELLER)
    )
    seller_actor = Actor(id=seller.id, role=seller.role)
    file_bytes = _build_workbook([("Товар", "", "", "pcs", 1, 2, 0)])

    with pytest.raises(AccessDeniedError):
        await PreviewProductsUseCase(make_uow(tenant_id)).execute(
            seller_actor, PreviewProductsCommand(file_bytes)
        )

    with pytest.raises(AccessDeniedError):
        await ApplyProductImportUseCase(make_uow(tenant_id)).execute(
            seller_actor,
            ApplyImportCommand(
                rows=[ApplyImportRow(client_row_id="row-2", action="create", name="Товар")]
            ),
        )
