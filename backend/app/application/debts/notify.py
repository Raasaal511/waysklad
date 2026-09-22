from app.domain.common.notifier import INotifier
from app.domain.common.uow import IUnitOfWork
from app.domain.debts.entities import Debt
from app.domain.identity.entities import Role
from app.domain.notifications.entities import NotificationKind


async def notify_debt_issued(uow: IUnitOfWork, notifier: INotifier | None, debt: Debt) -> None:
    """Мгновенное уведомление owner/manager о новом долге — в дополнение к
    ежедневному cron-обходу notify_due_debts (тот ловит уже выданные долги
    по сроку, этот — момент выдачи)."""
    from app.application.tasks.notify import notify_user

    if debt.client_id is not None:
        client = await uow.clients.get(debt.client_id)
        who = f"клиенту «{client.name}»"
    else:
        supplier = await uow.suppliers.get(debt.supplier_id)
        who = f"поставщику «{supplier.name}»"

    text = f"Новый долг {who} на {debt.balance}"
    recipients = [u for u in await uow.users.list_by_tenant() if u.role in (Role.OWNER, Role.MANAGER)]
    for user in recipients:
        await notify_user(
            uow, notifier,
            user_id=user.id,
            kind=NotificationKind.DEBT_ISSUED,
            text=text,
            link=f"/debts?highlight={debt.id}",
            entity_id=debt.id,
        )
