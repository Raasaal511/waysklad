"""Авто-освобождение резерва под заявку с витрины, которую владелец не обработал
72 часа — товар не должен зависать в резерве бесконечно, если заявку забыли
разобрать. Статус заявки НЕ меняется (остаётся NEW) — владелец продолжает
видеть её в списке новых, просто без резерва под ней.

Запускается тем же cron-процессом, что и остальные периодические задачи:
    docker compose exec backend python -m app.application.storefront.release_expired_reservations
Или как функция release_expired_storefront_reservations() из шедулера.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from app.application.storefront.reservation import RESERVATION_TTL_HOURS, release_request_reservation
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


async def _release_for_tenant(uow: SqlAlchemyUnitOfWork) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RESERVATION_TTL_HOURS)
    stale = await uow.storefront_requests.list_stale_reserved(cutoff)
    for request in stale:
        await release_request_reservation(uow, request)
        request.reservation_released = True
        await uow.storefront_requests.save(request)


async def _run_async() -> None:
    async with SqlAlchemyUnitOfWork(None) as uow:
        tenants = await uow.tenants.list_all()

    for tenant in tenants:
        async with SqlAlchemyUnitOfWork(tenant.id) as uow:
            await _release_for_tenant(uow)
            await uow.commit()


def release_expired_storefront_reservations() -> None:
    asyncio.run(_run_async())


if __name__ == "__main__":
    release_expired_storefront_reservations()
