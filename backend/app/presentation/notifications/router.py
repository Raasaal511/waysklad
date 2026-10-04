from fastapi import APIRouter, Response, WebSocket, WebSocketDisconnect

from app.application.notifications.push_subscriptions import SubscribePushCommand

from app.presentation.deps import (
    ActorDep,
    ListNotificationsDep,
    MarkAllNotificationsReadDep,
    MarkNotificationReadDep,
    PushSenderDep,
    SendTestPushDep,
    SessionFactoryDep,
    SubscribePushDep,
    UnsubscribePushDep,
)
from app.presentation.deps.auth import get_current_user_ws
from app.presentation.notifications.schemas import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
    PushKeyResponse,
    PushSubscriptionRequest,
    PushTestResponse,
    PushEndpointRequest,
)
from app.infrastructure.notifications.ws_broadcast import broadcaster, user_channel

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: str, factory: SessionFactoryDep) -> None:
    """Push-канал взамен периодического опроса GET /notifications. Браузер не
    может выставить заголовок Authorization при открытии сокета — токен
    передаётся query-параметром (?token=...)."""
    user = await get_current_user_ws(token, factory)
    channel = user_channel(user.id)
    await websocket.accept()
    await broadcaster.track_connect(channel, websocket)
    try:
        while True:
            # клиент ничего не обязан присылать — просто держим соединение
            # открытым и ждём either новое сообщение (игнорируем), либо разрыв
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.track_disconnect(channel, websocket)


@router.get("")
async def list_notifications(actor: ActorDep, use_case: ListNotificationsDep) -> NotificationListResponse:
    result = await use_case.execute(actor)
    return NotificationListResponse(
        items=[NotificationResponse.from_entity(n) for n in result.items], unread=result.unread
    )


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int, actor: ActorDep, use_case: MarkNotificationReadDep
) -> NotificationResponse:
    return NotificationResponse.from_entity(await use_case.execute(actor, notification_id))


@router.post("/read-all")
async def mark_all_read(actor: ActorDep, use_case: MarkAllNotificationsReadDep) -> MarkAllReadResponse:
    return MarkAllReadResponse(marked=await use_case.execute(actor))


@router.get("/push/key")
async def push_key(actor: ActorDep, sender: PushSenderDep) -> PushKeyResponse:
    """Публичный ключ VAPID для pushManager.subscribe(); null — push выключен."""
    return PushKeyResponse(public_key=sender.public_key)


@router.put("/push/subscription", status_code=204)
async def push_subscribe(
    body: PushSubscriptionRequest, actor: ActorDep, use_case: SubscribePushDep
) -> Response:
    await use_case.execute(
        actor,
        SubscribePushCommand(endpoint=body.endpoint, p256dh=body.keys.p256dh, auth=body.keys.auth),
    )
    return Response(status_code=204)


@router.post("/push/unsubscribe", status_code=204)
async def push_unsubscribe(
    body: PushEndpointRequest, actor: ActorDep, use_case: UnsubscribePushDep
) -> Response:
    # 204 и когда подписки не было: устройство уже в нужном состоянии
    await use_case.execute(actor, body.endpoint)
    return Response(status_code=204)


@router.post("/push/test")
async def push_test(
    body: PushEndpointRequest, actor: ActorDep, use_case: SendTestPushDep
) -> PushTestResponse:
    return PushTestResponse(delivered=await use_case.execute(actor, body.endpoint))
