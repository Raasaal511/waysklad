from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from app.application.storefront.list_messages import ListStorefrontMessagesCommand
from app.application.storefront.reject_request import RejectStorefrontRequestCommand
from app.domain.identity.permissions import Permission
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.rate_limit import limiter
from app.infrastructure.ws_broadcast import broadcaster, storefront_request_channel
from app.presentation.deps import (
    AcceptStorefrontRequestDep,
    ActorDep,
    CreateStorefrontRequestDep,
    GetStorefrontCatalogDep,
    ListStaffStorefrontMessagesDep,
    ListStorefrontMessagesDep,
    ListStorefrontRequestsDep,
    RejectStorefrontRequestDep,
    SendStaffStorefrontMessageDep,
    SendStorefrontMessageDep,
    SessionFactoryDep,
    UowDep,
)
from app.presentation.deps.auth import require_permission
from app.presentation.orders.schemas import OrderResponse
from app.presentation.storefront.schemas import (
    AcceptStorefrontRequestRequest,
    CreateStorefrontRequestRequest,
    SendStorefrontMessageRequest,
    StorefrontCatalogParams,
    StorefrontCatalogResponse,
    StorefrontMessageResponse,
    StorefrontRequestCreatedResponse,
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
) -> StorefrontRequestCreatedResponse:
    result = await use_case.execute(body.to_command(slug))
    if result is None:
        raise HTTPException(status_code=404, detail="Витрина не найдена")
    return StorefrontRequestCreatedResponse.from_entity(result)


@router.get("/requests/new", dependencies=[_view])
async def list_new_storefront_requests(
    actor: ActorDep, use_case: ListStorefrontRequestsDep
) -> list[StorefrontRequestResponse]:
    requests = await use_case.execute(actor)
    return [StorefrontRequestResponse.from_entity(r) for r in requests]


# Чат заявки: покупатель (публично, по access_token). Регистрируется ДО
# /requests/{request_id} ниже, иначе FastAPI сматчит "chat" как request_id.


@router.get("/requests/chat")
@limiter.limit("60/minute")
async def get_storefront_chat(
    request: Request, token: str, use_case: ListStorefrontMessagesDep
) -> list[StorefrontMessageResponse]:
    messages = await use_case.execute(ListStorefrontMessagesCommand(access_token=token))
    return [StorefrontMessageResponse.from_entity(m) for m in messages]


@router.post("/requests/chat", status_code=201)
@limiter.limit("60/minute")
async def send_storefront_chat_message(
    request: Request, token: str, body: SendStorefrontMessageRequest, use_case: SendStorefrontMessageDep
) -> StorefrontMessageResponse:
    message = await use_case.execute(body.to_command(token))
    return StorefrontMessageResponse.from_entity(message)


@router.websocket("/requests/chat/ws")
async def storefront_chat_ws(websocket: WebSocket, token: str, factory: SessionFactoryDep) -> None:
    """Покупатель без аккаунта получает сообщения сотрудника в реальном времени —
    доступ по тому же access_token, что и REST (нет JWT, нет аккаунта)."""
    async with SqlAlchemyUnitOfWork(None, session_factory=factory) as public_uow:
        chat_request = await public_uow.storefront_requests.get_by_token(token)
    if chat_request is None:
        await websocket.close(code=4404)
        return

    channel = storefront_request_channel(chat_request.id)
    await websocket.accept()
    broadcaster.registry.add(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.registry.remove(channel, websocket)


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


@router.get("/requests/{request_id}/chat", dependencies=[_view])
async def get_staff_storefront_chat(
    request_id: int, actor: ActorDep, use_case: ListStaffStorefrontMessagesDep
) -> list[StorefrontMessageResponse]:
    messages = await use_case.execute(actor, request_id)
    return [StorefrontMessageResponse.from_entity(m) for m in messages]


@router.post("/requests/{request_id}/chat", status_code=201, dependencies=[_view])
async def send_staff_storefront_chat_message(
    request_id: int,
    body: SendStorefrontMessageRequest,
    actor: ActorDep,
    use_case: SendStaffStorefrontMessageDep,
) -> StorefrontMessageResponse:
    message = await use_case.execute(actor, body.to_staff_command(request_id))
    return StorefrontMessageResponse.from_entity(message)
