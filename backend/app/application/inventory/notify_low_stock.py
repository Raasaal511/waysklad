"""Персональные уведомления владельцу/управляющему о товарах, которые
заканчиваются и при этом хорошо продаются (та же выборка, что и отчёт
«Рекомендации к дозаказу» — не дублируем отдельное определение «заканчивается»).

Запускается тем же cron-процессом, что и остальные периодические уведомления:
    docker compose exec backend python -m app.application.inventory.notify_low_stock
Или как функция notify_low_stock() из другого скрипта/шедулера.
"""

import asyncio
from datetime import datetime, timedelta

from app.application.analytics.restock_recommendations import SALE_PERIOD_DAYS
from app.domain.common.notifier import INotifier
from app.domain.identity.entities import Role
from app.domain.notifications.entities import NotificationKind
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


async def _notify_tenant(uow: SqlAlchemyUnitOfWork, notifier: INotifier) -> None:
    from app.application.tasks.notify import notify_user

    sale_period_from = datetime.now() - timedelta(days=SALE_PERIOD_DAYS)
    recommendations = await uow.analytics.restock_recommendations(sale_period_from)
    if not recommendations:
        return

    recipients = [u for u in await uow.users.list_by_tenant() if u.role in (Role.OWNER, Role.MANAGER)]
    if not recipients:
        return

    today = datetime.now().date()
    for item in recommendations:
        text = f"Заканчивается «{item.product_name}»: остаток {item.quantity} (порог {item.min_stock})"
        for user in recipients:
            if await uow.notifications.exists_for_entity_on(
                user.id, NotificationKind.LOW_STOCK, item.product_id, today
            ):
                continue
            await notify_user(
                uow, notifier,
                user_id=user.id,
                kind=NotificationKind.LOW_STOCK,
                text=text,
                link=f"/products?highlight={item.product_id}",
                entity_id=item.product_id,
            )


async def _run_async(notifier: INotifier) -> None:
    async with SqlAlchemyUnitOfWork(None) as uow:
        tenants = await uow.tenants.list_all()

    for tenant in tenants:
        async with SqlAlchemyUnitOfWork(tenant.id) as uow:
            await _notify_tenant(uow, notifier)
            await uow.commit()


def notify_low_stock() -> None:
    from app.infrastructure.telegram import TelegramNotifier

    asyncio.run(_run_async(TelegramNotifier()))


if __name__ == "__main__":
    notify_low_stock()
