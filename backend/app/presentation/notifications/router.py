from fastapi import APIRouter

from app.presentation.deps import (
    ActorDep,
    MarkAllNotificationsReadDep,
    MarkNotificationReadDep,
    UowDep,
)
from app.presentation.notifications.schemas import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


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
