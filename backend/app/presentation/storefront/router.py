from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.application.storefront.reject_request import RejectStorefrontRequestCommand
from app.domain.identity.permissions import Permission
from app.infrastructure.rate_limit import limiter
from app.presentation.deps import (
    AcceptStorefrontRequestDep,
    ActorDep,
    CreateStorefrontRequestDep,
    GetStorefrontCatalogDep,
    ListStorefrontRequestsDep,
    RejectStorefrontRequestDep,
    UowDep,
)
from app.presentation.deps.auth import require_permission
from app.presentation.orders.schemas import OrderResponse
from app.presentation.storefront.schemas import (
    AcceptStorefrontRequestRequest,
    CreateStorefrontRequestRequest,
    StorefrontCatalogParams,
    StorefrontCatalogResponse,
    StorefrontRequestResponse,
)

router = APIRouter(prefix="/storefront", tags=["storefront"])

_view = require_permission(Permission.ORDERS_VIEW)
_manage = require_permission(Permission.ORDERS_MANAGE)


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


@router.post("/{slug}/requests", status_code=201)
@limiter.limit("20/hour")
async def create_storefront_request(
    request: Request,
    slug: str,
    body: CreateStorefrontRequestRequest,
    use_case: CreateStorefrontRequestDep,
) -> StorefrontRequestResponse:
    result = await use_case.execute(body.to_command(slug))
    if result is None:
        raise HTTPException(status_code=404, detail="Витрина не найдена")
    return StorefrontRequestResponse.from_entity(result)


@router.get("/requests/new", dependencies=[_view])
async def list_new_storefront_requests(
    actor: ActorDep, use_case: ListStorefrontRequestsDep
) -> list[StorefrontRequestResponse]:
    requests = await use_case.execute(actor)
    return [StorefrontRequestResponse.from_entity(r) for r in requests]


@router.get("/requests/{request_id}", dependencies=[_view])
async def get_storefront_request(request_id: int, uow: UowDep) -> StorefrontRequestResponse:
    async with uow:
        return StorefrontRequestResponse.from_entity(await uow.storefront_requests.get(request_id))


@router.post("/requests/{request_id}/accept", dependencies=[_manage])
async def accept_storefront_request(
    request_id: int,
    body: AcceptStorefrontRequestRequest,
    actor: ActorDep,
    use_case: AcceptStorefrontRequestDep,
) -> OrderResponse:
    order = await use_case.execute(actor, body.to_command(request_id))
    return OrderResponse.from_entity(order)


@router.post("/requests/{request_id}/reject", dependencies=[_manage])
async def reject_storefront_request(
    request_id: int, actor: ActorDep, use_case: RejectStorefrontRequestDep
) -> StorefrontRequestResponse:
    result = await use_case.execute(actor, RejectStorefrontRequestCommand(request_id=request_id))
    return StorefrontRequestResponse.from_entity(result)
