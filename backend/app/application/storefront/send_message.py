import asyncio
from dataclasses import dataclass

from app.application.tasks.notify import notify_user
from app.domain.common.exceptions import NotFoundError
from app.domain.common.notifier import INotifier
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.notifications.entities import NotificationKind
from app.domain.storefront.entities import MessageAuthor, StorefrontMessage
from app.infrastructure.config import settings
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.notifications.ws_broadcast import broadcaster, storefront_request_channel


async def _publish_message(message: StorefrontMessage) -> None:
    try:
        await broadcaster.publish(
            storefront_request_channel(message.request_id),
            {
                "id": message.id,
                "request_id": message.request_id,
                "author": message.author.value,
                "text": message.text,
            },
        )
    except Exception:
        pass  # WS-push не должен валить бизнес-операцию


@dataclass(frozen=True)
class SendStorefrontMessageCommand:
    access_token: str
    text: str


class SendStorefrontMessageUseCase:
    """Покупатель без аккаунта пишет в чат своей заявки — доступ по
    непредсказуемому токену, выданному при создании заявки."""

    def __init__(self, session_factory, notifier: INotifier | None):
        self._session_factory = session_factory
        self._notifier = notifier

    async def execute(self, cmd: SendStorefrontMessageCommand) -> StorefrontMessage:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            request = await public_uow.storefront_requests.get_by_token(cmd.access_token)
        if request is None:
            raise NotFoundError("Заявка не найдена")

        async with SqlAlchemyUnitOfWork(request.tenant_id, session_factory=self._session_factory) as uow:
            message = StorefrontMessage(
                id=None, request_id=request.id, author=MessageAuthor.CUSTOMER, text=cmd.text
            )
            message.validate()
            await uow.storefront_messages.add(message)
            await _publish_message(message)

            recipients = [
                u for u in await uow.users.list_by_tenant() if u.role in (Role.OWNER, Role.MANAGER)
            ]
            for user in recipients:
                await notify_user(
                    uow, self._notifier,
                    user_id=user.id,
                    kind=NotificationKind.STOREFRONT_MESSAGE,
                    text=f"Новое сообщение от «{request.customer_name}» по заявке с витрины",
                    link="/orders/storefront-requests",
                    entity_id=request.id,
                )

            await uow.commit()
            return message


@dataclass(frozen=True)
class SendStaffStorefrontMessageCommand:
    request_id: int
    text: str


class SendStaffStorefrontMessageUseCase:
    """Сотрудник (owner/manager/…) отвечает в чат заявки из панели управления.

    Покупателю с привязанным Telegram уходит короткое уведомление — чтобы
    ответ магазина не терялся, пока он не откроет чат на сайте.
    """

    def __init__(self, uow: IUnitOfWork, notifier: INotifier | None = None):
        self._uow = uow
        self._notifier = notifier

    async def execute(self, actor: Actor, cmd: SendStaffStorefrontMessageCommand) -> StorefrontMessage:
        require(actor, Permission.ORDERS_VIEW)

        async with self._uow as uow:
            request = await uow.storefront_requests.get(cmd.request_id)
            message = StorefrontMessage(
                id=None, request_id=cmd.request_id, author=MessageAuthor.STAFF, text=cmd.text
            )
            message.validate()
            await uow.storefront_messages.add(message)
            await _publish_message(message)

            customer_chat_id = ""
            shop_name = ""
            shop_slug = ""
            if request.customer_id is not None:
                customer = await uow.customers.get(request.customer_id)
                customer_chat_id = customer.telegram_chat_id or ""
                tenant = await uow.tenants.get(uow.tenant_id)
                shop_name = tenant.name
                shop_slug = tenant.slug or ""

            await uow.commit()

        if self._notifier and customer_chat_id:
            preview = cmd.text.strip()
            if len(preview) > 120:
                preview = preview[:117] + "…"
            path = f"/account/chats/{cmd.request_id}"
            link = f"{settings.public_base_url.rstrip('/')}{path}" if settings.public_base_url and path else path
            text = (
                f"Магазин «{shop_name}» ответил по заказу:\n{preview}"
                + (f"\n\nОткрыть чат: {link}" if link else "")
            )
            try:
                await asyncio.to_thread(self._notifier.send, customer_chat_id, text)
            except Exception:
                pass

        return message
