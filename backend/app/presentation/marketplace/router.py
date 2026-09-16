from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.application.marketplace.get_product import GetMarketplaceProductCommand
from app.infrastructure.rate_limit import limiter
from app.presentation.deps import GetMarketplaceProductDep, ListMarketplaceProductsDep
from app.presentation.marketplace.schemas import (
    MarketplaceCatalogParams,
    MarketplaceCatalogResponse,
    MarketplaceProductPageResponse,
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


@router.get("/products/{product_id}")
@limiter.limit("300/minute")
async def get_marketplace_product(
    request: Request, product_id: int, use_case: GetMarketplaceProductDep
) -> MarketplaceProductPageResponse:
    result = await use_case.execute(GetMarketplaceProductCommand(product_id=product_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return MarketplaceProductPageResponse.from_result(result)
