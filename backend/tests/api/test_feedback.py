"""Обратная связь из кабинета → вкладка «Обратная связь» в админке.

Главное правило: пустое обращение не принимаем — нужен текст или хотя бы одно фото.
"""

import io

import pytest
from PIL import Image

from app.application.feedback import submit_feedback as submit_module
from app.application.feedback.submit_feedback import SubmittedFeedback, notify_admin_about_feedback
from app.domain.feedback.entities import Feedback, FeedbackTopic
from tests.test_admin import _admin_headers

URL = "/api/feedback"
ADMIN_URL = "/api/admin/feedback"


def _photo(name: str = "shot.jpg") -> tuple[str, tuple[str, bytes, str]]:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), color=(200, 90, 60)).save(buffer, "JPEG")
    return ("photos", (name, buffer.getvalue(), "image/jpeg"))


@pytest.fixture
async def admin_headers(client) -> dict:
    return await _admin_headers(client)


async def test_text_only_is_accepted_and_visible_in_admin(client, owner_headers, admin_headers):
    response = await client.post(
        URL,
        headers={**owner_headers, "User-Agent": "Pixel 7 Chrome"},
        data={"topic": "question", "text": "  Как вернуть товар?  ", "page": "/sales/new", "app_version": "1.0"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["topic"] == "question"
    assert body["text"] == "Как вернуть товар?"
    assert body["photos"] == []

    listing = await client.get(ADMIN_URL, headers=admin_headers)
    assert listing.status_code == 200, listing.text
    item = next(i for i in listing.json()["items"] if i["id"] == body["id"])
    # магазин, автор, экран и устройство подставлены сами — переспрашивать не нужно
    assert item["shop_name"] == "Магазин Беркат"
    assert item["author_name"] == "Ахмед"
    assert item["author_role"] == "owner"
    assert item["page"] == "/sales/new"
    assert item["user_agent"] == "Pixel 7 Chrome"
    assert item["app_version"] == "1.0"
    assert item["resolved_at"] is None


async def test_photo_only_is_accepted(client, owner_headers):
    response = await client.post(URL, headers=owner_headers, data={"topic": "bug"}, files=[_photo()])
    assert response.status_code == 201, response.text
    photos = response.json()["photos"]
    assert len(photos) == 1 and photos[0].startswith("/uploads/")


async def test_text_and_three_photos(client, owner_headers):
    response = await client.post(
        URL,
        headers=owner_headers,
        data={"topic": "suggestion", "text": "Добавьте тёмную тему в чек"},
        files=[_photo("a.jpg"), _photo("b.jpg"), _photo("c.jpg")],
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["photos"]) == 3


@pytest.mark.parametrize("text", ["", "   \n  "])
async def test_empty_feedback_is_rejected(client, owner_headers, text):
    response = await client.post(URL, headers=owner_headers, data={"topic": "bug", "text": text})
    assert response.status_code == 400
    assert "фото" in response.json()["detail"]


async def test_more_than_three_photos_rejected(client, owner_headers):
    response = await client.post(
        URL, headers=owner_headers, data={"topic": "bug"}, files=[_photo(f"{i}.jpg") for i in range(4)]
    )
    assert response.status_code == 400
    assert "3" in response.json()["detail"]


async def test_unknown_topic_rejected(client, owner_headers):
    response = await client.post(URL, headers=owner_headers, data={"topic": "complaint", "text": "Текст"})
    assert response.status_code == 400


async def test_invalid_photo_does_not_create_feedback(client, owner_headers, admin_headers):
    before = (await client.get(ADMIN_URL, headers=admin_headers, params={"status": "all"})).json()["total"]
    response = await client.post(
        URL,
        headers=owner_headers,
        data={"topic": "bug", "text": "С вложением-не-картинкой"},
        files=[("photos", ("notes.txt", b"not an image", "text/plain"))],
    )
    assert response.status_code == 400
    after = (await client.get(ADMIN_URL, headers=admin_headers, params={"status": "all"})).json()["total"]
    assert after == before


async def test_seller_can_send_feedback(client, owner_headers, random_phone):
    phone = random_phone()
    await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={"name": "Продавец", "phone": phone, "password": "secret123", "role": "seller"},
    )
    login = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "secret123", "personal_data_consent": True}
    )
    seller_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post(URL, headers=seller_headers, data={"topic": "question", "text": "Где отчёт?"})
    assert response.status_code == 201, response.text


async def test_requires_login(client):
    response = await client.post(URL, data={"topic": "question", "text": "Привет"})
    assert response.status_code == 401


async def test_shop_token_cannot_read_admin_list(client, owner_headers):
    response = await client.get(ADMIN_URL, headers=owner_headers)
    assert response.status_code in (401, 403)


async def test_resolve_moves_out_of_new_and_back(client, owner_headers, admin_headers):
    created = await client.post(URL, headers=owner_headers, data={"topic": "bug", "text": "Не печатается чек"})
    feedback_id = created.json()["id"]
    new_before = (await client.get(ADMIN_URL, headers=admin_headers)).json()["new_count"]

    resolved = await client.post(f"{ADMIN_URL}/{feedback_id}/resolve", headers=admin_headers)
    assert resolved.status_code == 200, resolved.text

    new_list = (await client.get(ADMIN_URL, headers=admin_headers)).json()
    assert feedback_id not in [i["id"] for i in new_list["items"]]
    assert new_list["new_count"] == new_before - 1
    done_list = (await client.get(ADMIN_URL, headers=admin_headers, params={"status": "resolved"})).json()
    assert feedback_id in [i["id"] for i in done_list["items"]]

    reopened = await client.post(
        f"{ADMIN_URL}/{feedback_id}/resolve", headers=admin_headers, params={"resolved": "false"}
    )
    assert reopened.status_code == 200
    again = (await client.get(ADMIN_URL, headers=admin_headers)).json()
    assert feedback_id in [i["id"] for i in again["items"]]


async def test_resolve_unknown_is_404(client, admin_headers):
    response = await client.post(f"{ADMIN_URL}/999999999/resolve", headers=admin_headers)
    assert response.status_code == 404


async def test_topic_filter(client, owner_headers, admin_headers):
    await client.post(URL, headers=owner_headers, data={"topic": "suggestion", "text": "Идея"})
    await client.post(URL, headers=owner_headers, data={"topic": "question", "text": "Вопрос"})
    only = (await client.get(ADMIN_URL, headers=admin_headers, params={"topic": "suggestion"})).json()
    assert only["items"] and all(i["topic"] == "suggestion" for i in only["items"])


class _RecordingNotifier:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))


def _submitted(text: str, photos: list[str]) -> SubmittedFeedback:
    return SubmittedFeedback(
        feedback=Feedback(id=1, tenant_id=1, user_id=1, topic=FeedbackTopic.BUG, text=text, photos=photos),
        shop_name="Магазин <Беркат>",
        author_name="Ахмед",
        author_phone="+79281234567",
    )


def test_admin_notification_escapes_html(monkeypatch):
    """Текст покупателя идёт в Telegram с parse_mode=HTML — теги должны экранироваться."""
    monkeypatch.setattr(submit_module.settings, "admin_alert_chat_id", "42")
    monkeypatch.setattr(submit_module.settings, "telegram_bot_token", "token")
    notifier = _RecordingNotifier()
    notify_admin_about_feedback(notifier, _submitted("<b>сломалось</b>", ["/uploads/a.webp"]))
    [(chat_id, text)] = notifier.sent
    assert chat_id == "42"
    assert "Ошибка" in text
    assert "&lt;b&gt;сломалось&lt;/b&gt;" in text
    assert "Магазин &lt;Беркат&gt;" in text
    assert "Фото: 1" in text


def test_admin_notification_skipped_without_chat(monkeypatch):
    monkeypatch.setattr(submit_module.settings, "admin_alert_chat_id", "")
    notifier = _RecordingNotifier()
    notify_admin_about_feedback(notifier, _submitted("текст", []))
    assert notifier.sent == []
