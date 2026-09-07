from dataclasses import dataclass

from app.application.storefront.reservation import release_request_reservation
from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.permissions import Actor, Permission, require
from app.domain.storefront.entities import StorefrontRequest, StorefrontRequestStatus


@dataclass(frozen=True)
class RejectStorefrontRequestCommand:
    request_id: int


class RejectStorefrontRequestUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: RejectStorefrontRequestCommand) -> StorefrontRequest:
        require(actor, Permission.ORDERS_MANAGE)

        async with self._uow as uow:
            request = await uow.storefront_requests.get(cmd.request_id)
            if request.status != StorefrontRequestStatus.NEW:
                raise DomainError("Заявка уже обработана")
            if not request.reservation_released:
                await release_request_reservation(uow, request)
            request.reject()
            await uow.storefront_requests.save(request)
            await uow.audit.add(
                AuditEntry.record(actor, "storefront_request.reject", request.id)
            )
            await uow.commit()
            return request
