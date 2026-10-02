"""WebPushSender с настоящим шифрованием и подписью VAPID — подменён только
HTTP до push-сервиса."""

import base64
import socket

import jwt
import pytest
import pywebpush

from app.domain.notifications.push import PushDeliveryResult, PushMessage, PushSubscription
from app.infrastructure.notifications.web_push import WebPushSender
from scripts.gen_vapid_keys import main as gen_vapid_keys

# ключи подписки настоящего браузера (из тестов pywebpush) — нужны для шифрования
P256DH = "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM"
AUTH = "tBHItJI5svbpez7KI4CCXg"


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.text = ""
        self.reason = ""
        self.headers = {}


def _resolver(address: str):
    def resolve(host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    return resolve


@pytest.fixture
def vapid_key(capsys) -> str:
    gen_vapid_keys()
    return capsys.readouterr().out.strip().split("=", 1)[1]


@pytest.fixture
def sender(vapid_key) -> WebPushSender:
    # DNS подменён: тесты не ходят в сеть, push-сервис «живёт» на публичном адресе
    return WebPushSender(vapid_key, "mailto:test@waysklad.ru", resolve=_resolver("142.250.74.106"))


class Posts(list):
    """Запросы к push-сервису; status — чем он ответит на следующий."""

    status = 201


@pytest.fixture
def posts(monkeypatch) -> Posts:
    calls = Posts()

    def fake_post(url, data=None, headers=None, timeout=None, **_):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        return FakeResponse(calls.status)

    monkeypatch.setattr(pywebpush.requests, "post", fake_post)
    return calls


def _subscription(endpoint: str) -> PushSubscription:
    return PushSubscription(id=1, user_id=1, endpoint=endpoint, p256dh=P256DH, auth=AUTH)


def _jwt_claims(headers: dict) -> dict:
    token = headers["Authorization"].split()[1].split(",")[0].removeprefix("t=")
    return jwt.decode(token, options={"verify_signature": False})


def test_public_key_is_uncompressed_p256_point(sender):
    raw = base64.urlsafe_b64decode(sender.public_key + "==")
    assert len(raw) == 65 and raw[0] == 4


def test_disabled_without_key():
    assert WebPushSender("", "").public_key is None


async def test_each_push_service_gets_its_own_audience(sender, posts):
    """pywebpush дописывает aud в словарь claims — общий словарь подписал бы
    отправку в Apple адресом Google, и Apple её отклонила бы."""
    message = PushMessage(title="Новая заявка", body="Ахмед, 2 товара", link="/orders", urgent=True)
    assert await sender.send(_subscription("https://fcm.googleapis.com/fcm/send/a"), message) is PushDeliveryResult.DELIVERED
    assert await sender.send(_subscription("https://web.push.apple.com/b"), message) is PushDeliveryResult.DELIVERED

    assert [_jwt_claims(c["headers"])["aud"] for c in posts] == [
        "https://fcm.googleapis.com",
        "https://web.push.apple.com",
    ]
    assert _jwt_claims(posts[0]["headers"])["sub"] == "mailto:test@waysklad.ru"
    assert posts[0]["headers"]["Urgency"] == "high"
    assert posts[0]["headers"]["ttl"] == "86400"
    assert posts[0]["timeout"] == 5


@pytest.mark.parametrize(
    ("status", "expected"),
    [(410, PushDeliveryResult.GONE), (404, PushDeliveryResult.GONE), (500, PushDeliveryResult.FAILED), (403, PushDeliveryResult.FAILED)],
)
async def test_status_mapping(sender, posts, status, expected):
    posts.status = status
    message = PushMessage(title="t", body="b")
    assert await sender.send(_subscription("https://fcm.googleapis.com/fcm/send/x"), message) is expected


async def test_network_error_is_failed(sender, monkeypatch):
    def broken(*args, **kwargs):
        raise pywebpush.requests.exceptions.ConnectionError("no route")

    monkeypatch.setattr(pywebpush.requests, "post", broken)
    result = await sender.send(_subscription("https://fcm.googleapis.com/fcm/send/x"), PushMessage(title="t", body="b"))
    assert result is PushDeliveryResult.FAILED


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.5", "172.18.0.3", "192.168.1.1", "169.254.169.254", "100.100.1.1", "::1", "fd00::1", "::ffff:10.0.0.1", "0.0.0.0"],
)
async def test_endpoint_resolving_to_internal_network_is_dropped(vapid_key, posts, address):
    """Публичное имя с A-записью во внутреннюю сеть: не шлём и забываем подписку."""
    sender = WebPushSender(vapid_key, "mailto:t@waysklad.ru", resolve=_resolver(address))
    result = await sender.send(_subscription("https://evil.example.com/x"), PushMessage(title="t", body="b"))
    assert result is PushDeliveryResult.GONE
    assert list(posts) == []


async def test_dns_failure_keeps_subscription(vapid_key, posts):
    def broken(host, port, **kwargs):
        raise socket.gaierror("temporary failure")

    sender = WebPushSender(vapid_key, "mailto:t@waysklad.ru", resolve=broken)
    result = await sender.send(_subscription("https://fcm.googleapis.com/x"), PushMessage(title="t", body="b"))
    assert result is PushDeliveryResult.FAILED


@pytest.mark.parametrize("subject", ["", "admin@waysklad.ru", "http://waysklad.ru"])
def test_without_valid_contact_push_is_off(vapid_key, subject):
    """Без контакта pywebpush шлёт без подписи — Google/Apple отклонят всё;
    честнее не показывать кнопку вовсе."""
    assert WebPushSender(vapid_key, subject).public_key is None


def test_broken_key_turns_push_off_instead_of_crashing():
    assert WebPushSender("-----BEGIN PRIVATE KEY----- garbage", "mailto:t@waysklad.ru").public_key is None


@pytest.mark.parametrize("address", ["198.18.0.5", "240.0.1.224"])
async def test_fake_ip_proxy_addresses_are_allowed(vapid_key, posts, address):
    """VPN/прокси с fake-ip отдают для fcm.googleapis.com такие адреса — push
    через них работает и не должен считаться атакой (и удалять подписки)."""
    sender = WebPushSender(vapid_key, "mailto:t@waysklad.ru", resolve=_resolver(address))
    result = await sender.send(_subscription("https://fcm.googleapis.com/x"), PushMessage(title="t", body="b"))
    assert result is PushDeliveryResult.DELIVERED
