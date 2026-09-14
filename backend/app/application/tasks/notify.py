import asyncio

from decimal import Decimal

from app.domain.common.notifier import INotifier
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role
from app.domain.notifications.entities import Notification, NotificationKind
from app.infrastructure.notifications.ws_broadcast import broadcaster, user_channel


async def notify_user(
    uow: IUnitOfWork,
    notifier: INotifier | None,
    *,
    user_id: int,
    kind: NotificationKind,
    text: str,
    link: str = "",
    entity_id: int | None = None,
    snapshot_value: Decimal | None = None,
) -> None:
    """In-app уведомление — всем; WebSocket-push — всем с открытым соединением;
    Telegram — только владельцу (один чат на магазин)."""
    saved = await uow.notifications.add(
        Notification(
            id=None, user_id=user_id, kind=kind, text=text, link=link,
            entity_id=entity_id, snapshot_value=snapshot_value,
        )
    )
    try:
        await broadcaster.publish(
            user_channel(user_id),
            {
                "id": saved.id,
                "kind": kind.value,
                "text": text,
                "link": link,
                "entity_id": entity_id,
            },
        )
    except Exception:
        pass  # WS-push не должен валить бизнес-операцию — клиент досчитает через REST

    if notifier is None:
        return
    recipient = await uow.users.get(user_id)
    if recipient.role is not Role.OWNER:
        return
    tenant = await uow.tenants.get(uow.tenant_id)
    if not tenant.owner_telegram_chat_id:
        return
    try:
        if kind is NotificationKind.STOREFRONT_REQUEST_NEW and entity_id is not None:
            # "Принять" не влезает в одну кнопку (нужен выбор склада и даты
            # готовности) — остаётся через панель; "Отклонить" однозначно,
            # можно прямо в чате. Кто не подключил Telegram — работает как
            # раньше, целиком через панель, эта кнопка только ускоряет путь.
            await asyncio.to_thread(
                notifier.send_with_buttons,
                tenant.owner_telegram_chat_id,
                text,
                [("❌ Отклонить заявку", f"reject_request:{entity_id}")],
            )
        else:
            await asyncio.to_thread(notifier.send, tenant.owner_telegram_chat_id, text)
    except Exception:
        pass  # уведомление не должно валить бизнес-операцию
