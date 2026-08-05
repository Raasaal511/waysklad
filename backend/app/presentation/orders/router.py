from fastapi import APIRouter

from app.domain.identity.permissions import Permission
from app.presentation.deps import ActorDep, ChangeOrderStatusDep, CreateOrderDep, UowDep
from app.presentation.deps.auth import require_permission
from app.presentation.orders.schemas import (
    ChangeStatusRequest,
    OrderCreateRequest,
    OrderResponse,
)

router = APIRouter(prefix="/orders", tags=["orders"])
_view = require_permission(Permission.ORDERS_VIEW)


@router.post("", status_code=201)
async def create_order(
    body: OrderCreateRequest, actor: ActorDep, use_case: CreateOrderDep
) -> OrderResponse:
    return OrderResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.patch("/{order_id}/status")
async def change_status(
    order_id: int, body: ChangeStatusRequest, actor: ActorDep, use_case: ChangeOrderStatusDep
) -> OrderResponse:
    return OrderResponse.from_entity(await use_case.execute(actor, body.to_command(order_id)))


@router.get("", dependencies=[_view])
async def list_active_orders(uow: UowDep) -> list[OrderResponse]:
    async with uow:
        return [OrderResponse.from_entity(o) for o in await uow.orders.list_active()]


@router.get("/{order_id}", dependencies=[_view])
async def get_order(order_id: int, uow: UowDep) -> OrderResponse:
    async with uow:
        return OrderResponse.from_entity(await uow.orders.get(order_id))
