from fastapi import APIRouter

from app.domain.identity.permissions import Permission
from app.presentation.audit.schemas import AuditEntryResponse
from app.presentation.deps import (
    ActorDep,
    CancelOrderDep,
    ChangeOrderStatusDep,
    CreateOrderDep,
    IssueOrderDep,
    UowDep,
    UpdateOrderDep,
)
from app.presentation.deps.auth import require_permission
from app.presentation.orders.schemas import (
    CancelOrderRequest,
    ChangeStatusRequest,
    IssueOrderRequest,
    IssueOrderResponse,
    OrderCreateRequest,
    OrderResponse,
    OrderUpdateRequest,
)

router = APIRouter(prefix="/orders", tags=["orders"])
_view = require_permission(Permission.ORDERS_VIEW)


@router.post("", status_code=201)
async def create_order(
    body: OrderCreateRequest, actor: ActorDep, use_case: CreateOrderDep
) -> OrderResponse:
    return OrderResponse.from_entity(await use_case.execute(actor, body.to_command()))


@router.patch("/{order_id}")
async def update_order(
    order_id: int, body: OrderUpdateRequest, actor: ActorDep, use_case: UpdateOrderDep
) -> OrderResponse:
    return OrderResponse.from_entity(await use_case.execute(actor, body.to_command(order_id)))


@router.patch("/{order_id}/status")
async def change_status(
    order_id: int, body: ChangeStatusRequest, actor: ActorDep, use_case: ChangeOrderStatusDep
) -> OrderResponse:
    return OrderResponse.from_entity(await use_case.execute(actor, body.to_command(order_id)))


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int, body: CancelOrderRequest, actor: ActorDep, use_case: CancelOrderDep
) -> OrderResponse:
    return OrderResponse.from_entity(await use_case.execute(actor, body.to_command(order_id)))


@router.post("/{order_id}/issue")
async def issue_order(
    order_id: int, body: IssueOrderRequest, actor: ActorDep, use_case: IssueOrderDep
) -> IssueOrderResponse:
    return IssueOrderResponse.from_result(await use_case.execute(actor, body.to_command(order_id)))


@router.get("", dependencies=[_view])
async def list_active_orders(uow: UowDep) -> list[OrderResponse]:
    async with uow:
        return [OrderResponse.from_entity(o) for o in await uow.orders.list_active()]


@router.get("/completed", dependencies=[_view])
async def list_completed_orders(uow: UowDep) -> list[OrderResponse]:
    async with uow:
        return [OrderResponse.from_entity(o) for o in await uow.orders.list_completed()]


@router.get("/{order_id}", dependencies=[_view])
async def get_order(order_id: int, uow: UowDep) -> OrderResponse:
    async with uow:
        return OrderResponse.from_entity(await uow.orders.get(order_id))


@router.get("/{order_id}/history", dependencies=[_view])
async def get_order_history(order_id: int, uow: UowDep) -> list[AuditEntryResponse]:
    async with uow:
        entries = await uow.audit.list_by_entity("order", order_id)
        return [AuditEntryResponse.from_entity(e) for e in entries]
