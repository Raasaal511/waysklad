from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.infrastructure.rate_limit import limiter
from app.presentation.deps import ListMarketplaceProductsDep
from app.presentation.marketplace.schemas import MarketplaceCatalogParams, MarketplaceCatalogResponse

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("/products")
@limiter.limit("60/minute")
async def list_marketplace_products(
    request: Request,
    params: Annotated[MarketplaceCatalogParams, Depends()],
    use_case: ListMarketplaceProductsDep,
) -> MarketplaceCatalogResponse:
    result = await use_case.execute(params.to_command())
    return MarketplaceCatalogResponse.from_result(result)
