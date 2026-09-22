"""Тесты промпта B3 (отзывы v2): уникальность по паре заявка+товар,
несколько фото, теги, голоса, публичные фильтры/агрегаты, eligibility,
список для модерации владельца."""

from datetime import date, timedelta
from io import BytesIO

from PIL import Image

from tests.api.test_reviews import _setup_accepted_request


def _test_photo_bytes(size: tuple[int, int] = (400, 300)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(90, 140, 200)).save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


async def _setup_shop_with_two_products(client, owner_headers, buyer_headers, slug="magazin-berkat"):
    """Магазин с двумя товарами в ОДНОЙ принятой заявке — для теста уникальности
    отзыва по паре (заявка, товар), а не только по заявке (баг B1/B2)."""
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product_a = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар А", "purchase_price": "50", "retail_price": "120"},
        )
    ).json()
    product_a = (
        await client.put(
            f"/api/products/{product_a['id']}",
            headers=owner_headers,
            json={**product_a, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()
    product_b = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар Б", "purchase_price": "60", "retail_price": "150"},
        )
    ).json()
    product_b = (
        await client.put(
            f"/api/products/{product_b['id']}",
            headers=owner_headers,
            json={**product_b, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()
    for p in (product_a, product_b):
        await client.post(
            "/api/inventory/receive",
            headers=owner_headers,
            json={"warehouse_id": 1, "lines": [{"product_id": p["id"], "quantity": "10", "cost": "50"}]},
        )

    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Ахмед",
            "items": [
                {"product_id": product_a["id"], "quantity": "1"},
                {"product_id": product_b["id"], "quantity": "1"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]

    due = (date.today() + timedelta(days=3)).isoformat()
    response = await client.post(
        f"/api/storefront/requests/{request_id}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )
    assert response.status_code == 200, response.text
    return product_a, product_b, request_id


# ---------------------------------------------------------------------------
# 1. Уникальность по паре (заявка, товар)
# ---------------------------------------------------------------------------


async def test_review_unique_per_product_not_per_request(client, owner_headers, customer_headers):
    """Заявка с двумя товарами — можно оставить отзыв на каждый; повтор на
    тот же товар по той же заявке всё ещё запрещён (промпт B3 п.1)."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    product_a, product_b, request_id = await _setup_shop_with_two_products(
        client, owner_headers, buyer_headers, slug
    )

    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={"storefront_request_id": request_id, "product_id": product_a["id"], "rating": 5, "text": "Супер"},
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={"storefront_request_id": request_id, "product_id": product_b["id"], "rating": 4, "text": "Хорошо"},
    )
    assert response.status_code == 201, response.text

    # повтор на товар А по той же заявке — запрещён
    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={"storefront_request_id": request_id, "product_id": product_a["id"], "rating": 3},
    )
    assert response.status_code == 400, response.text


# ---------------------------------------------------------------------------
# 2. Несколько фото
# ---------------------------------------------------------------------------


async def test_review_photo_upload_and_ownership_check(client, owner_headers, customer_headers, tmp_path):
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    other_buyer_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, buyer_headers, slug)

    # без авторизации — нельзя
    response = await client.post("/api/reviews/photos", files={"file": ("p.jpg", _test_photo_bytes(), "image/jpeg")})
    assert response.status_code == 401, response.text

    response = await client.post(
        "/api/reviews/photos", headers=buyer_headers, files={"file": ("p1.jpg", _test_photo_bytes(), "image/jpeg")}
    )
    assert response.status_code == 201, response.text
    url1 = response.json()["url"]
    assert url1.startswith("/uploads/")

    response = await client.post(
        "/api/reviews/photos", headers=buyer_headers, files={"file": ("p2.jpg", _test_photo_bytes(), "image/jpeg")}
    )
    assert response.status_code == 201, response.text
    url2 = response.json()["url"]
    assert url2 != url1

    # чужой покупатель не может подставить эти URL в свой отзыв
    response = await client.post(
        "/api/reviews/photos",
        headers=other_buyer_headers,
        files={"file": ("p3.jpg", _test_photo_bytes(), "image/jpeg")},
    )
    foreign_url = response.json()["url"]

    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={
            "storefront_request_id": request_id,
            "product_id": product["id"],
            "rating": 5,
            "text": "С фото",
            "photos": [url1, url2, foreign_url],
        },
    )
    assert response.status_code == 400, response.text

    # с фото, загруженными этим же покупателем — проходит
    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={
            "storefront_request_id": request_id,
            "product_id": product["id"],
            "rating": 5,
            "text": "С фото",
            "photos": [url1, url2],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["photos"] == [url1, url2]
    assert body["photo"] == url1  # совместимость — photo = photos[0]


async def test_review_legacy_single_photo_still_works(client, owner_headers, customer_headers):
    """Старое поле photo (без photos) — совместимость, photos подставляется
    при чтении как [photo] (промпт B3 п.2)."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, buyer_headers, slug)

    response = await client.post(
        "/api/reviews/photos", headers=buyer_headers, files={"file": ("p.jpg", _test_photo_bytes(), "image/jpeg")}
    )
    url = response.json()["url"]

    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={
            "storefront_request_id": request_id,
            "product_id": product["id"],
            "rating": 5,
            "text": "Старый формат",
            "photo": url,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["photo"] == url
    assert body["photos"] == [url]


# ---------------------------------------------------------------------------
# 3. Теги
# ---------------------------------------------------------------------------


async def test_review_tags_endpoint_and_validation(client, owner_headers, customer_headers):
    response = await client.get("/api/reviews/tags")
    assert response.status_code == 200, response.text
    codes = {t["code"] for t in response.json()}
    assert "fast_delivery" in codes
    assert "polite_seller" in codes
    assert len(response.json()) == 8

    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, buyer_headers, slug)

    # неизвестный тег — 400
    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={
            "storefront_request_id": request_id,
            "product_id": product["id"],
            "rating": 5,
            "text": "Ок",
            "tags": ["fast_delivery", "not_a_real_tag"],
        },
    )
    assert response.status_code == 400, response.text

    # известные теги — проходит, в ответе {code, label}
    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={
            "storefront_request_id": request_id,
            "product_id": product["id"],
            "rating": 5,
            "text": "Ок",
            "tags": ["fast_delivery", "good_quality"],
        },
    )
    assert response.status_code == 201, response.text
    tags = response.json()["tags"]
    assert {t["code"] for t in tags} == {"fast_delivery", "good_quality"}
    assert all(t["label"] for t in tags)


# ---------------------------------------------------------------------------
# 4. Голоса «полезно/не полезно»
# ---------------------------------------------------------------------------


async def test_review_voting(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    author_headers, _ = await customer_headers()
    voter_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, author_headers, slug)

    response = await client.post(
        "/api/reviews",
        headers=author_headers,
        json={"storefront_request_id": request_id, "product_id": product["id"], "rating": 5, "text": "Класс"},
    )
    review_id = response.json()["id"]

    # автор не может голосовать за свой отзыв
    response = await client.put(f"/api/reviews/{review_id}/vote", headers=author_headers, json={"value": 1})
    assert response.status_code == 400, response.text

    # без токена — нельзя голосовать (но можно читать список)
    response = await client.put(f"/api/reviews/{review_id}/vote", json={"value": 1})
    assert response.status_code == 401, response.text

    # чужой покупатель голосует "полезно"
    response = await client.put(f"/api/reviews/{review_id}/vote", headers=voter_headers, json={"value": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"likes": 1, "dislikes": 0, "my_vote": 1}

    # меняет голос на "не полезно"
    response = await client.put(f"/api/reviews/{review_id}/vote", headers=voter_headers, json={"value": -1})
    assert response.json() == {"likes": 0, "dislikes": 1, "my_vote": -1}

    # снимает голос
    response = await client.put(f"/api/reviews/{review_id}/vote", headers=voter_headers, json={"value": 0})
    assert response.json() == {"likes": 0, "dislikes": 0, "my_vote": 0}

    # публичный список без токена — my_vote = 0, без 401
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews")
    assert response.status_code == 200, response.text
    assert response.json()["reviews"][0]["my_vote"] == 0

    # публичный список с токеном голосовавшего — видит свой голос
    await client.put(f"/api/reviews/{review_id}/vote", headers=voter_headers, json={"value": 1})
    response = await client.get(
        f"/api/storefront/{slug}/products/{product['id']}/reviews", headers=voter_headers
    )
    review_out = response.json()["reviews"][0]
    assert review_out["my_vote"] == 1
    assert review_out["likes"] == 1


# ---------------------------------------------------------------------------
# 5. Публичный список — фильтры/сортировка/агрегаты
# ---------------------------------------------------------------------------


async def test_public_reviews_filters_and_aggregates(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    owner_setup_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, owner_setup_headers, slug)

    # ещё 4 покупателя с принятыми заявками на тот же товар — разные оценки/теги/фото
    ratings_data = [
        (5, ["fast_delivery"], True),
        (5, ["fast_delivery", "good_quality"], False),
        (3, [], False),
        (1, [], True),
    ]
    review_ids = []
    for rating, tags, with_photo in ratings_data:
        buyer, _ = await customer_headers()
        # своя заявка на этот же товар
        response = await client.post(
            f"/api/storefront/{slug}/requests",
            headers=buyer,
            json={"customer_name": "Покупатель", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
        req_id = response.json()["id"]
        due = (date.today() + timedelta(days=3)).isoformat()
        await client.post(
            f"/api/storefront/requests/{req_id}/accept",
            headers=owner_headers,
            json={"warehouse_id": 1, "due_date": due},
        )
        photos = []
        if with_photo:
            up = await client.post(
                "/api/reviews/photos", headers=buyer, files={"file": ("p.jpg", _test_photo_bytes(), "image/jpeg")}
            )
            photos = [up.json()["url"]]
        response = await client.post(
            "/api/reviews",
            headers=buyer,
            json={
                "storefront_request_id": req_id,
                "product_id": product["id"],
                "rating": rating,
                "text": f"Оценка {rating}",
                "tags": tags,
                "photos": photos,
            },
        )
        assert response.status_code == 201, response.text
        review_ids.append(response.json()["id"])

    # базовый список без фильтров — 4 отзыва, агрегаты без фильтра
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews")
    body = response.json()
    assert body["reviews_count"] == 4
    assert body["total"] == 4
    assert body["rating_distribution"] == {"5": 2, "4": 0, "3": 1, "2": 0, "1": 1}
    assert body["with_photos_count"] == 2
    assert body["average_rating"] == (5 + 5 + 3 + 1) / 4
    tag_counts = {t["code"]: t["count"] for t in body["tags"]}
    assert tag_counts == {"fast_delivery": 2, "good_quality": 1}
    assert len(body["photos"]) == 2

    # фильтр по rating
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews?rating=5")
    body = response.json()
    assert body["total"] == 2
    assert all(r["rating"] == 5 for r in body["reviews"])
    # агрегаты не зависят от фильтра
    assert body["reviews_count"] == 4

    # фильтр with_photos
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews?with_photos=true")
    body = response.json()
    assert body["total"] == 2
    assert all(r["photos"] for r in body["reviews"])

    # фильтр по тегу
    response = await client.get(
        f"/api/storefront/{slug}/products/{product['id']}/reviews?tag=good_quality"
    )
    body = response.json()
    assert body["total"] == 1

    # сортировка rating_asc
    response = await client.get(
        f"/api/storefront/{slug}/products/{product['id']}/reviews?sort=rating_asc"
    )
    ratings_sorted = [r["rating"] for r in response.json()["reviews"]]
    assert ratings_sorted == sorted(ratings_sorted)

    # пагинация
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews?limit=2&offset=0")
    assert len(response.json()["reviews"]) == 2
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews?limit=2&offset=2")
    assert len(response.json()["reviews"]) == 2

    # лимит больше 50 отклоняется
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews?limit=51")
    assert response.status_code == 422


async def test_public_reviews_aggregates_exclude_hidden(client, owner_headers, customer_headers):
    """Скрытый отзыв не должен попадать ни в список, ни в один из агрегатов
    (промпт B3 п.8 — «корректность агрегатов при скрытом отзыве»)."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, buyer_headers, slug)

    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={
            "storefront_request_id": request_id,
            "product_id": product["id"],
            "rating": 1,
            "text": "Плохо",
            "tags": ["no_defects"],
        },
    )
    review_id = response.json()["id"]

    up = await client.post(
        "/api/reviews/photos", headers=buyer_headers, files={"file": ("p.jpg", _test_photo_bytes(), "image/jpeg")}
    )
    # второй отзыв на другую заявку/товар не нужен — просто скрываем единственный
    await client.post(f"/api/reviews/{review_id}/hide", headers=owner_headers)

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews")
    body = response.json()
    assert body["reviews"] == []
    assert body["total"] == 0
    assert body["reviews_count"] == 0
    assert body["average_rating"] == 0.0
    assert body["rating_distribution"] == {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    assert body["with_photos_count"] == 0
    assert body["tags"] == []
    assert body["photos"] == []


# ---------------------------------------------------------------------------
# 6. Eligibility
# ---------------------------------------------------------------------------


async def test_review_eligibility(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()

    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "120"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()

    # нет заявок вообще — no_purchase
    response = await client.get(
        f"/api/storefront/{slug}/products/{product['id']}/reviews/eligibility", headers=buyer_headers
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"can_review": False, "request_id": None, "reason": "no_purchase"}

    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "10", "cost": "50"}]},
    )
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
    )
    request_id = response.json()["id"]

    # заявка ещё не принята — no_purchase
    response = await client.get(
        f"/api/storefront/{slug}/products/{product['id']}/reviews/eligibility", headers=buyer_headers
    )
    assert response.json()["reason"] == "no_purchase"

    due = (date.today() + timedelta(days=3)).isoformat()
    await client.post(
        f"/api/storefront/requests/{request_id}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )

    # принята — можно оставить отзыв, request_id совпадает
    response = await client.get(
        f"/api/storefront/{slug}/products/{product['id']}/reviews/eligibility", headers=buyer_headers
    )
    assert response.json() == {"can_review": True, "request_id": request_id, "reason": "ok"}

    await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={"storefront_request_id": request_id, "product_id": product["id"], "rating": 5, "text": "Ок"},
    )

    # уже оставлен — already_reviewed
    response = await client.get(
        f"/api/storefront/{slug}/products/{product['id']}/reviews/eligibility", headers=buyer_headers
    )
    assert response.json() == {"can_review": False, "request_id": None, "reason": "already_reviewed"}


async def test_review_eligibility_requires_auth(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "120"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews/eligibility")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 7. Владелец — модерация
# ---------------------------------------------------------------------------


async def test_owner_all_reviews_moderation_list(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, buyer_headers, slug)

    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={"storefront_request_id": request_id, "product_id": product["id"], "rating": 2, "text": "Так себе"},
    )
    review_id = response.json()["id"]

    response = await client.get("/api/reviews?status=all", headers=owner_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["reviews"][0]["product_name"] == product["name"]

    response = await client.get("/api/reviews?status=hidden", headers=owner_headers)
    assert response.json()["total"] == 0

    await client.post(f"/api/reviews/{review_id}/hide", headers=owner_headers)

    response = await client.get("/api/reviews?status=visible", headers=owner_headers)
    assert response.json()["total"] == 0

    response = await client.get("/api/reviews?status=hidden", headers=owner_headers)
    body = response.json()
    assert body["total"] == 1
    assert body["reviews"][0]["is_hidden"] is True


async def test_owner_all_reviews_requires_permission(client):
    response = await client.get("/api/reviews")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 8. Изоляция tenant
# ---------------------------------------------------------------------------


async def test_vote_isolated_across_shops(client, owner_headers, random_phone, customer_headers):
    """Отзыв существует в магазине A — голос за него доступен любому
    покупателю платформы (глобальная сущность review_id), но vote-таблица
    хранит tenant_id магазина, где сам отзыв, а не «текущего» tenant
    голосующего — важно, что второй магазин не видит/не путает эти голоса."""
    slug = "magazin-berkat"
    author_headers, _ = await customer_headers()
    voter_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, author_headers, slug)

    response = await client.post(
        "/api/reviews",
        headers=author_headers,
        json={"storefront_request_id": request_id, "product_id": product["id"], "rating": 5, "text": "Класс"},
    )
    review_id = response.json()["id"]

    response = await client.put(f"/api/reviews/{review_id}/vote", headers=voter_headers, json={"value": 1})
    assert response.status_code == 200, response.text

    # второй, независимый магазин
    response = await client.post(
        "/api/auth/register",
        json={
            "shop_name": "Другой магазин",
            "owner_name": "Другой",
            "phone": random_phone(),
            "password": "secret123",
            "personal_data_consent": True,
        },
    )
    other_owner_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    await client.post("/api/inventory/warehouses", headers=other_owner_headers, json={"name": "Склад"})
    await client.patch(
        "/api/auth/shop",
        headers=other_owner_headers,
        json={"name": "Другой магазин", "storefront_enabled": True},
    )

    # у другого магазина нет отзывов с product_id=review_id владельца A — moderation-список пуст
    response = await client.get("/api/reviews?status=all", headers=other_owner_headers)
    assert response.json()["total"] == 0

    # владелец другого магазина не видит чужой отзыв в своей карточке
    response = await client.get(f"/api/reviews/product/{product['id']}", headers=other_owner_headers)
    assert response.status_code == 200
    assert response.json()["reviews"] == []


async def test_review_photo_upload_rejects_bad_format(client, customer_headers):
    buyer_headers, _ = await customer_headers()
    response = await client.post(
        "/api/reviews/photos",
        headers=buyer_headers,
        files={"file": ("virus.exe", b"not-an-image", "application/octet-stream")},
    )
    assert response.status_code == 400, response.text
