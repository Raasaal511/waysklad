"""Чаты покупателя по JWT (A8).

Старый путь — доступ к чату по access_token заявки: у кого ссылка, тот и
внутри. Он остаётся для тех, кто заказывал без регистрации, но для личного
кабинета не годится: чтобы показать список диалогов, пришлось бы отдать на
фронт токены всех заявок разом, а это ключи от всех чатов в одном ответе.

Здесь доступ доказывается аккаунтом: сервер сам проверяет, что заявка
принадлежит этому покупателю (StorefrontRequest.customer_id).
"""

from dataclasses import dataclass
from datetime import datetime

from app.domain.common.exceptions import AccessDeniedError, NotFoundError
from app.domain.notifications.entities import NotificationKind
from app.domain.identity.entities import Role
from app.domain.storefront.entities import MessageAuthor, StorefrontMessage
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.application.storefront.send_message import _publish_message
from app.application.tasks.notify import notify_user
from app.domain.common.notifier import INotifier


@dataclass(frozen=True)
class CustomerChatSummary:
    """Строка списка диалогов: заявка + превью последнего сообщения."""

    request_id: int
    shop_name: str
    shop_slug: str
    shop_logo: str
    request_status: str
    last_message: str = ""
    last_message_at: datetime | None = None
    last_message_from_shop: bool = False
    messages_count: int = 0


async def _load_own_request(session_factory, customer_id: int, request_id: int):
    """Заявка покупателя или отказ — общая проверка для всех операций чата."""
    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as uow:
        request = await uow.storefront_requests.get_by_id_any_tenant(request_id)
        if request is None:
            raise NotFoundError("Заявка не найдена")
        if request.customer_id != customer_id:
            # именно 403, а не 404: заявка существует, просто чужая
            raise AccessDeniedError("Это не ваша заявка")
        return request


class ListCustomerChatsUseCase:
    """Список диалогов по всем заказам покупателя — вкладка «Чаты» в профиле.

    Как и в списке заказов, обращения группируются по магазинам: сообщения
    лежат в tenant-scoped таблицах, поэтому на магазин приходится один заход,
    а не по одному на заявку.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, customer_id: int) -> list[CustomerChatSummary]:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as uow:
            requests = await uow.storefront_requests.list_by_customer(customer_id)
            tenants = {t.id: t for t in await uow.tenants.list_all()}

        by_tenant: dict[int, list] = {}
        for request in requests:
            if request.tenant_id is not None:
                by_tenant.setdefault(request.tenant_id, []).append(request)

        summaries: list[CustomerChatSummary] = []
        for tenant_id, tenant_requests in by_tenant.items():
            tenant = tenants.get(tenant_id)
            async with SqlAlchemyUnitOfWork(
                tenant_id, session_factory=self._session_factory
            ) as tenant_uow:
                for request in tenant_requests:
                    messages = await tenant_uow.storefront_messages.list_by_request(request.id)
                    if not messages:
                        # диалог не начинали — в списке чатов ему нечего показать
                        continue
                    last = messages[-1]
                    summaries.append(
                        CustomerChatSummary(
                            request_id=request.id,
                            shop_name=tenant.name if tenant else "",
                            shop_slug=(tenant.slug or "") if tenant else "",
                            shop_logo=tenant.logo if tenant else "",
                            request_status=request.status.value,
                            last_message=last.text,
                            last_message_at=last.created_at,
                            last_message_from_shop=last.author != MessageAuthor.CUSTOMER,
                            messages_count=len(messages),
                        )
                    )

        # свежие диалоги сверху; без даты (теоретически) — в конец
        summaries.sort(key=lambda s: (s.last_message_at is not None, s.last_message_at), reverse=True)
        return summaries


class ListCustomerChatMessagesUseCase:
    """Переписка по одной заявке покупателя."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, customer_id: int, request_id: int) -> list[StorefrontMessage]:
        request = await _load_own_request(self._session_factory, customer_id, request_id)
        async with SqlAlchemyUnitOfWork(
            request.tenant_id, session_factory=self._session_factory
        ) as uow:
            return await uow.storefront_messages.list_by_request(request.id)


class SendCustomerChatMessageUseCase:
    """Покупатель пишет в чат своей заявки из личного кабинета.

    Уведомление магазину — то же самое, что и у входа по токену: продавцу
    неважно, каким путём пришло сообщение.
    """

    def __init__(self, session_factory, notifier: INotifier | None):
        self._session_factory = session_factory
        self._notifier = notifier

    async def execute(
        self, customer_id: int, request_id: int, text: str
    ) -> StorefrontMessage:
        request = await _load_own_request(self._session_factory, customer_id, request_id)

        async with SqlAlchemyUnitOfWork(
            request.tenant_id, session_factory=self._session_factory
        ) as uow:
            message = StorefrontMessage(
                id=None, request_id=request.id, author=MessageAuthor.CUSTOMER, text=text
            )
            message.validate()
            await uow.storefront_messages.add(message)
            # тот же WS-канал, что и у входа по токену: открытый чат магазина
            # должен увидеть сообщение независимо от способа отправки
            await _publish_message(message)

            recipients = [
                u
                for u in await uow.users.list_by_tenant()
                if u.role in (Role.OWNER, Role.MANAGER)
            ]
            for user in recipients:
                await notify_user(
                    uow,
                    self._notifier,
                    user_id=user.id,
                    kind=NotificationKind.STOREFRONT_MESSAGE,
                    text=f"Новое сообщение от «{request.customer_name}» по заявке с витрины",
                    link="/orders/storefront-requests",
                    entity_id=request.id,
                )

            await uow.commit()
            return message
