"""Web Push через VAPID (pywebpush) — реализация IPushSender.

Сервер шифрует уведомление ключами подписки и отдаёт push-сервису браузера
(Google FCM, Apple, Mozilla); тот будит телефон, даже если кабинет закрыт.
"""

import asyncio
import base64
import ipaddress
import json
import logging
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException, webpush

from app.domain.notifications.push import PushDeliveryResult, PushMessage, PushSubscription
from app.infrastructure.config import settings

_logger = logging.getLogger(__name__)

Resolver = Callable[..., list]

# заявка, пришедшая ночью, ещё нужна утром; через сутки — уже нет, колокольчик её хранит
_TTL_SECONDS = 24 * 60 * 60
# push-сервис отвечает за десятки миллисекунд; дольше — сеть до него лежит,
# и ждать её внутри оформления заявки покупателя нельзя
_TIMEOUT_SECONDS = 5
# лимит полезной нагрузки Web Push — 4 КБ после шифрования; текст наших
# уведомлений — одна строка, но имя покупателя/товара приходит снаружи
_MAX_BODY = 300


def _public_key_b64(vapid: Vapid) -> str:
    raw = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


# Внутренние сети, куда подписка не должна заставить сервер слать запросы:
# docker, локальная сеть хостера, Tailscale/CGNAT. Не «всё, что не global»:
# прокси/VPN с fake-ip (Clash, sing-box) отдают для fcm.googleapis.com адреса
# из 198.18.0.0/15 и 240.0.0.0/4 — запрос туда уходит в локальный прокси,
# который ведёт его к настоящему хосту по имени.
_INTERNAL_NETWORKS = [
    ipaddress.ip_network(n)
    for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7")
]


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
        return False  # link-local — в том числе метаданные облака 169.254.169.254
    return not any(ip in network for network in _INTERNAL_NETWORKS)


def _resolves_to_public(host: str, resolve: Resolver) -> bool | None:
    """Имя push-сервиса не должно вести во внутреннюю сеть: проверка имени при
    подписке (domain/notifications/push.py) не видит DNS-записей вида
    127.0.0.1 на публичном домене. None — DNS не ответил, судить не о чем."""
    try:
        infos = resolve(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return None
    return bool(infos) and all(_is_public_address(info[4][0]) for info in infos)


class WebPushSender:
    def __init__(self, private_key: str, subject: str, resolve: Resolver = socket.getaddrinfo):
        self._vapid = None
        self._public_key = None
        self._subject = subject
        self._resolve = resolve
        if not private_key:
            return
        # Без контакта pywebpush шлёт вовсе без подписи VAPID, и Google/Apple
        # отклоняют всё — лучше честно выключить push, чем обещать его в профиле.
        if not subject.startswith(("mailto:", "https://")):
            _logger.error("Web Push выключен: VAPID_SUBJECT (или PUBLIC_BASE_URL) должен быть mailto: или https://")
            return
        try:
            self._vapid = Vapid.from_string(private_key)
            self._public_key = _public_key_b64(self._vapid)
        except Exception:
            # битый ключ в .env не должен ронять API и cron при импорте
            _logger.error("Web Push выключен: VAPID_PRIVATE_KEY не читается", exc_info=True)
            self._vapid = None

    @classmethod
    def from_settings(cls) -> "WebPushSender":
        return cls(
            settings.vapid_private_key.strip(),
            settings.vapid_subject.strip() or settings.public_base_url.strip(),
        )

    @property
    def public_key(self) -> str | None:
        return self._public_key

    async def send(self, subscription: PushSubscription, message: PushMessage) -> PushDeliveryResult:
        if self._vapid is None:
            return PushDeliveryResult.FAILED
        return await asyncio.to_thread(self._send_sync, subscription, message)

    def _send_sync(self, subscription: PushSubscription, message: PushMessage) -> PushDeliveryResult:
        host = urlsplit(subscription.endpoint).hostname or ""
        public = _resolves_to_public(host, self._resolve)
        if public is None:
            _logger.warning("Web Push DNS failed host=%s", host)
            return PushDeliveryResult.FAILED
        if not public:
            # настоящий push-сервис так не резолвится — подписку забываем
            _logger.warning("Web Push endpoint resolves to a non-public address host=%s", host)
            return PushDeliveryResult.GONE
        payload = json.dumps(
            {
                "title": message.title,
                "body": message.body[:_MAX_BODY],
                "link": message.link,
                "tag": message.tag,
            },
            ensure_ascii=False,
        )
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=self._vapid,
                # новый словарь на каждую отправку: pywebpush дописывает в него
                # aud/exp, и общий словарь подписал бы все следующие отправки
                # адресом первого push-сервиса — Apple и Google их отклонят
                vapid_claims={"sub": self._subject},
                ttl=_TTL_SECONDS,
                timeout=_TIMEOUT_SECONDS,
                headers={"Urgency": "high" if message.urgent else "normal"},
            )
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                return PushDeliveryResult.GONE
            _logger.warning(
                "Web Push failed status=%s host=%s: %s",
                status,
                host,
                (exc.response.text[:200] if exc.response is not None else str(exc)),
            )
            return PushDeliveryResult.FAILED
        except Exception:
            _logger.warning("Web Push failed host=%s", host, exc_info=True)
            return PushDeliveryResult.FAILED
        return PushDeliveryResult.DELIVERED


# Один на процесс, как broadcaster у WebSocket-канала. Тесты подменяют атрибут
# модуля, поэтому читать его нужно как web_push.push_sender в момент вызова.
push_sender = WebPushSender.from_settings()
