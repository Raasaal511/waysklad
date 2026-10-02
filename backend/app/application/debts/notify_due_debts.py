"""Персональные уведомления владельцу/управляющему о сроках долгов.

Запускается тем же cron-процессом, что и ежедневная Telegram-сводка:
    docker compose exec backend python -m app.application.debts.notify_due_debts
Или как функция internal_notify_due_debts() из другого скрипта/шедулера.
"""

import asyncio
from datetime import date

from app.domain.common.notifier import INotifier
from app.domain.debts.entities import Debt, DebtStatus
from app.domain.identity.entities import Role
from app.domain.notifications.entities import NotificationKind
from app.infrastructure.background import drain
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


def _debt_text(debt: Debt, who: str) -> str:
    action = "просрочен" if debt.status() is DebtStatus.OVERDUE else "истекает"
    due = debt.due_date.strftime("%d.%m") if debt.due_date else "—"
    return f"Долг {who} на {debt.balance} — срок {due} ({action})"


async def _notify_tenant(uow: SqlAlchemyUnitOfWork, notifier: INotifier) -> None:
    from app.application.tasks.notify import notify_user

    debts = await uow.debts.list_active()
    urgent = [d for d in debts if d.status() in (DebtStatus.OVERDUE, DebtStatus.DUE_SOON)]
    if not urgent:
        return

    recipients = [u for u in await uow.users.list_by_tenant() if u.role in (Role.OWNER, Role.MANAGER)]
    if not recipients:
        return

    for debt in urgent:
        if debt.client_id is not None:
            client = await uow.clients.get(debt.client_id)
            who = f"клиента «{client.name}»"
        else:
            supplier = await uow.suppliers.get(debt.supplier_id)
            who = f"поставщику «{supplier.name}»"
        kind = NotificationKind.DEBT_OVERDUE if debt.status() is DebtStatus.OVERDUE else NotificationKind.DEBT_DUE_SOON
        text = _debt_text(debt, who)
        today = date.today()
        for user in recipients:
            if await uow.notifications.exists_for_entity_on(user.id, kind, debt.id, today):
                continue
            await notify_user(
                uow, notifier,
                user_id=user.id,
                kind=kind,
                text=text,
                link=f"/debts?highlight={debt.id}",
                entity_id=debt.id,
            )


async def _run_async(notifier: INotifier) -> None:
    async with SqlAlchemyUnitOfWork(None) as uow:
        tenants = await uow.tenants.list_all()

    for tenant in tenants:
        async with SqlAlchemyUnitOfWork(tenant.id) as uow:
            await _notify_tenant(uow, notifier)
            await uow.commit()

    # push уходят после commit в фоне — asyncio.run отменил бы их на выходе
    await drain()


def notify_due_debts() -> None:
    from app.infrastructure.notifications.telegram import TelegramNotifier

    asyncio.run(_run_async(TelegramNotifier()))


if __name__ == "__main__":
    notify_due_debts()
