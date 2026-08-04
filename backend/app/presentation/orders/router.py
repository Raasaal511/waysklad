from fastapi import APIRouter

from app.presentation.deps import ActorDep, ChangeOrderStatusDep, CreateOrderDep, UowDep
from app.presentation.orders.schemas import (
    ChangeStatusRequest,
    OrderCreateRequest,
    OrderResponse,
)

router = APIRouter(prefix="/orders", tags=["orders"])


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


@router.get("")
async def list_active_orders(uow: UowDep) -> list[OrderResponse]:
    async with uow:
        return [OrderResponse.from_entity(o) for o in await uow.orders.list_active()]
