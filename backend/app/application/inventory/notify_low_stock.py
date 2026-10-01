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
from app.infrastructure.background import drain
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

# роли, чьи алерты фильтруются по назначенным складам — тот же список, что
# у _WAREHOUSE_SCOPED_ROLES в presentation/deps/auth.py (здесь нет HTTP-контекста,
# чтобы переиспользовать сам Actor/get_actor)
_WAREHOUSE_SCOPED_ROLES = (Role.MANAGER,)


async def _notify_tenant(uow: SqlAlchemyUnitOfWork, notifier: INotifier) -> None:
    from app.application.tasks.notify import notify_user

    sale_period_from = datetime.now() - timedelta(days=SALE_PERIOD_DAYS)

    recipients = [u for u in await uow.users.list_by_tenant() if u.role in (Role.OWNER, Role.MANAGER)]
    if not recipients:
        return

    for user in recipients:
        # OWNER видит все склады (warehouse_ids=None — без фильтра, как у
        # not-scoped Actor); MANAGER — только назначенные ему, тот же принцип,
        # что у GetRestockRecommendationsUseCase/get_actor для HTTP-запросов
        warehouse_ids = None
        if user.role in _WAREHOUSE_SCOPED_ROLES:
            warehouse_ids = [w.id for w in await uow.warehouses.list_for_user(user.id)]
            if not warehouse_ids:
                continue  # manager без назначенных складов — нечего проверять

        recommendations = await uow.analytics.restock_recommendations(sale_period_from, warehouse_ids)
        for item in recommendations:
            text = f"Заканчивается «{item.product_name}»: остаток {item.quantity} (порог {item.min_stock})"
            # повтор только если остаток вырос с прошлого уведомления (пытались
            # пополнить) — иначе не спамим одним и тем же каждые 15 минут/день,
            # пока товар не появится на складе
            last = await uow.notifications.last_snapshot_value(
                user.id, NotificationKind.LOW_STOCK, item.product_id
            )
            if last is not None and item.quantity <= last:
                continue
            await notify_user(
                uow, notifier,
                user_id=user.id,
                kind=NotificationKind.LOW_STOCK,
                text=text,
                link=f"/products/{item.product_id}",
                entity_id=item.product_id,
                snapshot_value=item.quantity,
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


def notify_low_stock() -> None:
    from app.infrastructure.notifications.telegram import TelegramNotifier

    asyncio.run(_run_async(TelegramNotifier()))


if __name__ == "__main__":
    notify_low_stock()
