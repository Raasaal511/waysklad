from typing import Annotated

from fastapi import APIRouter, Depends, Response, UploadFile

from app.application.products.add_storefront_photo import AddStorefrontPhotoCommand
from app.application.products.delete_product import DeleteProductCommand
from app.application.products.import_excel import ImportProductsCommand
from app.application.products.import_preview import PreviewProductsCommand
from app.application.products.search_products import SearchProductsCommand
from app.application.products.set_product_photo import SetProductPhotoCommand
from app.application.products.set_storefront_photos import SetStorefrontPhotosCommand
from app.application.products.set_variant_photo import SetVariantPhotoCommand
from app.domain.catalog.barcode import Barcode
from app.infrastructure.export.products_export import (
    render_products_csv,
    render_products_pdf,
    render_products_xlsx,
)
from app.presentation.deps import (
    ActorDep,
    AddStorefrontPhotoDep,
    ApplyImportProductsDep,
    CreateCategoryDep,
    CreateProductDep,
    CreateUnitDep,
    DeleteProductDep,
    GenerateBarcodeDep,
    GetProductByBarcodeDep,
    GetProductDep,
    GetProductHistoryDep,
    GetProductsExportDataDep,
    ImportProductsDep,
    ListCategoriesDep,
    ListUnitsDep,
    PreviewImportProductsDep,
    SearchProductsDep,
    SetProductPhotoDep,
    SetStorefrontPhotosDep,
    SetVariantPhotoDep,
    ShowPurchaseDep,
    UpdateProductDep,
)
from app.presentation.audit.schemas import AuditEntryResponse
from app.presentation.products.schemas import (
    ApplyImportRequest,
    ApplyImportResponse,
    CategoryCreateRequest,
    CategoryResponse,
    GenerateBarcodeResponse,
    ImportProductsResponse,
    PreviewProductsResponse,
    ProductCreateRequest,
    ProductResponse,
    ProductsFilterParams,
    ProductUpdateRequest,
    SetStorefrontPhotosRequest,
    UnitCreateRequest,
    UnitResponse,
)

router = APIRouter(prefix="/products", tags=["products"])


async def _photo_command(product_id: int, file: UploadFile) -> SetProductPhotoCommand:
    return SetProductPhotoCommand(product_id, file.filename or "photo.jpg", await file.read())


async def _import_command(file: UploadFile) -> ImportProductsCommand:
    filename = (file.filename or "").lower()
    file_format = "csv" if filename.endswith(".csv") else "xlsx"
    return ImportProductsCommand(await file.read(), file_format=file_format)


async def _preview_command(file: UploadFile) -> PreviewProductsCommand:
    filename = (file.filename or "").lower()
    file_format = "csv" if filename.endswith(".csv") else "xlsx"
    return PreviewProductsCommand(await file.read(), file_format=file_format)


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


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: int, actor: ActorDep, use_case: DeleteProductDep) -> None:
    await use_case.execute(actor, DeleteProductCommand(product_id))


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


@router.post("/{product_id}/variants/{variant_id}/photo", status_code=201)
async def set_variant_photo(
    product_id: int,
    variant_id: int,
    actor: ActorDep,
    file: UploadFile,
    show_purchase: ShowPurchaseDep,
    use_case: SetVariantPhotoDep,
) -> ProductResponse:
    command = SetVariantPhotoCommand(
        product_id, variant_id, file.filename or "photo.jpg", await file.read()
    )
    product = await use_case.execute(actor, command)
    return ProductResponse.from_entity(product, show_purchase)


@router.post("/{product_id}/storefront-photos", status_code=201)
async def add_storefront_photo(
    product_id: int,
    actor: ActorDep,
    file: UploadFile,
    show_purchase: ShowPurchaseDep,
    use_case: AddStorefrontPhotoDep,
) -> ProductResponse:
    command = AddStorefrontPhotoCommand(product_id, file.filename or "photo.jpg", await file.read())
    product = await use_case.execute(actor, command)
    return ProductResponse.from_entity(product, show_purchase)


@router.put("/{product_id}/storefront-photos")
async def set_storefront_photos(
    product_id: int,
    body: SetStorefrontPhotosRequest,
    actor: ActorDep,
    show_purchase: ShowPurchaseDep,
    use_case: SetStorefrontPhotosDep,
) -> ProductResponse:
    command = SetStorefrontPhotosCommand(product_id, body.photos)
    product = await use_case.execute(actor, command)
    return ProductResponse.from_entity(product, show_purchase)


@router.post("/barcode/generate")
async def generate_barcode(
    actor: ActorDep, use_case: GenerateBarcodeDep
) -> GenerateBarcodeResponse:
    result = await use_case.execute(actor)
    return GenerateBarcodeResponse.from_result(result)


@router.post("/import", status_code=201)
async def import_products(
    actor: ActorDep, file: UploadFile, use_case: ImportProductsDep
) -> ImportProductsResponse:
    result = await use_case.execute(actor, await _import_command(file))
    return ImportProductsResponse.from_result(result)


@router.post("/import/preview")
async def preview_import_products(
    actor: ActorDep, file: UploadFile, use_case: PreviewImportProductsDep
) -> PreviewProductsResponse:
    result = await use_case.execute(actor, await _preview_command(file))
    return PreviewProductsResponse.from_result(result)


@router.post("/import/apply", status_code=201)
async def apply_import_products(
    body: ApplyImportRequest, actor: ActorDep, use_case: ApplyImportProductsDep
) -> ApplyImportResponse:
    result = await use_case.execute(actor, body.to_command())
    return ApplyImportResponse.from_result(result)


@router.post("/units", status_code=201)
async def create_unit(
    body: UnitCreateRequest, actor: ActorDep, use_case: CreateUnitDep
) -> UnitResponse:
    return UnitResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/units")
async def list_units(use_case: ListUnitsDep) -> list[UnitResponse]:
    return [UnitResponse.from_entity(u) for u in await use_case.execute()]


@router.post("/categories", status_code=201)
async def create_category(
    body: CategoryCreateRequest, actor: ActorDep, use_case: CreateCategoryDep
) -> CategoryResponse:
    return CategoryResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.get("/categories")
async def list_categories(use_case: ListCategoriesDep) -> list[CategoryResponse]:
    return [CategoryResponse.from_entity(c) for c in await use_case.execute()]


@router.get("")
async def search_products(
    response: Response,
    use_case: SearchProductsDep,
    show_purchase: ShowPurchaseDep,
    params: Annotated[ProductsFilterParams, Depends()],
) -> list[ProductResponse]:
    result = await use_case.execute(
        SearchProductsCommand(raw_params=params.to_raw_params(), warehouse_id=params.warehouse_id)
    )
    response.headers["X-Total-Count"] = str(result.total)
    return [ProductResponse.from_entity(p, show_purchase) for p in result.products]


@router.get("/export.xlsx")
async def export_products_xlsx(use_case: GetProductsExportDataDep, show_purchase: ShowPurchaseDep) -> Response:
    data = await use_case.execute()
    content = render_products_xlsx(data.products, data.category_names, show_purchase)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="tovary.xlsx"'},
    )


@router.get("/export.csv")
async def export_products_csv(use_case: GetProductsExportDataDep, show_purchase: ShowPurchaseDep) -> Response:
    data = await use_case.execute()
    content = render_products_csv(data.products, data.category_names, show_purchase)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tovary.csv"'},
    )


@router.get("/export.pdf")
async def export_products_pdf(use_case: GetProductsExportDataDep, show_purchase: ShowPurchaseDep) -> Response:
    data = await use_case.execute()
    content = render_products_pdf(data.shop_name, data.products, data.category_names, show_purchase)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="tovary.pdf"'},
    )


@router.get("/barcode/{barcode}")
async def get_by_barcode(
    barcode: str, use_case: GetProductByBarcodeDep, show_purchase: ShowPurchaseDep
) -> ProductResponse | None:
    product = await use_case.execute(Barcode(barcode))
    return ProductResponse.from_entity(product, show_purchase) if product else None


@router.get("/{product_id}")
async def get_product(
    product_id: int, use_case: GetProductDep, show_purchase: ShowPurchaseDep
) -> ProductResponse:
    return ProductResponse.from_entity(await use_case.execute(product_id), show_purchase)


@router.get("/{product_id}/history")
async def get_product_history(
    product_id: int, use_case: GetProductHistoryDep
) -> list[AuditEntryResponse]:
    entries = await use_case.execute(product_id)
    return [AuditEntryResponse.from_entity(e) for e in entries]
