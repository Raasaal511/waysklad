"""M-B1: справочник категорий платформы, город магазина, проверенный магазин,
старая цена товара — тесты по разделу 7 промпта M-B1
(docs/MARKETPLACE_HOME_PROMPTS.md)."""

from datetime import date, timedelta
from decimal import Decimal

from app.domain.catalog.entities import Category
from app.domain.platform.category_synonyms import match_platform_slug


async def _admin_headers(client) -> dict:
    response = await client.post(
        "/api/admin/login", json={"login": "test-admin", "password": "test-admin-password"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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
    tenant_id = body["user"]  # placeholder, overwritten below if needed

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


async def _make_sale(client, headers, warehouse_id, product_id, qty="1", price="50"):
    response = await client.post(
        "/api/sales",
        headers=headers,
        json={
            "warehouse_id": warehouse_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": qty, "price": price}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# 1. Справочник категорий платформы
# ---------------------------------------------------------------------------


async def test_platform_categories_seeded_by_migration_equivalent(client):
    """Сид платформенных категорий применяется через миграцию (не через API) —
    здесь проверяем, что справочник вообще доступен и админка его видит."""
    headers = await _admin_headers(client)
    response = await client.get("/api/admin/platform-categories", headers=headers)
    assert response.status_code == 200, response.text
    slugs = {c["slug"] for c in response.json()}
    assert "electronics" in slugs
    assert "shoes" in slugs


async def test_category_synonym_matching():
    assert match_platform_slug("Обувь") == "shoes"
    assert match_platform_slug("кроссовки") == "shoes"
    assert match_platform_slug("  Туфли ") == "shoes"
    assert match_platform_slug("Ёлочные игрушки") is None  # ё->е нормализация не создаёт ложных совпадений
    assert match_platform_slug("одежда") == "clothing"
    assert match_platform_slug("Совершенно неизвестное") is None


async def test_map_platform_categories_script(make_uow, create_shop, db_session_factory, monkeypatch):
    """scripts/map_platform_categories.py — одноразовый скрипт автосопоставления
    категорий магазина по словарю синонимов. Скрипт по умолчанию открывает
    SqlAlchemyUnitOfWork() без явного session_factory (реальная БД при запуске
    через `python -m scripts...`) — здесь подменяем дефолтный session_factory
    модуля на тестовую БД (тот же приём, что использует сам фреймворк для client)."""
    from scripts.map_platform_categories import map_categories

    monkeypatch.setattr(
        "app.infrastructure.db.uow.SqlAlchemyUnitOfWork.__init__.__defaults__",
        (db_session_factory,),
    )

    tenant_id, _, _ = await create_shop()
    async with make_uow(tenant_id) as uow:
        shoes_category = await uow.categories.add(Category(id=None, name="Кроссовки"))
        unknown_category = await uow.categories.add(Category(id=None, name="Загадочная категория"))
        await uow.commit()

    await map_categories()

    async with make_uow(tenant_id) as uow:
        refreshed_shoes = await uow.categories.get(shoes_category.id)
        refreshed_unknown = await uow.categories.get(unknown_category.id)
    assert refreshed_shoes.platform_category_id is not None
    assert refreshed_unknown.platform_category_id is None


async def test_owner_sets_platform_category_on_shop_category(client, owner_headers):
    admin_headers = await _admin_headers(client)
    categories_response = await client.get("/api/admin/platform-categories", headers=admin_headers)
    electronics_id = next(c["id"] for c in categories_response.json() if c["slug"] == "electronics")

    create_response = await client.post(
        "/api/products/categories", headers=owner_headers, json={"name": "Гаджеты"}
    )
    assert create_response.status_code == 201, create_response.text
    category_id = create_response.json()["id"]
    assert create_response.json()["platform_category_id"] is None

    update_response = await client.put(
        f"/api/products/categories/{category_id}",
        headers=owner_headers,
        json={"name": "Гаджеты", "platform_category_id": electronics_id},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["platform_category_id"] == electronics_id

    list_response = await client.get("/api/products/categories", headers=owner_headers)
    updated = next(c for c in list_response.json() if c["id"] == category_id)
    assert updated["platform_category_id"] == electronics_id


async def test_marketplace_categories_public_endpoint(client, random_phone):
    admin_headers = await _admin_headers(client)
    categories_response = await client.get("/api/admin/platform-categories", headers=admin_headers)
    shoes_id = next(c["id"] for c in categories_response.json() if c["slug"] == "shoes")

    headers, slug, wh = await _register_shop(client, random_phone, "Магазин обуви")
    category_response = await client.post(
        "/api/products/categories", headers=headers, json={"name": "Обувь"}
    )
    category_id = category_response.json()["id"]
    await client.put(
        f"/api/products/categories/{category_id}",
        headers=headers,
        json={"name": "Обувь", "platform_category_id": shoes_id},
    )
    product = await _add_product(client, headers, wh, "Кроссовки Nike", "3000", category_id=category_id)

    response = await client.get("/api/marketplace/categories")
    assert response.status_code == 200, response.text
    categories = response.json()["categories"]
    by_slug = {c["slug"]: c for c in categories}
    assert "shoes" in by_slug
    assert by_slug["shoes"]["products_count"] >= 1

    # категории без товаров не отдаются вовсе
    for item in categories:
        assert item["products_count"] > 0

    # фильтр каталога по platform_category включает дочерние — тут проверяем прямое совпадение
    filtered = await client.get(
        "/api/marketplace/products", params={"platform_category": "shoes"}
    )
    assert filtered.status_code == 200, filtered.text
    ids = [p["id"] for p in filtered.json()["products"]]
    assert product["id"] in ids

    other_filtered = await client.get(
        "/api/marketplace/products", params={"platform_category": "electronics"}
    )
    assert product["id"] not in [p["id"] for p in other_filtered.json()["products"]]


async def test_marketplace_platform_category_filter_includes_children(client, random_phone):
    admin_headers = await _admin_headers(client)
    parent_response = await client.post(
        "/api/admin/platform-categories",
        headers=admin_headers,
        json={"name": "Родитель М-Б1", "slug": "parent-mb1-test"},
    )
    assert parent_response.status_code == 201, parent_response.text
    parent_id = parent_response.json()["id"]

    child_response = await client.post(
        "/api/admin/platform-categories",
        headers=admin_headers,
        json={"name": "Ребёнок М-Б1", "slug": "child-mb1-test", "parent_id": parent_id},
    )
    assert child_response.status_code == 201, child_response.text
    child_id = child_response.json()["id"]

    headers, slug, wh = await _register_shop(client, random_phone, "Магазин иерархии")
    category_response = await client.post(
        "/api/products/categories", headers=headers, json={"name": "Дочерняя категория магазина"}
    )
    category_id = category_response.json()["id"]
    await client.put(
        f"/api/products/categories/{category_id}",
        headers=headers,
        json={"name": "Дочерняя категория магазина", "platform_category_id": child_id},
    )
    product = await _add_product(client, headers, wh, "Товар в дочерней категории", "500", category_id=category_id)

    response = await client.get(
        "/api/marketplace/products", params={"platform_category": "parent-mb1-test"}
    )
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["products"]]
    assert product["id"] in ids  # фильтр по родителю находит товар из дочерней категории


async def test_admin_platform_category_crud_and_soft_delete(client, random_phone):
    admin_headers = await _admin_headers(client)

    create_response = await client.post(
        "/api/admin/platform-categories",
        headers=admin_headers,
        json={"name": "Тестовая категория", "slug": "test-crud-category"},
    )
    assert create_response.status_code == 201, create_response.text
    category_id = create_response.json()["id"]

    update_response = await client.put(
        f"/api/admin/platform-categories/{category_id}",
        headers=admin_headers,
        json={"name": "Обновлённая", "slug": "test-crud-category", "sort_order": 5, "is_active": True},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["name"] == "Обновлённая"

    # без привязок — физическое удаление
    delete_response = await client.delete(
        f"/api/admin/platform-categories/{category_id}", headers=admin_headers
    )
    assert delete_response.status_code == 200, delete_response.text

    all_response = await client.get("/api/admin/platform-categories", headers=admin_headers)
    assert category_id not in [c["id"] for c in all_response.json()]

    # с привязкой (товар/категория магазина использует её) — мягкое отключение
    create_response = await client.post(
        "/api/admin/platform-categories",
        headers=admin_headers,
        json={"name": "С привязкой", "slug": "test-crud-bound"},
    )
    bound_id = create_response.json()["id"]
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин с привязкой")
    category_response = await client.post(
        "/api/products/categories", headers=headers, json={"name": "Категория с привязкой"}
    )
    shop_category_id = category_response.json()["id"]
    await client.put(
        f"/api/products/categories/{shop_category_id}",
        headers=headers,
        json={"name": "Категория с привязкой", "platform_category_id": bound_id},
    )

    delete_response = await client.delete(
        f"/api/admin/platform-categories/{bound_id}", headers=admin_headers
    )
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["is_active"] is False

    all_response = await client.get("/api/admin/platform-categories", headers=admin_headers)
    still_there = next(c for c in all_response.json() if c["id"] == bound_id)
    assert still_there["is_active"] is False


async def test_admin_platform_categories_require_token(client):
    response = await client.get("/api/admin/platform-categories")
    assert response.status_code == 401, response.text
    response = await client.post(
        "/api/admin/platform-categories", json={"name": "X", "slug": "x-no-auth"}
    )
    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# 2. Город магазина
# ---------------------------------------------------------------------------


async def test_shop_city_get_patch_validation(client, owner_headers):
    response = await client.get("/api/auth/shop", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.json()["city"] is None

    response = await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "city": "Грозный"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["city"] == "Грозный"

    response = await client.get("/api/auth/shop", headers=owner_headers)
    assert response.json()["city"] == "Грозный"

    response = await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "city": "Москва"}
    )
    assert response.status_code == 400, response.text


async def test_marketplace_cities_and_city_filter(client, random_phone):
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин Грозного")
    await client.patch(
        "/api/auth/shop", headers=headers_a, json={"name": "Магазин Грозного", "city": "Грозный"}
    )
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин Шали")
    await client.patch(
        "/api/auth/shop", headers=headers_b, json={"name": "Магазин Шали", "city": "Шали"}
    )

    product_a = await _add_product(client, headers_a, wh_a, "Товар Грозного", "100")
    product_b = await _add_product(client, headers_b, wh_b, "Товар Шали", "100")

    cities_response = await client.get("/api/marketplace/cities")
    assert cities_response.status_code == 200, cities_response.text
    by_name = {c["name"]: c["shops_count"] for c in cities_response.json()["cities"]}
    assert by_name.get("Грозный", 0) >= 1
    assert by_name.get("Шали", 0) >= 1

    filtered = await client.get("/api/marketplace/products", params={"city": "Грозный"})
    ids = [p["id"] for p in filtered.json()["products"]]
    assert product_a["id"] in ids
    assert product_b["id"] not in ids


async def test_marketplace_cities_excludes_shops_without_storefront(client, random_phone):
    headers, slug, wh = await _register_shop(
        client, random_phone, "Магазин без витрины", storefront_enabled=False
    )
    await client.patch(
        "/api/auth/shop", headers=headers, json={"name": "Магазин без витрины", "city": "Аргун"}
    )
    response = await client.get("/api/marketplace/cities")
    by_name = {c["name"]: c["shops_count"] for c in response.json()["cities"]}
    # магазин без витрины не должен попасть в счётчик — используем большое
    # значение как признак отсутствия влияния (сравнение с 0 ненадёжно при
    # параллельных тестах в одной БД, поэтому проверяем отдельный уникальный город)
    assert "Аргун" not in by_name or by_name["Аргун"] == 0


# ---------------------------------------------------------------------------
# 3. Проверенный магазин
# ---------------------------------------------------------------------------


async def test_admin_verify_unverify_tenant(client, random_phone):
    register = await client.post(
        "/api/auth/register",
        json={
            "shop_name": "Магазин для проверки",
            "owner_name": "Владелец",
            "phone": random_phone(),
            "password": "secret123",
        },
    )
    tenant_name = "Магазин для проверки"
    admin_headers = await _admin_headers(client)

    list_response = await client.get("/api/admin/tenants", headers=admin_headers)
    tenant_id = next(t["id"] for t in list_response.json()["tenants"] if t["name"] == tenant_name)

    detail_response = await client.get(f"/api/admin/tenants/{tenant_id}", headers=admin_headers)
    assert detail_response.json()["is_verified"] is False

    verify_response = await client.post(
        f"/api/admin/tenants/{tenant_id}/verify", headers=admin_headers
    )
    assert verify_response.status_code == 200, verify_response.text
    assert verify_response.json()["is_verified"] is True

    list_response = await client.get("/api/admin/tenants", headers=admin_headers)
    listed = next(t for t in list_response.json()["tenants"] if t["id"] == tenant_id)
    assert listed["is_verified"] is True

    unverify_response = await client.post(
        f"/api/admin/tenants/{tenant_id}/unverify", headers=admin_headers
    )
    assert unverify_response.status_code == 200, unverify_response.text
    assert unverify_response.json()["is_verified"] is False


async def test_verify_requires_admin_token(client, random_phone):
    response = await client.post("/api/admin/tenants/1/verify")
    assert response.status_code == 401, response.text


async def test_verify_unknown_tenant_returns_404(client):
    admin_headers = await _admin_headers(client)
    response = await client.post("/api/admin/tenants/999999/verify", headers=admin_headers)
    assert response.status_code == 404, response.text


async def test_marketplace_shows_shop_is_verified(client, random_phone):
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин проверки на витрине")
    product = await _add_product(client, headers, wh, "Проверяемый товар", "100")

    response = await client.get("/api/marketplace/products", params={"shop_slug": slug})
    by_id = {p["id"]: p for p in response.json()["products"]}
    assert by_id[product["id"]]["shop_is_verified"] is False

    admin_headers = await _admin_headers(client)
    list_response = await client.get("/api/admin/tenants", headers=admin_headers)
    tenant_id = next(t["id"] for t in list_response.json()["tenants"] if t["name"] == "Магазин проверки на витрине")
    await client.post(f"/api/admin/tenants/{tenant_id}/verify", headers=admin_headers)

    response = await client.get("/api/marketplace/products", params={"shop_slug": slug})
    by_id = {p["id"]: p for p in response.json()["products"]}
    assert by_id[product["id"]]["shop_is_verified"] is True


# ---------------------------------------------------------------------------
# 4. Старая цена (compare_at_price)
# ---------------------------------------------------------------------------


async def test_compare_at_price_validation_on_create(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Товар с неверной скидкой",
            "purchase_price": "50",
            "retail_price": "200",
            "compare_at_price": "150",  # меньше retail_price — должно быть 400
        },
    )
    assert response.status_code == 400, response.text
    assert "Старая цена" in response.json()["detail"]

    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Товар со скидкой",
            "purchase_price": "50",
            "retail_price": "200",
            "compare_at_price": "250",
        },
    )
    assert response.status_code == 201, response.text
    assert Decimal(response.json()["compare_at_price"]) == Decimal("250")


async def test_compare_at_price_validation_on_update(client, owner_headers):
    create_response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар для апдейта", "purchase_price": "50", "retail_price": "200"},
    )
    product_id = create_response.json()["id"]

    update_response = await client.put(
        f"/api/products/{product_id}",
        headers=owner_headers,
        json={
            "name": "Товар для апдейта", "purchase_price": "50", "retail_price": "200",
            "compare_at_price": "199",
        },
    )
    assert update_response.status_code == 400, update_response.text

    update_response = await client.put(
        f"/api/products/{product_id}",
        headers=owner_headers,
        json={
            "name": "Товар для апдейта", "purchase_price": "50", "retail_price": "200",
            "compare_at_price": "300",
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert Decimal(update_response.json()["compare_at_price"]) == Decimal("300")


async def test_compare_at_price_hidden_when_retail_price_raised_above_it(client, random_phone):
    """Если retail_price позже подняли выше старой цены — скидка на витрине не
    отдаётся, но compare_at_price в БД не трогается (промпт M-B1 п.4)."""
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин переменной цены")
    product = await _add_product(
        client, headers, wh, "Товар с плавающей ценой", "100", compare_at_price="150"
    )
    assert product["compare_at_price"] == "150.00"

    storefront_response = await client.get(f"/api/storefront/{slug}")
    item = next(p for p in storefront_response.json()["products"] if p["id"] == product["id"])
    assert item["old_price"] == "150.00"
    assert item["discount_percent"] is not None

    # поднимаем retail_price выше compare_at_price
    update_response = await client.put(
        f"/api/products/{product['id']}",
        headers=headers,
        json={
            "name": "Товар с плавающей ценой", "purchase_price": "10", "retail_price": "200",
            "compare_at_price": "150", "show_on_storefront": True,
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["compare_at_price"] == "150.00"  # в БД не тронуто

    storefront_response = await client.get(f"/api/storefront/{slug}")
    item = next(p for p in storefront_response.json()["products"] if p["id"] == product["id"])
    assert item["old_price"] is None  # на витрине скидка не показывается
    assert item["discount_percent"] is None


async def test_discount_percent_rounds_down_and_hides_below_3_percent(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    # (200-195)/200 = 2.5% -> ниже порога 3%, не должно показываться
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Товар с маленькой скидкой", "purchase_price": "10",
            "retail_price": "195", "compare_at_price": "200", "show_on_storefront": True,
        },
    )
    product_id = response.json()["id"]
    detail = await client.get(f"/api/products/{product_id}", headers=owner_headers)
    assert detail.json()["compare_at_price"] == "200.00"  # хранится как есть

    storefront_response = await client.get(f"/api/storefront/{slug}")
    item = next(p for p in storefront_response.json()["products"] if p["id"] == product_id)
    assert item["discount_percent"] is None  # < 3% не показываем
    assert item["old_price"] is None


async def test_compare_at_price_does_not_affect_storefront_request_amount(client, random_phone, customer_headers):
    """Заявка с витрины считается по retail_price — compare_at_price на деньги не влияет."""
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин заявок со скидкой")
    product = await _add_product(
        client, headers, wh, "Товар заявки", "100", compare_at_price="200"
    )

    buyer_headers, _ = await customer_headers()
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        headers=buyer_headers,
        json={"customer_name": "Покупатель", "items": [{"product_id": product["id"], "quantity": "2"}]},
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]

    due = (date.today() + timedelta(days=3)).isoformat()
    accept_response = await client.post(
        f"/api/storefront/requests/{request_id}/accept",
        headers=headers,
        json={"warehouse_id": wh, "due_date": due},
    )
    assert accept_response.status_code == 200, accept_response.text
    order = accept_response.json()
    assert Decimal(order["total"]) == Decimal("200.00")  # 2 x retail_price=100, не compare_at_price


async def test_with_discount_filter_marketplace_and_storefront(client, random_phone):
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин фильтра скидок")
    discounted = await _add_product(
        client, headers, wh, "Товар со скидкой на фильтр", "100", compare_at_price="150"
    )
    regular = await _add_product(client, headers, wh, "Товар без скидки на фильтр", "100")

    marketplace_response = await client.get(
        "/api/marketplace/products", params={"with_discount": True, "shop_slug": slug}
    )
    ids = [p["id"] for p in marketplace_response.json()["products"]]
    assert discounted["id"] in ids
    assert regular["id"] not in ids

    storefront_response = await client.get(
        f"/api/storefront/{slug}", params={"with_discount": True}
    )
    ids = [p["id"] for p in storefront_response.json()["products"]]
    assert discounted["id"] in ids
    assert regular["id"] not in ids


# ---------------------------------------------------------------------------
# 5. Поля карточки маркетплейса: shop_logo, is_new, is_hit
# ---------------------------------------------------------------------------


async def test_shop_logo_upload(client, owner_headers, random_phone):
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (400, 400), color=(10, 200, 10)).save(buffer, "JPEG")
    response = await client.post(
        "/api/auth/shop/logo",
        headers=owner_headers,
        files={"file": ("logo.jpg", buffer.getvalue(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    logo_url = response.json()["logo"]
    assert logo_url.startswith("/uploads/")

    shop_response = await client.get("/api/auth/shop", headers=owner_headers)
    assert shop_response.json()["logo"] == logo_url

    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product_response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Товар с логотипом магазина", "purchase_price": "10", "retail_price": "100",
            "show_on_storefront": True,
        },
    )
    marketplace_response = await client.get(
        "/api/marketplace/products", params={"shop_slug": slug}
    )
    item = next(
        p for p in marketplace_response.json()["products"] if p["id"] == product_response.json()["id"]
    )
    assert item["shop_logo"] == logo_url


async def test_marketplace_is_new_badge(client, random_phone):
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин новинок")
    product = await _add_product(client, headers, wh, "Новый товар", "100")

    response = await client.get("/api/marketplace/products", params={"shop_slug": slug})
    by_id = {p["id"]: p for p in response.json()["products"]}
    assert by_id[product["id"]]["is_new"] is True  # только что созданный товар — новинка

    detail_response = await client.get(f"/api/marketplace/products/{product['id']}")
    assert detail_response.json()["is_new"] is True


async def test_marketplace_is_hit_badge(client, random_phone):
    """Топ-10% по продажам за 30 дней среди видимых товаров платформы, минимум
    5 продаж — с одним товаром и 5 продажами он автоматически топ-100%."""
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин хитов")
    product = await _add_product(client, headers, wh, "Хитовый товар", "50", qty="20")

    for _ in range(5):
        await _make_sale(client, headers, wh, product["id"], qty="1")

    response = await client.get("/api/marketplace/products", params={"shop_slug": slug, "sort": "popular"})
    assert response.status_code == 200, response.text
    by_id = {p["id"]: p for p in response.json()["products"]}
    assert by_id[product["id"]]["is_hit"] is True


async def test_marketplace_is_hit_requires_minimum_five_sales(client, random_phone):
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин почти хитов")
    product = await _add_product(client, headers, wh, "Товар с малым числом продаж", "50", qty="20")
    for _ in range(2):
        await _make_sale(client, headers, wh, product["id"], qty="1")

    response = await client.get("/api/marketplace/products", params={"shop_slug": slug})
    by_id = {p["id"]: p for p in response.json()["products"]}
    assert by_id[product["id"]]["is_hit"] is False


# ---------------------------------------------------------------------------
# 6. Новые сортировки
# ---------------------------------------------------------------------------


async def test_marketplace_sort_popular(client, random_phone):
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин сортировки популярности")
    slow = await _add_product(client, headers, wh, "Медленный товар", "100", qty="20")
    fast = await _add_product(client, headers, wh, "Быстрый товар", "100", qty="20")

    for _ in range(3):
        await _make_sale(client, headers, wh, fast["id"], qty="1")
    await _make_sale(client, headers, wh, slow["id"], qty="1")

    response = await client.get(
        "/api/marketplace/products", params={"shop_slug": slug, "sort": "popular"}
    )
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["products"]]
    assert ids.index(fast["id"]) < ids.index(slow["id"])


async def test_marketplace_sort_rating(client, random_phone, customer_headers):
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин сортировки рейтинга")
    low_rated = await _add_product(client, headers, wh, "Товар с низким рейтингом", "100")
    high_rated = await _add_product(client, headers, wh, "Товар с высоким рейтингом", "100")

    async def leave_review(product_id, rating):
        buyer_headers, _ = await customer_headers()
        response = await client.post(
            f"/api/storefront/{slug}/requests",
            headers=buyer_headers,
            json={"customer_name": "Покупатель", "items": [{"product_id": product_id, "quantity": "1"}]},
        )
        request_id = response.json()["id"]
        due = (date.today() + timedelta(days=3)).isoformat()
        accept = await client.post(
            f"/api/storefront/requests/{request_id}/accept",
            headers=headers, json={"warehouse_id": wh, "due_date": due},
        )
        order_id = accept.json()["id"]
        for status in ("in_progress", "ready"):
            await client.patch(f"/api/orders/{order_id}/status", headers=headers, json={"new_status": status})
        await client.post(f"/api/orders/{order_id}/issue", headers=headers, json={"payment_method": "cash"})
        await client.post(
            "/api/reviews", headers=buyer_headers,
            json={"storefront_request_id": request_id, "product_id": product_id, "rating": rating, "text": "т"},
        )

    await leave_review(low_rated["id"], 2)
    await leave_review(high_rated["id"], 5)

    response = await client.get(
        "/api/marketplace/products", params={"shop_slug": slug, "sort": "rating"}
    )
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["products"]]
    assert ids.index(high_rated["id"]) < ids.index(low_rated["id"])


async def test_marketplace_sort_discount(client, random_phone):
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин сортировки скидок")
    small_discount = await _add_product(
        client, headers, wh, "Маленькая скидка", "190", compare_at_price="200"
    )
    big_discount = await _add_product(
        client, headers, wh, "Большая скидка", "100", compare_at_price="200"
    )
    no_discount = await _add_product(client, headers, wh, "Без скидки", "100")

    response = await client.get(
        "/api/marketplace/products", params={"shop_slug": slug, "sort": "discount"}
    )
    assert response.status_code == 200, response.text
    products = response.json()["products"]
    ids = [p["id"] for p in products]
    assert ids.index(big_discount["id"]) < ids.index(small_discount["id"])
    # без скидки — discount_percent null, должны быть в конце (NULLS LAST)
    assert ids.index(no_discount["id"]) > ids.index(small_discount["id"])


async def test_storefront_sort_popular_rating_discount(client, owner_headers):
    """Те же сортировки, но у одиночной витрины (/api/storefront/{slug})."""
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Витринный товар со скидкой", "purchase_price": "10",
            "retail_price": "100", "compare_at_price": "150", "show_on_storefront": True,
        },
    )
    product_id = response.json()["id"]

    response = await client.get(f"/api/storefront/{slug}", params={"sort": "discount"})
    assert response.status_code == 200, response.text
    response = await client.get(f"/api/storefront/{slug}", params={"sort": "popular"})
    assert response.status_code == 200, response.text
    response = await client.get(f"/api/storefront/{slug}", params={"sort": "rating"})
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# 7. Изоляция tenant и скрытые товары (доп. проверки к уже существующим в test_marketplace.py)
# ---------------------------------------------------------------------------


async def test_marketplace_excludes_suspended_shop(client, random_phone):
    headers, slug, wh = await _register_shop(client, random_phone, "Магазин под блокировкой")
    product = await _add_product(client, headers, wh, "Товар заблокированного магазина", "100")

    admin_headers = await _admin_headers(client)
    list_response = await client.get("/api/admin/tenants", headers=admin_headers)
    tenant_id = next(t["id"] for t in list_response.json()["tenants"] if t["name"] == "Магазин под блокировкой")
    await client.post(f"/api/admin/tenants/{tenant_id}/suspend", headers=admin_headers)

    response = await client.get("/api/marketplace/products", params={"shop_slug": slug})
    ids = [p["id"] for p in response.json()["products"]]
    assert product["id"] not in ids


async def test_marketplace_hit_and_rating_isolated_per_tenant(client, random_phone):
    """is_hit/рейтинг одного магазина не влияют на другой — товар без продаж
    у другого продавца не становится хитом только потому, что где-то на
    платформе есть хиты."""
    headers_a, slug_a, wh_a = await _register_shop(client, random_phone, "Магазин с хитом")
    headers_b, slug_b, wh_b = await _register_shop(client, random_phone, "Магазин без хита")

    hit_product = await _add_product(client, headers_a, wh_a, "Товар-хит", "50", qty="20")
    for _ in range(5):
        await _make_sale(client, headers_a, wh_a, hit_product["id"], qty="1")

    quiet_product = await _add_product(client, headers_b, wh_b, "Тихий товар", "50")

    response = await client.get("/api/marketplace/products", params={"shop_slug": slug_b})
    by_id = {p["id"]: p for p in response.json()["products"]}
    assert by_id[quiet_product["id"]]["is_hit"] is False
