"""Push-доставка событий в открытые WebSocket-соединения — уведомления в реальном
времени вместо периодического опроса GET /api/notifications, и чат заявок с витрины.

Без NOTIFICATIONS_REDIS_URL — форвардинг в памяти процесса: подходит для dev
(один uvicorn-процесс, --reload без --workers). С NOTIFICATIONS_REDIS_URL —
события идут через Redis pub/sub, что необходимо в проде (--workers 4):
открытое соединение клиента живёт только в одном воркере, и без общей шины
уведомление, созданное HTTP-запросом в другом воркере, никогда не дойдёт до
открытого сокета.

Каналы — произвольные строки ("user:<id>" для личных уведомлений,
"storefront_request:<id>" для чата заявки) — один Broadcaster/Redis pub/sub
обслуживает оба сценария.
"""

import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket

from app.infrastructure.config import settings
from app.infrastructure.observability.logging import get_logger

_logger = get_logger("app.ws")
_PUBSUB_PREFIX = "ws_channel:"


def user_channel(user_id: int) -> str:
    return f"user:{user_id}"


def storefront_request_channel(request_id: int) -> str:
    return f"storefront_request:{request_id}"


class ConnectionRegistry:
    """Локальные для этого процесса подключения — независимо от режима (in-memory/Redis),
    доставка в конкретный сокет всегда идёт через локальный реестр этого воркера."""

    def __init__(self) -> None:
        self._by_channel: dict[str, set[WebSocket]] = defaultdict(set)

    def add(self, channel: str, ws: WebSocket) -> None:
        self._by_channel[channel].add(ws)

    def remove(self, channel: str, ws: WebSocket) -> None:
        self._by_channel[channel].discard(ws)
        if not self._by_channel[channel]:
            del self._by_channel[channel]

    async def send_local(self, channel: str, payload: dict) -> None:
        sockets = list(self._by_channel.get(channel, ()))
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                _logger.exception("Не удалось отправить событие в WebSocket channel=%s", channel)

    def count_connections(self) -> int:
        """Для admin-статуса — только этот воркер (см. get_server_status.py),
        не общее число по всей платформе (--workers N в проде)."""
        return sum(len(sockets) for sockets in self._by_channel.values())


class Broadcaster:
    """Единая точка публикации события в канал — скрывает, идёт ли оно через
    Redis pub/sub или напрямую в памяти процесса."""

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
        await self._pubsub.psubscribe(f"{_PUBSUB_PREFIX}*")
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
                raw_channel: str = message["channel"].decode()
                channel = raw_channel.removeprefix(_PUBSUB_PREFIX)
                payload = json.loads(message["data"])
            except Exception:
                _logger.exception("Некорректное сообщение в ws pub/sub")
                continue
            await self.registry.send_local(channel, payload)

    async def publish(self, channel: str, payload: dict) -> None:
        if self._redis is not None:
            try:
                await self._redis.publish(f"{_PUBSUB_PREFIX}{channel}", json.dumps(payload))
                return
            except Exception:
                _logger.exception("Redis publish не удался — событие потеряно для других воркеров")
        # без Redis (dev) или как fallback — доставляем хотя бы локально в этом процессе
        await self.registry.send_local(channel, payload)


broadcaster = Broadcaster()
