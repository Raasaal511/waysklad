from datetime import date, timedelta


async def _setup_accepted_request(client, owner_headers, buyer_headers, slug="magazin-berkat"):
    """Магазин с витриной, товар, принятая заявка — общий сетап для тестов отзывов."""
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
                "retail_price": "120",
                "show_on_storefront": True,
            },
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


async def test_review_full_flow_via_api(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, buyer_headers, slug)

    # без авторизации отзыв не оставить
    response = await client.post(
        "/api/reviews",
        json={"storefront_request_id": request_id, "product_id": product["id"], "rating": 5, "text": "Отлично"},
    )
    assert response.status_code == 401, response.text

    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={
            "storefront_request_id": request_id,
            "product_id": product["id"],
            "rating": 5,
            "text": "Очень доволен покупкой",
        },
    )
    assert response.status_code == 201, response.text
    review = response.json()
    assert review["rating"] == 5
    assert review["author_name"] == "Ахмед"
    assert review["is_hidden"] is None  # покупателю флаг скрытости не показываем

    # повторный отзыв по той же заявке запрещён
    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={
            "storefront_request_id": request_id,
            "product_id": product["id"],
            "rating": 3,
            "text": "Ещё раз",
        },
    )
    assert response.status_code == 400, response.text

    # публичный список отзывов на товар + агрегат
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reviews_count"] == 1
    assert body["average_rating"] == 5.0
    assert body["reviews"][0]["text"] == "Очень доволен покупкой"

    # каталог и карточка товара отдают агрегат рейтинга
    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 200, response.text
    catalog_product = next(p for p in response.json()["products"] if p["id"] == product["id"])
    assert catalog_product["average_rating"] == 5.0
    assert catalog_product["reviews_count"] == 1

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["product"]["average_rating"] == 5.0


async def test_review_requires_accepted_request(client, owner_headers, customer_headers):
    """Отзыв на NEW-заявку (ещё не принятую владельцем) запрещён."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "120", "show_on_storefront": True},
        )
    ).json()
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
    )
    request_id = response.json()["id"]

    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={"storefront_request_id": request_id, "product_id": product["id"], "rating": 5},
    )
    assert response.status_code == 403, response.text


async def test_review_rejects_product_not_in_request(client, owner_headers, customer_headers):
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, buyer_headers, slug)

    other_product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Другой товар",
                "purchase_price": "10",
                "retail_price": "20",
                "show_on_storefront": True,
            },
        )
    ).json()

    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={"storefront_request_id": request_id, "product_id": other_product["id"], "rating": 4},
    )
    assert response.status_code == 400, response.text


async def test_review_rejects_foreign_request(client, owner_headers, customer_headers):
    """Покупатель не может оставить отзыв по чужой заявке (не своей)."""
    slug = "magazin-berkat"
    buyer_headers, _ = await customer_headers()
    other_buyer_headers, _ = await customer_headers()
    product, request_id = await _setup_accepted_request(client, owner_headers, buyer_headers, slug)

    response = await client.post(
        "/api/reviews",
        headers=other_buyer_headers,
        json={"storefront_request_id": request_id, "product_id": product["id"], "rating": 5},
    )
    assert response.status_code == 404, response.text


async def test_review_moderation_via_api(client, owner_headers, customer_headers):
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
            "text": "Неадекватный отзыв",
        },
    )
    review_id = response.json()["id"]

    # владелец видит отзыв в панели (включая скрытость)
    response = await client.get(f"/api/reviews/product/{product['id']}", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.json()[0]["is_hidden"] is False

    # скрываем
    response = await client.post(f"/api/reviews/{review_id}/hide", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.json()["is_hidden"] is True

    # скрытый отзыв больше не виден публично и не входит в агрегат
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews")
    body = response.json()
    assert body["reviews_count"] == 0
    assert body["reviews"] == []

    response = await client.get(f"/api/storefront/{slug}")
    catalog_product = next(p for p in response.json()["products"] if p["id"] == product["id"])
    assert catalog_product["reviews_count"] == 0

    # возвращаем
    response = await client.post(f"/api/reviews/{review_id}/unhide", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.json()["is_hidden"] is False

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}/reviews")
    assert response.json()["reviews_count"] == 1
