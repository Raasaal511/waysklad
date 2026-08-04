from typing import Annotated

from fastapi import APIRouter, Depends

from app.domain.catalog.barcode import Barcode
from app.domain.catalog.entities import Product
from app.domain.identity.permissions import Permission, has_permission
from app.presentation.deps import (
    ActorDep,
    CreateProductDep,
    CurrentUserDep,
    UowDep,
    UpdateProductDep,
)
from app.presentation.products.schemas import (
    ProductCreateRequest,
    ProductResponse,
    ProductUpdateRequest,
)

router = APIRouter(prefix="/products", tags=["products"])


def _show_purchase(user: CurrentUserDep) -> bool:
    return has_permission(user.role, Permission.PURCHASE_PRICES_VIEW)


ShowPurchaseDep = Annotated[bool, Depends(_show_purchase)]


def _maybe(product: Product | None, show_purchase: bool) -> ProductResponse | None:
    return ProductResponse.from_entity(product, show_purchase) if product else None


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
