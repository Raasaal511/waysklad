from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.infrastructure.rate_limit import limiter
from app.presentation.deps import GetStorefrontCatalogDep
from app.presentation.storefront.schemas import StorefrontCatalogParams, StorefrontCatalogResponse

router = APIRouter(prefix="/storefront", tags=["storefront"])


@router.get("/{slug}")
@limiter.limit("60/minute")
async def get_storefront_catalog(
    request: Request,
    slug: str,
    params: Annotated[StorefrontCatalogParams, Depends()],
    use_case: GetStorefrontCatalogDep,
) -> StorefrontCatalogResponse:
    result = await use_case.execute(params.to_command(slug))
    if result is None:
        raise HTTPException(status_code=404, detail="Витрина не найдена")
    return StorefrontCatalogResponse.from_result(result)
