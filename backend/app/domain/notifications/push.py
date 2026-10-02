import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlsplit

from app.domain.common.exceptions import DomainError

# одна строка base64url: ключи подписки браузер отдаёт именно так
_B64URL = re.compile(r"^[A-Za-z0-9_\-]+=*$")
# FCM/Apple/Mozilla — около 200 символов; запас на будущие форматы
MAX_ENDPOINT_LENGTH = 1024
MAX_KEY_LENGTH = 200
# телефон, планшет, компьютер, рабочий ноутбук — больше 10 значит, что старые
# подписки не снялись (переустановки браузера); забываем давно не открытые
MAX_DEVICES_PER_USER = 10


@dataclass
class PushSubscription:
    """Подписка браузера на Web Push — одно устройство одного сотрудника.

    token_version — снимок User.token_version на момент подписки: после смены
    пароля или «Завершить все сессии» подписка перестаёт совпадать с
    пользователем и удаляется при первой же рассылке, без отдельных хуков в
    этих сценариях."""

    id: int | None
    user_id: int
    endpoint: str
    p256dh: str
    auth: str
    token_version: int = 0
    confirmed_at: datetime | None = None

    def validate(self) -> None:
        validate_push_endpoint(self.endpoint)
        for key in (self.p256dh, self.auth):
            if not key or len(key) > MAX_KEY_LENGTH or not _B64URL.match(key):
                raise DomainError("Некорректные ключи подписки на уведомления")


def validate_push_endpoint(endpoint: str) -> None:
    """Адрес push-сервиса придумывает браузер, но присылает его клиент — значит,
    его можно подделать и заставить сервер слать POST куда угодно. Пропускаем
    только https на доменное имя: не IP-адрес, не localhost и не короткие имена
    docker-сети (redis, db, backend)."""
    if not endpoint or len(endpoint) > MAX_ENDPOINT_LENGTH:
        raise DomainError("Некорректный адрес подписки на уведомления")
    parts = urlsplit(endpoint)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        raise DomainError("Некорректный адрес подписки на уведомления")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise DomainError("Некорректный адрес подписки на уведомления")
    if "." not in host or host.endswith((".local", ".internal", ".localhost")):
        raise DomainError("Некорректный адрес подписки на уведомления")


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    # путь внутри кабинета, куда ведёт касание уведомления
    link: str = "/"
    # уведомление с тем же tag заменяет предыдущее на экране, а не копится стопкой
    tag: str = ""
    # заявка/сообщение покупателя ждут ответа — будим телефон из энергосбережения;
    # остальное можно доставить с задержкой
    urgent: bool = False


class PushDeliveryResult(StrEnum):
    DELIVERED = "delivered"
    # push-сервис ответил 404/410 — браузер отписался или приложение удалено
    GONE = "gone"
    # сеть, таймаут, 5xx — подписку не трогаем, следующее событие попробует снова
    FAILED = "failed"


class IPushSender(Protocol):
    @property
    def public_key(self) -> str | None:
        """applicationServerKey для браузера; None — push на сервере не настроен."""
        ...

    async def send(self, subscription: PushSubscription, message: PushMessage) -> PushDeliveryResult: ...


class IPushSubscriptionRepository(Protocol):
    async def upsert(self, subscription: PushSubscription) -> PushSubscription:
        """Сохранить по endpoint: тот же браузер, вошедший под другим сотрудником
        (или в другой магазин), переходит к нему — прежний владелец больше не
        получает уведомлений на это устройство."""
        ...

    async def list_for_user(self, user_id: int) -> list[PushSubscription]: ...

    async def delete(self, subscription_id: int) -> None: ...

    async def delete_for_user(self, user_id: int, endpoint: str) -> bool:
        """Снять подписку своего устройства (выход из кабинета). False — не было."""
        ...
