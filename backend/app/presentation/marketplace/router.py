from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.application.marketplace.get_product import GetMarketplaceProductCommand
from app.application.marketplace.list_cities import ListCitiesCommand
from app.application.marketplace.list_platform_categories import ListPlatformCategoriesCommand
from app.infrastructure.rate_limit import limiter
from app.presentation.deps import (
    GetMarketplaceProductDep,
    ListCitiesDep,
    ListMarketplaceProductsDep,
    ListPlatformCategoriesDep,
)
from app.presentation.marketplace.schemas import (
    CityResponse,
    ListCitiesResponse,
    ListPlatformCategoriesResponse,
    MarketplaceCatalogParams,
    MarketplaceCatalogResponse,
    MarketplaceProductPageResponse,
    PlatformCategoryPublicResponse,
)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("/products")
@limiter.limit("300/minute")
async def list_marketplace_products(
    request: Request,
    params: Annotated[MarketplaceCatalogParams, Depends()],
    use_case: ListMarketplaceProductsDep,
) -> MarketplaceCatalogResponse:
    result = await use_case.execute(params.to_command())
    return MarketplaceCatalogResponse.from_result(result)


@router.get("/categories")
@limiter.limit("300/minute")
async def list_marketplace_categories(
    request: Request, use_case: ListPlatformCategoriesDep, city: str | None = None
) -> ListPlatformCategoriesResponse:
    result = await use_case.execute(ListPlatformCategoriesCommand(city=city))
    return ListPlatformCategoriesResponse(
        categories=[PlatformCategoryPublicResponse.from_item(i) for i in result.items]
    )


@router.get("/cities")
@limiter.limit("300/minute")
async def list_marketplace_cities(
    request: Request, use_case: ListCitiesDep
) -> ListCitiesResponse:
    result = await use_case.execute(ListCitiesCommand())
    return ListCitiesResponse(
        cities=[CityResponse(name=c.name, shops_count=c.shops_count) for c in result.cities]
    )


@router.get("/products/{product_id}")
@limiter.limit("300/minute")
async def get_marketplace_product(
    request: Request, product_id: int, use_case: GetMarketplaceProductDep
) -> MarketplaceProductPageResponse:
    result = await use_case.execute(GetMarketplaceProductCommand(product_id=product_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return MarketplaceProductPageResponse.from_result(result)
