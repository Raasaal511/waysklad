from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.presentation.deps import (
    ActorDep,
    MarkAllNotificationsReadDep,
    MarkNotificationReadDep,
    SessionFactoryDep,
    UowDep,
)
from app.presentation.deps.auth import get_current_user_ws
from app.presentation.notifications.schemas import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
)
from app.infrastructure.ws_broadcast import broadcaster

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: str, factory: SessionFactoryDep) -> None:
    """Push-канал взамен периодического опроса GET /notifications. Браузер не
    может выставить заголовок Authorization при открытии сокета — токен
    передаётся query-параметром (?token=...)."""
    user = await get_current_user_ws(token, factory)
    await websocket.accept()
    broadcaster.registry.add(user.id, websocket)
    try:
        while True:
            # клиент ничего не обязан присылать — просто держим соединение
            # открытым и ждём either новое сообщение (игнорируем), либо разрыв
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.registry.remove(user.id, websocket)


@router.get("")
async def list_notifications(actor: ActorDep, uow: UowDep) -> NotificationListResponse:
    async with uow:
        items = await uow.notifications.list_for_user(actor.id)
        unread = await uow.notifications.unread_count(actor.id)
        return NotificationListResponse(
            items=[NotificationResponse.from_entity(n) for n in items], unread=unread
        )


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int, actor: ActorDep, use_case: MarkNotificationReadDep
) -> NotificationResponse:
    return NotificationResponse.from_entity(await use_case.execute(actor, notification_id))


@router.post("/read-all")
async def mark_all_read(actor: ActorDep, use_case: MarkAllNotificationsReadDep) -> MarkAllReadResponse:
    return MarkAllReadResponse(marked=await use_case.execute(actor))
