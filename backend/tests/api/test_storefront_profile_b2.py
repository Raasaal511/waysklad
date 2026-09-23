"""Тесты промпта B2 — публичный профиль магазина: лого, рейтинг, контакты,
FAQ, минимальная сумма заказа."""

from datetime import date, timedelta
from io import BytesIO

from PIL import Image

from app.application.storefront.get_profile import _orders_count_label


def _test_logo_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (200, 200), color=(90, 140, 200)).save(buffer, "PNG")
    return buffer.getvalue()


def test_orders_count_label_rounding():
    """Три буквальных примера из промпта B2 п.2 — "2000+", "150+", "12" (без
    "+") — однозначно задают правило: ниже 50 число точное, от 50 —
    округление вниз с шагом по порядку величины (10/50/100/500/1000) плюс
    "+". Все три примера воспроизводятся дословно."""
    assert _orders_count_label(7) == "7"
    assert _orders_count_label(9) == "9"
    assert _orders_count_label(12) == "12"  # буквальный пример из промпта
    assert _orders_count_label(19) == "19"
    assert _orders_count_label(49) == "49"
    assert _orders_count_label(50) == "50+"
    assert _orders_count_label(99) == "90+"
    assert _orders_count_label(100) == "100+"
    assert _orders_count_label(150) == "150+"  # буквальный пример из промпта
    assert _orders_count_label(499) == "450+"
    assert _orders_count_label(500) == "500+"
    assert _orders_count_label(999) == "900+"
    assert _orders_count_label(1000) == "1000+"
    assert _orders_count_label(2000) == "2000+"  # буквальный пример из промпта
    assert _orders_count_label(2734) == "2500+"


async def _enable_storefront_with_warehouse(client, owner_headers, warehouse_id: int = 1):
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    response = await client.put(
        f"/api/inventory/warehouses/{warehouse_id}",
        headers=owner_headers,
        json={"name": "Основной склад", "address": "ул. Мира, 1", "show_on_storefront": True},
    )
    assert response.status_code == 200, response.text


async def test_update_shop_contacts_and_policies_via_api(client, owner_headers):
    """GET/PATCH /api/auth/shop принимают и отдают все новые поля профиля."""
    response = await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={
            "name": "Магазин Беркат",
            "storefront_description": "Продаём качественную обувь с 2020 года",
            "contact_phone": "+79280001122",
            "contact_whatsapp": "89280001122",
            "contact_telegram": "@berkat_shop",
            "storefront_min_order_total": "1000",
            "policy_refund_money": "Возврат в течение 14 дней",
            "policy_payment": "Наличными или картой при получении",
            "policy_delivery": "Курьером по городу за 1-2 дня",
            "policy_returns": "Товар должен быть в упаковке",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["storefront_description"] == "Продаём качественную обувь с 2020 года"
    assert body["contact_phone"] == "+79280001122"
    assert body["contact_whatsapp"] == "+79280001122"
    assert body["contact_telegram"] == "berkat_shop"  # "@" отброшен
    assert body["storefront_min_order_total"] == "1000.00"
    assert body["policy_refund_money"] == "Возврат в течение 14 дней"
    assert body["policy_payment"] == "Наличными или картой при получении"
    assert body["policy_delivery"] == "Курьером по городу за 1-2 дня"
    assert body["policy_returns"] == "Товар должен быть в упаковке"

    response = await client.get("/api/auth/shop", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.json()["contact_telegram"] == "berkat_shop"


async def test_update_shop_invalid_telegram_username_rejected_via_api(client, owner_headers):
    response = await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "contact_telegram": "a"},  # короче 5 символов
    )
    assert response.status_code == 400, response.text


async def test_update_shop_invalid_contact_phone_rejected_via_api(client, owner_headers):
    response = await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "contact_phone": "не телефон"},
    )
    assert response.status_code == 400, response.text


async def test_update_shop_clear_min_order_total_via_api(client, owner_headers):
    """Явный null сбрасывает лимит; отсутствие поля в body его не трогает."""
    response = await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "storefront_min_order_total": "500"},
    )
    assert response.json()["storefront_min_order_total"] == "500.00"

    # поле отсутствует в body — значение не меняется
    response = await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат"}
    )
    assert response.json()["storefront_min_order_total"] == "500.00"

    # явный null — сброс
    response = await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "storefront_min_order_total": None},
    )
    assert response.status_code == 200, response.text
    assert response.json()["storefront_min_order_total"] is None


async def test_shop_logo_upload_and_delete_via_api(client, owner_headers):
    response = await client.post(
        "/api/auth/shop/logo",
        headers=owner_headers,
        files={"file": ("logo.png", _test_logo_bytes(), "image/png")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["logo"]

    response = await client.delete("/api/auth/shop/logo", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.json()["logo"] == ""


async def test_storefront_profile_full_fields_via_api(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)
    await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={
            "name": "Магазин Беркат",
            "storefront_description": "О нас",
            "contact_phone": "+79280001122",
            "contact_whatsapp": "+79280001133",
            "contact_telegram": "berkat_shop",
            "storefront_min_order_total": "1000",
            "policy_refund_money": "14 дней",
        },
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()

    response = await client.get(f"/api/storefront/{slug}/profile")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["name"] == "Магазин Беркат"
    assert body["slug"] == slug
    assert body["description"] == "О нас"
    assert "on_platform_since" in body
    assert body["rating"] == {"average_rating": 0.0, "reviews_count": 0}
    assert body["products_count"] == 1
    assert body["orders_count"] is None  # новый магазин без продаж — скрыт
    assert body["orders_count_label"] is None
    assert body["min_order_total"] == "1000.00"
    assert body["contacts"] == {
        "phone": "+79280001122",
        "whatsapp": "+79280001133",
        "telegram": "berkat_shop",
    }
    assert body["addresses"] == [{"name": "Основной склад", "address": "ул. Мира, 1"}]
    assert body["policies"]["refund_money"] == "14 дней"
    # пустые policies -> null, чтобы фронт не рисовал пустой пункт FAQ
    assert body["policies"]["payment"] is None
    assert body["policies"]["delivery"] is None
    assert body["policies"]["returns"] is None

    # товар с product_id смысла не имеет тут, просто проверим что он существует
    assert product["id"] > 0


async def test_storefront_profile_hidden_warehouse_not_in_addresses_via_api(client, owner_headers):
    """Склад без show_on_storefront не должен попадать в публичные адреса."""
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    # склад 1 остаётся скрытым (show_on_storefront по умолчанию False)

    response = await client.get(f"/api/storefront/{slug}/profile")
    assert response.status_code == 200, response.text
    assert response.json()["addresses"] == []


async def test_storefront_profile_404_disabled_or_missing_via_api(client, owner_headers):
    response = await client.get("/api/storefront/no-such-shop/profile")
    assert response.status_code == 404, response.text

    # витрина существует, но выключена
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": False}
    )
    response = await client.get(f"/api/storefront/{slug}/profile")
    assert response.status_code == 404, response.text


async def _setup_accepted_request(client, owner_headers, buyer_headers, slug="magazin-berkat", price="120"):
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Товар с отзывом",
                "purchase_price": "50",
                "retail_price": price,
            },
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()
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
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]

    due = (date.today() + timedelta(days=3)).isoformat()
    response = await client.post(
        f"/api/storefront/requests/{request_id}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )
    assert response.status_code == 200, response.text
    return product, request_id


async def test_storefront_profile_rating_ignores_hidden_reviews_via_api(client, owner_headers, customer_headers):
    """Рейтинг магазина — среднее по всем видимым отзывам всех товаров,
    скрытые (is_hidden) не учитываются (промпт B2 п.2)."""
    slug = "magazin-berkat"
    buyer1, _ = await customer_headers()
    buyer2, _ = await customer_headers()
    product, request_id_1 = await _setup_accepted_request(client, owner_headers, buyer1, slug)

    response = await client.post(
        "/api/reviews",
        headers=buyer1,
        json={"storefront_request_id": request_id_1, "product_id": product["id"], "rating": 5, "text": "Отлично"},
    )
    assert response.status_code == 201, response.text

    # второй отзыв (на СВОЙ товар той же второй заявки — _setup_accepted_request
    # создаёт новый товар каждый раз), будет скрыт
    product_2, request_id_2 = await _setup_accepted_request(client, owner_headers, buyer2, slug)
    response = await client.post(
        "/api/reviews",
        headers=buyer2,
        json={"storefront_request_id": request_id_2, "product_id": product_2["id"], "rating": 1, "text": "Плохо"},
    )
    assert response.status_code == 201, response.text
    hidden_review_id = response.json()["id"]

    # рейтинг магазина учитывает оба отзыва
    response = await client.get(f"/api/storefront/{slug}/profile")
    assert response.json()["rating"] == {"average_rating": 3.0, "reviews_count": 2}

    # скрываем второй отзыв
    response = await client.post(f"/api/reviews/{hidden_review_id}/hide", headers=owner_headers)
    assert response.status_code == 200, response.text

    response = await client.get(f"/api/storefront/{slug}/profile")
    assert response.json()["rating"] == {"average_rating": 5.0, "reviews_count": 1}


async def test_storefront_profile_orders_count_shown_above_threshold_via_api(
    client, owner_headers, customer_headers
):
    """orders_count/label появляются только начиная с порога (5 заказов) —
    у нового магазина с малым числом продаж скрыты (null)."""
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "20", "cost": "10"}]},
    )

    due = (date.today() + timedelta(days=3)).isoformat()
    for _ in range(4):
        buyer, _ = await customer_headers()
        request_id = (
            await client.post(
                f"/api/storefront/{slug}/requests",
                headers=buyer,
                json={"customer_name": "Покупатель", "items": [{"product_id": product["id"], "quantity": "1"}]},
            )
        ).json()["id"]
        response = await client.post(
            f"/api/storefront/requests/{request_id}/accept",
            headers=owner_headers,
            json={"warehouse_id": 1, "due_date": due},
        )
        assert response.status_code == 200, response.text

    # 4 принятых заявки — ещё ниже порога (5)
    response = await client.get(f"/api/storefront/{slug}/profile")
    assert response.json()["orders_count"] is None

    # пятая заявка — порог достигнут
    buyer, _ = await customer_headers()
    request_id = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            headers=buyer,
            json={"customer_name": "Покупатель", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()["id"]
    response = await client.post(
        f"/api/storefront/requests/{request_id}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )
    assert response.status_code == 200, response.text

    response = await client.get(f"/api/storefront/{slug}/profile")
    body = response.json()
    assert body["orders_count"] == 5
    assert body["orders_count_label"] == "5"


async def test_storefront_product_page_includes_shop_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)
    await client.post(
        "/api/auth/shop/logo",
        headers=owner_headers,
        files={"file": ("logo.png", _test_logo_bytes(), "image/png")},
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    shop = response.json()["product"]["shop"]
    assert shop["slug"] == slug
    assert shop["name"] == "Магазин Беркат"
    assert shop["logo"]  # загруженный логотип
    assert shop["average_rating"] == 0.0
    assert shop["reviews_count"] == 0


async def test_storefront_catalog_includes_min_order_total_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "storefront_enabled": True, "storefront_min_order_total": "1000"},
    )

    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 200, response.text
    assert response.json()["min_order_total"] == "1000.00"


async def test_storefront_request_below_min_order_total_rejected_via_api(client, owner_headers, customer_headers):
    """Сумма заявки по серверным ценам (с учётом цены варианта) ниже
    минимальной суммы заказа — 400 с точным текстом ошибки."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "storefront_enabled": True, "storefront_min_order_total": "1000"},
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Дешёвый товар", "purchase_price": "50", "retail_price": "100"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()

    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={"customer_name": "Покупатель", "items": [{"product_id": product["id"], "quantity": "1"}]},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Минимальная сумма заказа в этом магазине — 1\u202f000 ₽"


async def test_storefront_request_exact_min_order_total_passes_via_api(client, owner_headers, customer_headers):
    """Граница: сумма заявки РОВНО равна минимуму — заявка проходит (не строгое <)."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "storefront_enabled": True, "storefront_min_order_total": "1000"},
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар ровно на минимум", "purchase_price": "500", "retail_price": "1000"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()

    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={"customer_name": "Покупатель", "items": [{"product_id": product["id"], "quantity": "1"}]},
    )
    assert response.status_code == 201, response.text


async def test_storefront_request_min_order_total_uses_variant_price_via_api(client, owner_headers, customer_headers):
    """Сумма заявки считается по цене ВАРИАНТА, если она задана, а не по
    retail_price товара (баг из README «Найденные проблемы», попутно исправлен)."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "storefront_enabled": True, "storefront_min_order_total": "1000"},
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Товар с дорогим вариантом",
                "purchase_price": "100",
                "retail_price": "100",  # низкая базовая цена
                "variants": [{"size": "L", "color": "Синий", "price": "1200"}],  # цена варианта выше минимума
            },
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()
    variant_id = product["variants"][0]["id"]

    # если бы считали по retail_price (100), заявка не прошла бы минимум (1000)
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={
            "customer_name": "Покупатель",
            "items": [{"product_id": product["id"], "quantity": "1", "variant_id": variant_id}],
        },
    )
    assert response.status_code == 201, response.text


async def test_storefront_request_no_min_order_total_not_enforced_via_api(client, owner_headers, customer_headers):
    """Если storefront_min_order_total не задан — проверка не применяется вообще."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Дешёвый товар", "purchase_price": "1", "retail_price": "1"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()

    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={"customer_name": "Покупатель", "items": [{"product_id": product["id"], "quantity": "1"}]},
    )
    assert response.status_code == 201, response.text


async def test_storefront_profile_tenant_isolation_via_api(client, owner_headers, random_phone):
    """Профиль одного магазина не должен утекать данные другого."""
    other_response = await client.post(
        "/api/auth/register",
        json={
            "shop_name": "Другой магазин",
            "owner_name": "Другой владелец",
            "phone": random_phone(),
            "password": "secret123",
            "personal_data_consent": True,
        },
    )
    other_headers = {"Authorization": f"Bearer {other_response.json()['access_token']}"}
    await client.patch(
        "/api/auth/shop",
        headers=other_headers,
        json={"name": "Другой магазин", "storefront_enabled": True, "storefront_description": "Чужое описание"},
    )

    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "storefront_enabled": True, "storefront_description": "Своё описание"},
    )

    response = await client.get(f"/api/storefront/{slug}/profile")
    assert response.status_code == 200, response.text
    assert response.json()["description"] == "Своё описание"

    # PATCH /api/auth/shop владельца одного магазина не должен менять данные другого
    response = await client.get("/api/auth/shop", headers=other_headers)
    assert response.json()["storefront_description"] == "Чужое описание"
