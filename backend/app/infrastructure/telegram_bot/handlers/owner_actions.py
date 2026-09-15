"""Действия владельца прямо из уведомления в Telegram (см. app/application/
tasks/notify.py, INotifier.send_with_buttons) — дополнение к работе через
панель, не замена: кто не подключил Telegram (Tenant.owner_telegram_chat_id
пусто), продолжает принимать/отклонять заявки как раньше, целиком в панели.
"""

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.application.storefront.reject_request import (
    RejectStorefrontRequestCommand,
    RejectStorefrontRequestUseCase,
)
from app.domain.common.exceptions import DomainError
from app.domain.identity.entities import Role
from app.domain.identity.permissions import Actor
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

router = Router(name="owner_actions")


@router.callback_query(F.data.startswith("reject_request:"))
async def reject_request(callback: CallbackQuery, session_factory) -> None:
    request_id = int(callback.data.split(":", 1)[1])
    chat_id = str(callback.from_user.id)

    async with SqlAlchemyUnitOfWork(None, session_factory=session_factory) as public_uow:
        tenant = await public_uow.tenants.get_by_owner_chat_id(chat_id)
    if tenant is None:
        await callback.answer("Этот чат не подключён ни к одному магазину", show_alert=True)
        return

    async with SqlAlchemyUnitOfWork(tenant.id, session_factory=session_factory) as uow:
        owner = next(
            (u for u in await uow.users.list_by_tenant() if u.role is Role.OWNER), None
        )
    if owner is None:
        await callback.answer("Владелец магазина не найден", show_alert=True)
        return

    actor = Actor(id=owner.id, role=owner.role)
    use_case = RejectStorefrontRequestUseCase(
        SqlAlchemyUnitOfWork(tenant.id, session_factory=session_factory)
    )
    try:
        await use_case.execute(actor, RejectStorefrontRequestCommand(request_id=request_id))
    except DomainError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await callback.answer("Заявка отклонена")
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("❌ Заявка отклонена из Telegram.")
