"""Фоновые задачи процесса: то, чего бизнес-операция не должна ждать (push на
телефон после commit заявки). Ссылки держим здесь — иначе asyncio может
собрать незавершённую задачу сборщиком мусора.

Короткоживущие процессы (cron-скрипты через asyncio.run) обязаны дождаться
drain() перед выходом, иначе задачи отменятся вместе с циклом событий."""

import asyncio
import logging
from collections.abc import Awaitable

_logger = logging.getLogger(__name__)
_tasks: set[asyncio.Task] = set()


def _done(task: asyncio.Task) -> None:
    _tasks.discard(task)
    if not task.cancelled() and task.exception() is not None:
        _logger.error("Фоновая задача упала", exc_info=task.exception())


def spawn(work: Awaitable[None]) -> None:
    task = asyncio.ensure_future(work, loop=asyncio.get_running_loop())
    _tasks.add(task)
    task.add_done_callback(_done)


async def drain() -> None:
    """Дождаться всех фоновых задач, включая порождённые по ходу ожидания."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
