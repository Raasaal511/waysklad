from fastapi import APIRouter, UploadFile

from app.application.products.import_excel import ImportProductsCommand
from app.application.products.set_product_photo import SetProductPhotoCommand
from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Product
from app.presentation.deps import (
    ActorDep,
    CreateProductDep,
    CreateUnitDep,
    ImportProductsDep,
    SetProductPhotoDep,
    ShowPurchaseDep,
    UowDep,
    UpdateProductDep,
)
from app.presentation.products.schemas import (
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
    return ImportProductsCommand(await file.read())


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


@router.get("")
async def search_products(
    uow: UowDep, show_purchase: ShowPurchaseDep, query: str = ""
) -> list[ProductResponse]:
    async with uow:
        return [
            ProductResponse.from_entity(p, show_purchase)
            for p in await uow.products.search(query)
        ]


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
