from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.application.marketplace.get_product import GetMarketplaceProductCommand
from app.application.marketplace.list_cities import ListCitiesCommand
from app.application.marketplace.list_platform_categories import ListPlatformCategoriesCommand
from app.application.marketplace.suggest import SuggestCommand
from app.infrastructure.rate_limit import limiter
from app.presentation.deps import (
    GetMarketplaceHomeDep,
    GetMarketplaceProductDep,
    ListCitiesDep,
    ListMarketplaceProductsDep,
    ListPlatformCategoriesDep,
    ListShopsDep,
    SuggestDep,
)
from app.presentation.marketplace.schemas import (
    CityResponse,
    ListCitiesResponse,
    ListPlatformCategoriesResponse,
    MarketplaceCatalogParams,
    MarketplaceCatalogResponse,
    MarketplaceHomeParams,
    MarketplaceHomeResponse,
    MarketplaceProductPageResponse,
    MarketplaceShopsParams,
    MarketplaceShopsResponse,
    PlatformCategoryPublicResponse,
    SuggestResponse,
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


@router.get("/home")
@limiter.limit("300/minute")
async def get_marketplace_home(
    request: Request,
    params: Annotated[MarketplaceHomeParams, Depends()],
    use_case: GetMarketplaceHomeDep,
) -> MarketplaceHomeResponse:
    result = await use_case.execute(params.to_command())
    return MarketplaceHomeResponse.from_result(result)


@router.get("/shops")
@limiter.limit("300/minute")
async def list_marketplace_shops(
    request: Request,
    params: Annotated[MarketplaceShopsParams, Depends()],
    use_case: ListShopsDep,
) -> MarketplaceShopsResponse:
    result = await use_case.execute(params.to_command())
    return MarketplaceShopsResponse.from_result(result)


@router.get("/suggest")
@limiter.limit("120/minute")
async def marketplace_suggest(
    request: Request, use_case: SuggestDep, q: str = "", city: str | None = None
) -> SuggestResponse:
    result = await use_case.execute(SuggestCommand(query=q, city=city))
    return SuggestResponse.from_result(result)
