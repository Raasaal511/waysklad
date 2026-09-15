from dataclasses import dataclass

from app.domain.common.exceptions import NotFoundError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.storefront.entities import StorefrontMessage
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class ListStorefrontMessagesCommand:
    access_token: str


class ListStorefrontMessagesUseCase:
    """Покупатель читает переписку своей заявки по токену — без авторизации."""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def execute(self, cmd: ListStorefrontMessagesCommand) -> list[StorefrontMessage]:
        async with SqlAlchemyUnitOfWork(None, session_factory=self._session_factory) as public_uow:
            request = await public_uow.storefront_requests.get_by_token(cmd.access_token)
        if request is None:
            raise NotFoundError("Заявка не найдена")

        async with SqlAlchemyUnitOfWork(request.tenant_id, session_factory=self._session_factory) as uow:
            return await uow.storefront_messages.list_by_request(request.id)


class ListStaffStorefrontMessagesUseCase:
    """Сотрудник читает переписку заявки из панели управления."""

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, request_id: int) -> list[StorefrontMessage]:
        require(actor, Permission.ORDERS_VIEW)
        async with self._uow as uow:
            await uow.storefront_requests.get(request_id)  # 404 если чужая/не существует
            return await uow.storefront_messages.list_by_request(request_id)
