"""Удаляет старые CustomerLoginLink — и протухшие неподтверждённые черновики
входа, и уже подтверждённые (своё дело сделали, дальше не нужны). Хранить
дольше суток незачем: LOGIN_LINK_TTL = 10 минут, после этого ссылка либо уже
использована (обменяна на JWT через GetCustomerLoginStatusUseCase), либо
мертва навсегда.

Запускается тем же cron-процессом, что и остальные периодические задачи:
    docker compose exec backend python -m app.application.customers.cleanup_login_links
Или как функция cleanup_customer_login_links() из шедулера.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from app.infrastructure.db.uow import SqlAlchemyUnitOfWork

_KEEP_FOR = timedelta(days=1)


async def _run_async() -> None:
    cutoff = datetime.now(timezone.utc) - _KEEP_FOR
    async with SqlAlchemyUnitOfWork(None) as uow:
        await uow.customer_login_links.delete_created_before(cutoff)
        await uow.commit()


def cleanup_customer_login_links() -> None:
    asyncio.run(_run_async())


if __name__ == "__main__":
    cleanup_customer_login_links()
