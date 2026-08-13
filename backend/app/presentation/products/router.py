from fastapi import APIRouter, Response, UploadFile

from app.application.products.import_excel import ImportProductsCommand
from app.application.products.set_product_photo import SetProductPhotoCommand
from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Product
from app.infrastructure.products_export import (
    render_products_csv,
    render_products_pdf,
    render_products_xlsx,
)
from app.presentation.deps import (
    ActorDep,
    CreateCategoryDep,
    CreateProductDep,
    CreateUnitDep,
    ImportProductsDep,
    SetProductPhotoDep,
    ShowPurchaseDep,
    UowDep,
    UpdateProductDep,
)
from app.presentation.audit.schemas import AuditEntryResponse
from app.presentation.products.schemas import (
    CategoryCreateRequest,
    CategoryResponse,
    ImportProductsResponse,
    ProductCreateRequest,
    ProductResponse,
    ProductUpdateRequest,
    UnitCreateRequest,
    UnitResponse,
)

router = APIRouter(prefix="/products", tags=["products"])


def _maybe(product: Product | None, show_purchase: bool) -> ProductResponse | None:
    return ProductResponse.from_entity(product, show_purchase) if product else None


async def _photo_command(product_id: int, file: UploadFile) -> SetProductPhotoCommand:
    return SetProductPhotoCommand(product_id, file.filename or "photo.jpg", await file.read())


async def _import_command(file: UploadFile) -> ImportProductsCommand:
    filename = (file.filename or "").lower()
    file_format = "csv" if filename.endswith(".csv") else "xlsx"
    return ImportProductsCommand(await file.read(), file_format=file_format)


async def _load_export_data(uow: UowDep) -> tuple[list[Product], dict[int, str], str]:
    async with uow:
        products = await uow.products.search_all()
        categories = await uow.categories.list()
        tenant = await uow.tenants.get(uow.tenant_id)
        category_names = {c.id: c.name for c in categories}
        return products, category_names, tenant.name


@router.post("", status_code=201)
async def create_product(
    body: ProductCreateRequest,
    actor: ActorDep,
    show_purchase: ShowPurchaseDep,
    use_case: CreateProductDep,
) -> ProductResponse:
    product = await use_case.execute(actor, body.to_command())
    return ProductResponse.from_entity(product, show_purchase)


@router.put("/{product_id}")
async def update_product(
    product_id: int,
    body: ProductUpdateRequest,
    actor: ActorDep,
    show_purchase: ShowPurchaseDep,
    use_case: UpdateProductDep,
) -> ProductResponse:
    product = await use_case.execute(actor, body.to_command(product_id))
    return ProductResponse.from_entity(product, show_purchase)


@router.post("/{product_id}/photo", status_code=201)
async def set_product_photo(
    product_id: int,
    actor: ActorDep,
    file: UploadFile,
    show_purchase: ShowPurchaseDep,
    use_case: SetProductPhotoDep,
) -> ProductResponse:
    product = await use_case.execute(actor, await _photo_command(product_id, file))
    return ProductResponse.from_entity(product, show_purchase)


@router.post("/import", status_code=201)
async def import_products(
    actor: ActorDep, file: UploadFile, use_case: ImportProductsDep
) -> ImportProductsResponse:
    result = await use_case.execute(actor, await _import_command(file))
    return ImportProductsResponse.from_result(result)


@router.post("/units", status_code=201)
async def create_unit(
    body: UnitCreateRequest, actor: ActorDep, use_case: CreateUnitDep
) -> UnitResponse:
    return UnitResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/units")
async def list_units(uow: UowDep) -> list[UnitResponse]:
    async with uow:
        return [UnitResponse.from_entity(u) for u in await uow.units.list()]


@router.post("/categories", status_code=201)
async def create_category(
    body: CategoryCreateRequest, actor: ActorDep, use_case: CreateCategoryDep
) -> CategoryResponse:
    return CategoryResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/categories")
async def list_categories(uow: UowDep) -> list[CategoryResponse]:
    async with uow:
        return [CategoryResponse.from_entity(c) for c in await uow.categories.list()]


@router.get("")
async def search_products(
    response: Response,
    uow: UowDep,
    show_purchase: ShowPurchaseDep,
    query: str = "",
    limit: int = 50,
    offset: int = 0,
    category_id: int | None = None,
    sort: str = "name",
) -> list[ProductResponse]:
    async with uow:
        products, total = await uow.products.search(
            query, limit=limit, offset=offset, category_id=category_id, sort=sort
        )
        response.headers["X-Total-Count"] = str(total)
        return [ProductResponse.from_entity(p, show_purchase) for p in products]


@router.get("/export.xlsx")
async def export_products_xlsx(uow: UowDep, show_purchase: ShowPurchaseDep) -> Response:
    products, category_names, _ = await _load_export_data(uow)
    content = render_products_xlsx(products, category_names, show_purchase)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="tovary.xlsx"'},
    )


@router.get("/export.csv")
async def export_products_csv(uow: UowDep, show_purchase: ShowPurchaseDep) -> Response:
    products, category_names, _ = await _load_export_data(uow)
    content = render_products_csv(products, category_names, show_purchase)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tovary.csv"'},
    )


@router.get("/export.pdf")
async def export_products_pdf(uow: UowDep, show_purchase: ShowPurchaseDep) -> Response:
    products, category_names, shop_name = await _load_export_data(uow)
    content = render_products_pdf(shop_name, products, category_names, show_purchase)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="tovary.pdf"'},
    )


@router.get("/barcode/{barcode}")
async def get_by_barcode(
    barcode: str, uow: UowDep, show_purchase: ShowPurchaseDep
) -> ProductResponse | None:
    async with uow:
        return _maybe(await uow.products.get_by_barcode(Barcode(barcode)), show_purchase)


@router.get("/{product_id}")
async def get_product(
    product_id: int, uow: UowDep, show_purchase: ShowPurchaseDep
) -> ProductResponse:
    async with uow:
        return ProductResponse.from_entity(
            await uow.products.get(product_id), show_purchase
        )


@router.get("/{product_id}/history")
async def get_product_history(product_id: int, uow: UowDep) -> list[AuditEntryResponse]:
    async with uow:
        entries = await uow.audit.list_by_entity("product", product_id)
        return [AuditEntryResponse.from_entity(e) for e in entries]
