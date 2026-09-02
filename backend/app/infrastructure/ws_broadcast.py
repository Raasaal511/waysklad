"""Push-доставка событий в открытые WebSocket-соединения (уведомления в реальном
времени вместо периодического опроса GET /api/notifications).

Без NOTIFICATIONS_REDIS_URL — форвардинг в памяти процесса: подходит для dev
(один uvicorn-процесс, --reload без --workers). С NOTIFICATIONS_REDIS_URL —
события идут через Redis pub/sub, что необходимо в проде (--workers 4):
открытое соединение клиента живёт только в одном воркере, и без общей шины
уведомление, созданное HTTP-запросом в другом воркере, никогда не дойдёт до
открытого сокета.
"""

import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket

from app.infrastructure.config import settings
from app.infrastructure.logging import get_logger

_logger = get_logger("app.ws")


def _channel(user_id: int) -> str:
    return f"notifications:user:{user_id}"


class ConnectionRegistry:
    """Локальные для этого процесса подключения — независимо от режима (in-memory/Redis),
    доставка в конкретный сокет всегда идёт через локальный реестр этого воркера."""

    def __init__(self) -> None:
        self._by_user: dict[int, set[WebSocket]] = defaultdict(set)

    def add(self, user_id: int, ws: WebSocket) -> None:
        self._by_user[user_id].add(ws)

    def remove(self, user_id: int, ws: WebSocket) -> None:
        self._by_user[user_id].discard(ws)
        if not self._by_user[user_id]:
            del self._by_user[user_id]

    async def send_local(self, user_id: int, payload: dict) -> None:
        sockets = list(self._by_user.get(user_id, ()))
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                _logger.exception("Не удалось отправить событие в WebSocket user_id=%s", user_id)


class Broadcaster:
    """Единая точка публикации события пользователю — скрывает, идёт ли оно
    через Redis pub/sub или напрямую в памяти процесса."""

    def __init__(self) -> None:
        self.registry = ConnectionRegistry()
        self._redis = None
        self._pubsub = None
        self._listen_task: asyncio.Task | None = None

    async def start(self) -> None:
        if not settings.notifications_redis_url:
            return
        import redis.asyncio as redis

        self._redis = redis.from_url(settings.notifications_redis_url)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.psubscribe("notifications:user:*")
        self._listen_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._listen_task is not None:
            self._listen_task.cancel()
        if self._pubsub is not None:
            await self._pubsub.close()
        if self._redis is not None:
            await self._redis.close()

    async def _listen(self) -> None:
        assert self._pubsub is not None
        async for message in self._pubsub.listen():
            if message["type"] != "pmessage":
                continue
            try:
                channel: str = message["channel"].decode()
                user_id = int(channel.rsplit(":", 1)[1])
                payload = json.loads(message["data"])
            except Exception:
                _logger.exception("Некорректное сообщение в notifications pub/sub")
                continue
            await self.registry.send_local(user_id, payload)

    async def publish(self, user_id: int, payload: dict) -> None:
        if self._redis is not None:
            try:
                await self._redis.publish(_channel(user_id), json.dumps(payload))
                return
            except Exception:
                _logger.exception("Redis publish не удался — событие потеряно для других воркеров")
        # без Redis (dev) или как fallback — доставляем хотя бы локально в этом процессе
        await self.registry.send_local(user_id, payload)


broadcaster = Broadcaster()
