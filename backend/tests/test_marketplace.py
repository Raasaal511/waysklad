"""Общий каталог платформы (/api/marketplace/products) — витрина сразу всех
магазинов, в отличие от /api/storefront/{slug} (один магазин)."""

from datetime import date, timedelta
from decimal import Decimal


async def _register_shop(client, random_phone, shop_name: str, storefront_enabled: bool = True):
    response = await client.post(
        "/api/auth/register",
        json={
            "shop_name": shop_name,
            "owner_name": "Продавец",
            "phone": random_phone(),
            "password": "secret123",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    slug = body["shop_slug"]

    if storefront_enabled:
        response = await client.patch(
            "/api/auth/shop", headers=headers, json={"name": shop_name, "storefront_enabled": True}
        )
        assert response.status_code == 200, response.text

    warehouse_response = await client.post(
        "/api/inventory/warehouses", headers=headers, json={"name": "Основной склад"}
    )
    assert warehouse_response.status_code == 201, warehouse_response.text
    warehouse_id = warehouse_response.json()["id"]

    # show_on_storefront выставляется только явным обновлением, не при создании (см. WarehouseCreateRequest)
    update_response = await client.put(
        f"/api/inventory/warehouses/{warehouse_id}",
        headers=headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )
    assert update_response.status_code == 200, update_response.text

    return headers, slug, warehouse_id


async def _leave_review(client, owner_headers, buyer_headers, slug, product_id, warehouse_id, rating):
    """Полный флоу: заявка -> accept -> issue -> отзыв — единственный способ
    оставить отзыв (см. tests/api/test_reviews.py)."""
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={"customer_name": "Покупатель", "items": [{"product_id": product_id, "quantity": "1"}]},
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]
    due = (date.today() + timedelta(days=3)).isoformat()
    response = await client.post(
        f"/api/storefront/requests/{request_id}/accept",
        headers=owner_headers,
        json={"warehouse_id": warehouse_id, "due_date": due},
    )
    assert response.status_code == 200, response.text
    order_id = response.json()["id"]
    for status in ("in_progress", "ready"):
        response = await client.patch(
            f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": status}
        )
        assert response.status_code == 200, response.text
    response = await client.post(
        f"/api/orders/{order_id}/issue", headers=owner_headers, json={"payment_method": "cash"}
    )
    assert response.status_code == 200, response.text
    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={
            "storefront_request_id": request_id,
            "product_id": product_id,
            "rating": rating,
            "text": "Отзыв для теста",
        },
    )
    assert response.status_code == 201, response.text


async def _add_product(client, headers, warehouse_id, name, price, qty="10", **extra):
    response = await client.post(
        "/api/products",
        headers=headers,
        json={
            "name": name,
            "purchase_price": "10",
            "retail_price": price,
            "show_on_storefront": True,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    product = response.json()

    if qty != "0":  # без приёмки товар остаётся без остатка — эквивалент qty=0
        receive_response = await client.post(
            "/api/inventory/receive",
            headers=headers,
            json={
                "warehouse_id": warehouse_id,
                "lines": [{"product_id": product["id"], "quantity": qty}],
            },
        )
        assert receive_response.status_code == 201, receive_response.text
    return product


async def test_marketplace_lists_products_from_multiple_shops(client, random_phone):
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин Алиса")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин Борис")

    product_a = await _add_product(client, headers_a, wh_a, "Товар А", "100")
    product_b = await _add_product(client, headers_b, wh_b, "Товар Б", "200")

    response = await client.get("/api/marketplace/products")
    assert response.status_code == 200, response.text
    body = response.json()

    by_id = {p["id"]: p for p in body["products"]}
    assert product_a["id"] in by_id
    assert product_b["id"] in by_id
    assert by_id[product_a["id"]]["shop_slug"] == slug_a
    assert by_id[product_a["id"]]["shop_name"] == "Магазин Алиса"
    assert by_id[product_b["id"]]["shop_slug"] == slug_b
    assert by_id[product_b["id"]]["shop_name"] == "Магазин Борис"
    assert body["total"] >= 2

    # покупателю не отдаём закупочную цену
    assert "purchase_price" not in by_id[product_a["id"]]
    assert set(by_id[product_a["id"]].keys()) == {
        "id", "name", "retail_price", "photo", "category_name", "in_stock",
        "min_order_qty", "order_step_qty", "shop_slug", "shop_name",
        "sold_count", "average_rating", "reviews_count",
    }


async def test_marketplace_excludes_shop_with_storefront_disabled(client, random_phone):
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Открытый магазин")
    headers_b, slug_b, wh_b = await _register_shop(
        client, random_phone, "Закрытый магазин", storefront_enabled=False
    )

    product_a = await _add_product(client, headers_a, wh_a, "Видимый товар", "100")
    product_b = await _add_product(client, headers_b, wh_b, "Невидимый товар", "150")

    response = await client.get("/api/marketplace/products")
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["products"]]
    assert product_a["id"] in ids
    assert product_b["id"] not in ids


async def test_marketplace_hidden_warehouse_marks_product_out_of_stock(client, random_phone):
    headers, slug, _visible_wh = await _register_shop(client, random_phone, "Магазин со складами")

    hidden_wh_response = await client.post(
        "/api/inventory/warehouses", headers=headers, json={"name": "Скрытый склад"}
    )
    assert hidden_wh_response.status_code == 201, hidden_wh_response.text
    hidden_wh_id = hidden_wh_response.json()["id"]
    # show_on_storefront=False — дефолт при создании (см. Warehouse.show_on_storefront),
    # явно передавать его в POST бессмысленно: WarehouseCreateRequest такого поля не принимает

    product = await _add_product(client, headers, hidden_wh_id, "Товар на скрытом складе", "100")

    response = await client.get("/api/marketplace/products", params={"shop_slug": slug})
    assert response.status_code == 200, response.text
    by_id = {p["id"]: p for p in response.json()["products"]}
    assert product["id"] in by_id  # товар остаётся видимым в каталоге
    assert by_id[product["id"]]["in_stock"] is False  # но не в наличии — остаток только на скрытом складе


async def test_marketplace_filter_by_shop_slug(client, random_phone):
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Первый магазин")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Второй магазин")

    product_a = await _add_product(client, headers_a, wh_a, "Товар первого", "100")
    product_b = await _add_product(client, headers_b, wh_b, "Товар второго", "100")

    response = await client.get("/api/marketplace/products", params={"shop_slug": slug_a})
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [p["id"] for p in body["products"]]
    assert product_a["id"] in ids
    assert product_b["id"] not in ids
    assert all(p["shop_slug"] == slug_a for p in body["products"])


async def test_marketplace_filters_price_stock_and_category(client, random_phone):
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин с фильтрами")

    category_response = await client.post(
        "/api/products/categories", headers=headers, json={"name": "Обувь"}
    )
    assert category_response.status_code == 201, category_response.text
    category_id = category_response.json()["id"]

    cheap_in_stock = await _add_product(
        client, headers, wh, "Дешёвый в наличии", "50", qty="5", category_id=category_id
    )
    expensive_in_stock = await _add_product(
        client, headers, wh, "Дорогой в наличии", "500", qty="5"
    )
    cheap_out_of_stock = await _add_product(
        client, headers, wh, "Дешёвый без остатка", "60", qty="0"
    )

    # price_min/price_max
    response = await client.get(
        "/api/marketplace/products", params={"price_min": "40", "price_max": "100"}
    )
    ids = [p["id"] for p in response.json()["products"]]
    assert cheap_in_stock["id"] in ids
    assert cheap_out_of_stock["id"] in ids
    assert expensive_in_stock["id"] not in ids

    # in_stock_only
    response = await client.get("/api/marketplace/products", params={"in_stock_only": True})
    ids = [p["id"] for p in response.json()["products"]]
    assert cheap_in_stock["id"] in ids
    assert expensive_in_stock["id"] in ids
    assert cheap_out_of_stock["id"] not in ids

    # category
    response = await client.get("/api/marketplace/products", params={"category": "Обувь"})
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["products"]]
    assert cheap_in_stock["id"] in ids
    assert expensive_in_stock["id"] not in ids
    assert response.json()["products"][0]["category_name"] == "Обувь"


async def test_marketplace_pagination_across_shops(client, random_phone):
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин пагинации А")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин пагинации Б")

    for i in range(3):
        await _add_product(client, headers_a, wh_a, f"Товар А{i}", "100")
    for i in range(3):
        await _add_product(client, headers_b, wh_b, f"Товар Б{i}", "100")

    response = await client.get("/api/marketplace/products", params={"limit": 2, "offset": 0})
    assert response.status_code == 200, response.text
    first_page = response.json()
    assert len(first_page["products"]) == 2
    assert first_page["total"] >= 6

    response = await client.get("/api/marketplace/products", params={"limit": 2, "offset": 2})
    assert response.status_code == 200, response.text
    second_page = response.json()
    assert len(second_page["products"]) == 2

    first_ids = {p["id"] for p in first_page["products"]}
    second_ids = {p["id"] for p in second_page["products"]}
    assert first_ids.isdisjoint(second_ids)


async def test_marketplace_no_shops_returns_empty(client):
    response = await client.get("/api/marketplace/products")
    assert response.status_code == 200, response.text
    assert response.json() == {"products": [], "total": 0}


async def test_marketplace_shows_sold_count_and_rating(client, random_phone, customer_headers):
    """Кросс-tenant агрегаты (sold_count/rating) считаются по конкретному
    товару, не перетекают между магазинами — товар без продаж/отзывов у
    другого продавца остаётся с нулями."""
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин с отзывом")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин без отзывов")

    product_a = await _add_product(client, headers_a, wh_a, "Товар с историей", "100")
    product_b = await _add_product(client, headers_b, wh_b, "Товар без истории", "50")

    buyer_headers, _ = await customer_headers()
    response = await client.post(
        f"/api/storefront/{slug_a}/requests",
        headers=buyer_headers,
        json={"customer_name": "Ахмед", "items": [{"product_id": product_a["id"], "quantity": "1"}]},
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]

    due = (date.today() + timedelta(days=3)).isoformat()
    response = await client.post(
        f"/api/storefront/requests/{request_id}/accept",
        headers=headers_a,
        json={"warehouse_id": wh_a, "due_date": due},
    )
    assert response.status_code == 200, response.text
    order_id = response.json()["id"]

    # sold_count считается по Sale, не по Order — нужно провести заказ до выдачи
    for status in ("in_progress", "ready"):
        response = await client.patch(
            f"/api/orders/{order_id}/status", headers=headers_a, json={"new_status": status}
        )
        assert response.status_code == 200, response.text
    response = await client.post(
        f"/api/orders/{order_id}/issue", headers=headers_a, json={"payment_method": "cash"}
    )
    assert response.status_code == 200, response.text

    response = await client.post(
        "/api/reviews",
        headers=buyer_headers,
        json={
            "storefront_request_id": request_id,
            "product_id": product_a["id"],
            "rating": 4,
            "text": "Хороший товар",
        },
    )
    assert response.status_code == 201, response.text

    response = await client.get("/api/marketplace/products")
    assert response.status_code == 200, response.text
    by_id = {p["id"]: p for p in response.json()["products"]}

    assert Decimal(by_id[product_a["id"]]["sold_count"]) == 1
    assert by_id[product_a["id"]]["average_rating"] == 4.0
    assert by_id[product_a["id"]]["reviews_count"] == 1

    assert Decimal(by_id[product_b["id"]]["sold_count"]) == 0
    assert by_id[product_b["id"]]["average_rating"] == 0.0
    assert by_id[product_b["id"]]["reviews_count"] == 0


async def test_marketplace_min_rating_filter(client, random_phone, customer_headers):
    """Фильтр применяется ДО пагинации (SQL, не постфактум в Python) — товар
    без отзывов не проходит фильтр даже min_rating=1 (NULL не >= 1 в SQL)."""
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин рейтингов")
    high_rated = await _add_product(client, headers_a, wh_a, "Хороший", "100")
    low_rated = await _add_product(client, headers_a, wh_a, "Так себе", "100")
    no_reviews = await _add_product(client, headers_a, wh_a, "Без отзывов", "100")

    buyer1, _ = await customer_headers()
    await _leave_review(client, headers_a, buyer1, slug_a, high_rated["id"], wh_a, rating=5)
    buyer2, _ = await customer_headers()
    await _leave_review(client, headers_a, buyer2, slug_a, low_rated["id"], wh_a, rating=2)

    response = await client.get("/api/marketplace/products", params={"min_rating": 4})
    assert response.status_code == 200, response.text
    ids = {p["id"] for p in response.json()["products"]}
    assert high_rated["id"] in ids
    assert low_rated["id"] not in ids
    assert no_reviews["id"] not in ids

    response = await client.get("/api/marketplace/products", params={"min_rating": 1})
    ids = {p["id"] for p in response.json()["products"]}
    assert high_rated["id"] in ids
    assert low_rated["id"] in ids
    assert no_reviews["id"] not in ids
