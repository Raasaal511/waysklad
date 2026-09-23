"""Тесты промпта B4 — похожие товары: GET /storefront/{slug}/products/{id}/similar
(scope=shop и scope=marketplace)."""

from tests.test_admin import _admin_headers


async def _add_category(client, headers, name: str, parent_id: int | None = None) -> int:
    response = await client.post(
        "/api/products/categories", headers=headers, json={"name": name, "parent_id": parent_id}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _add_product(client, headers, warehouse_id, name, price, qty="10", **extra):
    show_on_storefront = extra.pop("show_on_storefront", True)
    response = await client.post(
        "/api/products",
        headers=headers,
        json={
            "name": name,
            "purchase_price": "10",
            "retail_price": price,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    product = response.json()
    if show_on_storefront:
        update_response = await client.put(
            f"/api/products/{product['id']}",
            headers=headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
        assert update_response.status_code == 200, update_response.text
        product = update_response.json()

    if qty != "0":
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


async def _sell(client, headers, warehouse_id, product_id, price="500", qty="1"):
    response = await client.post(
        "/api/sales",
        headers=headers,
        json={
            "warehouse_id": warehouse_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": qty, "price": price}],
            "cash_received": "100000",
        },
    )
    assert response.status_code == 201, response.text


async def _register_shop(client, random_phone, shop_name: str, storefront_enabled: bool = True):
    response = await client.post(
        "/api/auth/register",
        json={
            "shop_name": shop_name,
            "owner_name": "Продавец",
            "phone": random_phone(),
            "password": "secret123",
            "personal_data_consent": True,
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

    update_response = await client.put(
        f"/api/inventory/warehouses/{warehouse_id}",
        headers=headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )
    assert update_response.status_code == 200, update_response.text

    return headers, slug, warehouse_id


# ---------- scope=shop ----------


async def test_similar_shop_priority_category_then_parent_then_rest(client, owner_headers):
    """Порядок групп: та же категория -> та же родительская категория -> остальные."""
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )

    parent_id = await _add_category(client, owner_headers, "Электроника")
    same_category_id = await _add_category(client, owner_headers, "Наушники", parent_id)
    sibling_category_id = await _add_category(client, owner_headers, "Колонки", parent_id)
    other_category_id = await _add_category(client, owner_headers, "Одежда")

    current = await _add_product(
        client, owner_headers, 1, "Текущий товар", "1000", category_id=same_category_id
    )
    same_cat = await _add_product(
        client, owner_headers, 1, "Такая же категория", "1000", category_id=same_category_id
    )
    same_parent = await _add_product(
        client, owner_headers, 1, "Та же родительская", "1000", category_id=sibling_category_id
    )
    other = await _add_product(
        client, owner_headers, 1, "Другая категория", "1000", category_id=other_category_id
    )

    response = await client.get(f"/api/storefront/{slug}/products/{current['id']}/similar")
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["shop_products"]]

    assert ids.index(same_cat["id"]) < ids.index(same_parent["id"])
    assert ids.index(same_parent["id"]) < ids.index(other["id"])
    assert current["id"] not in ids  # текущий товар исключён


async def test_similar_shop_priority_in_stock_then_sold_count(client, owner_headers):
    """Внутри одной группы приоритета: сначала в наличии, затем по sold_count убыв."""
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )

    current = await _add_product(client, owner_headers, 1, "Текущий", "500")
    out_of_stock = await _add_product(client, owner_headers, 1, "Без остатка", "500", qty="0")
    low_sales = await _add_product(client, owner_headers, 1, "Мало продано", "500", qty="10")
    high_sales = await _add_product(client, owner_headers, 1, "Много продано", "500", qty="10")

    await _sell(client, owner_headers, 1, high_sales["id"], price="500", qty="3")
    await _sell(client, owner_headers, 1, low_sales["id"], price="500", qty="1")

    response = await client.get(f"/api/storefront/{slug}/products/{current['id']}/similar")
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["shop_products"]]

    # оба товара в наличии идут раньше товара без остатка
    assert ids.index(high_sales["id"]) < ids.index(out_of_stock["id"])
    assert ids.index(low_sales["id"]) < ids.index(out_of_stock["id"])
    # среди товаров в наличии — больше продаж раньше
    assert ids.index(high_sales["id"]) < ids.index(low_sales["id"])


async def test_similar_shop_excludes_hidden_products(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )

    current = await _add_product(client, owner_headers, 1, "Текущий", "500")
    hidden = await _add_product(
        client, owner_headers, 1, "Скрытый", "500", show_on_storefront=False
    )
    visible = await _add_product(client, owner_headers, 1, "Видимый", "500")

    response = await client.get(f"/api/storefront/{slug}/products/{current['id']}/similar")
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["shop_products"]]

    assert hidden["id"] not in ids
    assert visible["id"] in ids


async def test_similar_shop_limit_capped_at_20(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    current = await _add_product(client, owner_headers, 1, "Текущий", "500", qty="0")

    response = await client.get(
        f"/api/storefront/{slug}/products/{current['id']}/similar",
        params={"limit": 999},
    )
    assert response.status_code == 422, response.text  # limit > 20 отклоняется валидацией


async def test_similar_shop_unknown_product_404(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    response = await client.get(f"/api/storefront/{slug}/products/999999/similar")
    assert response.status_code == 404, response.text


# ---------- scope=marketplace ----------


async def test_similar_marketplace_matches_by_category_name_excludes_own_shop(client, random_phone):
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин А")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин Б")

    category_a = await _add_category(client, headers_a, "Наушники")
    category_b = await _add_category(client, headers_b, "Наушники")  # то же название, другой tenant

    current = await _add_product(client, headers_a, wh_a, "Товар А", "1000", category_id=category_a)
    same_shop_same_category = await _add_product(
        client, headers_a, wh_a, "Другой товар А", "1000", category_id=category_a
    )
    other_shop_same_category = await _add_product(
        client, headers_b, wh_b, "Товар Б", "1000", category_id=category_b
    )

    response = await client.get(
        f"/api/storefront/{slug_a}/products/{current['id']}/similar",
        params={"scope": "marketplace"},
    )
    assert response.status_code == 200, response.text
    items = response.json()["marketplace_products"]
    ids = [p["id"] for p in items]
    shop_slugs = {p["shop_slug"] for p in items}

    assert other_shop_same_category["id"] in ids
    assert same_shop_same_category["id"] not in ids  # свой магазин исключён целиком
    assert current["id"] not in ids
    assert slug_a not in shop_slugs


async def test_similar_marketplace_hidden_product_not_included(client, random_phone):
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин А")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин Б")

    category_a = await _add_category(client, headers_a, "Обувь")
    category_b = await _add_category(client, headers_b, "Обувь")

    current = await _add_product(client, headers_a, wh_a, "Товар А", "1000", category_id=category_a)
    hidden = await _add_product(
        client, headers_b, wh_b, "Скрытый товар Б", "1000",
        category_id=category_b, show_on_storefront=False,
    )

    response = await client.get(
        f"/api/storefront/{slug_a}/products/{current['id']}/similar",
        params={"scope": "marketplace"},
    )
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["marketplace_products"]]
    assert hidden["id"] not in ids


async def test_similar_marketplace_blocked_shop_not_included(client, random_phone):
    """Магазин, заблокированный админом (is_suspended), не должен попадать
    в похожие товары маркетплейса, даже с совпадающей категорией."""
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин А")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин для блокировки")

    category_a = await _add_category(client, headers_a, "Игрушки")
    category_b = await _add_category(client, headers_b, "Игрушки")

    current = await _add_product(client, headers_a, wh_a, "Товар А", "1000", category_id=category_a)
    to_block = await _add_product(
        client, headers_b, wh_b, "Товар заблокированного магазина", "1000", category_id=category_b
    )

    admin_hdrs = await _admin_headers(client)
    tenants = (await client.get("/api/admin/tenants", headers=admin_hdrs)).json()["tenants"]
    tenant_id = next(t["id"] for t in tenants if t["name"] == "Магазин для блокировки")
    suspend_response = await client.post(
        f"/api/admin/tenants/{tenant_id}/suspend", headers=admin_hdrs
    )
    assert suspend_response.status_code == 200, suspend_response.text

    response = await client.get(
        f"/api/storefront/{slug_a}/products/{current['id']}/similar",
        params={"scope": "marketplace"},
    )
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["marketplace_products"]]
    assert to_block["id"] not in ids


async def test_similar_marketplace_falls_back_to_name_similarity(
    client, random_phone, db_session_factory
):
    """Меньше limit совпадений по категории -> добор по похожести названия.
    Явно гоним через ILIKE-фолбэк (DROP EXTENSION), а не полагаемся на
    состояние по умолчанию — pg_trgm мог остаться установленным в общей
    тестовой БД воркера от другого теста этого файла (extension переживает
    Base.metadata.drop_all/create_all, тот чистит только таблицы), и тогда
    тест перестаёт быть детерминированным по порядку запуска."""
    async with db_session_factory() as session:
        from sqlalchemy import text

        await session.execute(text("DROP EXTENSION IF EXISTS pg_trgm"))
        await session.commit()

    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин А")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин Б")

    current = await _add_product(client, headers_a, wh_a, "Беспроводные наушники Aurum", "1000")
    name_match = await _add_product(
        client, headers_b, wh_b, "Беспроводные наушники Silver", "1200"
    )
    unrelated = await _add_product(client, headers_b, wh_b, "Совершенно другой товар", "500")

    response = await client.get(
        f"/api/storefront/{slug_a}/products/{current['id']}/similar",
        params={"scope": "marketplace"},
    )
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["marketplace_products"]]
    assert name_match["id"] in ids


async def test_similar_marketplace_response_shape_matches_catalog(client, random_phone):
    """Формат элемента — как в GET /marketplace/products (shop_slug, shop_name и т.д.)."""
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин А")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин Б")

    category_a = await _add_category(client, headers_a, "Спорт")
    category_b = await _add_category(client, headers_b, "Спорт")

    current = await _add_product(client, headers_a, wh_a, "Товар А", "1000", category_id=category_a)
    await _add_product(client, headers_b, wh_b, "Товар Б", "800", category_id=category_b)

    response = await client.get(
        f"/api/storefront/{slug_a}/products/{current['id']}/similar",
        params={"scope": "marketplace"},
    )
    assert response.status_code == 200, response.text
    items = response.json()["marketplace_products"]
    assert len(items) >= 1
    item = items[0]
    for field in (
        "id", "name", "retail_price", "photo", "category_name", "in_stock",
        "shop_slug", "shop_name", "sold_count", "average_rating", "reviews_count",
        "shop_logo", "shop_is_verified", "shop_city", "old_price", "discount_percent",
        "is_new", "is_hit",
    ):
        assert field in item


async def test_similar_endpoint_invalid_scope_422(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = await _add_product(client, owner_headers, 1, "Товар", "500")
    response = await client.get(
        f"/api/storefront/{slug}/products/{product['id']}/similar",
        params={"scope": "bogus"},
    )
    assert response.status_code == 422, response.text


async def test_similar_marketplace_uses_pg_trgm_when_extension_available(client, random_phone, db_session_factory):
    """Тестовая БД (create_all, не Alembic) не ставит pg_trgm сама — эмулируем
    окружение, где расширение доступно (реальный прод-Postgres с locale
    en_US.utf8, см. отчёт), и проверяем, что репозиторий реально идёт по
    similarity()-ветке (не падает, отдаёт совпадение) — не только ILIKE-фолбэк,
    который остальные тесты этого файла уже покрывают неявно (extension
    отсутствует в тестовой БД по умолчанию)."""
    async with db_session_factory() as session:
        from sqlalchemy import text

        await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await session.commit()

    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин А")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин Б")

    # ASCII-имена — trigram-сравнение под C-локалью тестовой БД корректно
    # работает только для ASCII (см. отчёт: под C кириллица не даёт триграмм,
    # это особенность локали кластера, не бага кода — прод использует
    # en_US.utf8, где similarity() для кириллицы работает штатно)
    current = await _add_product(client, headers_a, wh_a, "Wireless Headphones Aurum", "1000")
    name_match = await _add_product(client, headers_b, wh_b, "Wireless Headphones Silver", "1200")
    await _add_product(client, headers_b, wh_b, "Completely Unrelated Item", "500")

    response = await client.get(
        f"/api/storefront/{slug_a}/products/{current['id']}/similar",
        params={"scope": "marketplace"},
    )
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["marketplace_products"]]
    assert name_match["id"] in ids
