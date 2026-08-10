from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.domain.audit.entities import AuditEntry
from app.domain.common.exceptions import AccessDeniedError, DomainError
from app.domain.common.uow import IUnitOfWork
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor, Permission, require

EDIT_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class EditSaleCommand:
    sale_id: int
    client_id: int | None
    note: str


class EditSaleUseCase:
    """Правка клиента и заметки задним числом — не товарных позиций и не сумм.

    Продавец может править только свои продажи и только в первые 24 часа после
    продажи. Владелец/управляющий не ограничены по времени.
    """

    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def execute(self, actor: Actor, cmd: EditSaleCommand) -> None:
        require(actor, Permission.SALES_EDIT)

        async with self._uow as uow:
            sale = await uow.sales.get(cmd.sale_id)
            if sale.deleted_at is not None:
                raise DomainError(f"Продажа {sale.id} удалена")

            if actor.role not in (Role.OWNER, Role.MANAGER):
                if sale.seller_id != actor.id:
                    raise AccessDeniedError("Нельзя редактировать чужую продажу")
                if datetime.now(timezone.utc) - sale.created_at > EDIT_WINDOW:
                    raise AccessDeniedError("Продажу можно редактировать только в первые 24 часа")

            if cmd.client_id is not None:
                await uow.clients.get(cmd.client_id)

            sale.client_id = cmd.client_id
            sale.note = cmd.note
            await uow.sales.save(sale)

            await uow.audit.add(
                AuditEntry.record(actor, "sale.edit", sale.id, client_id=cmd.client_id)
            )
            await uow.commit()
