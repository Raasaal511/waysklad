"""Тесты промпта B1 — расширенная карточка товара витрины: название варианта,
наличие по вариантам, категория/единица, гарантия, просмотры за 90 дней."""

from decimal import Decimal

from app.application.storefront.get_product import StorefrontProductResult


def test_storefront_product_result_from_json_survives_old_cache_entry():
    """Кэш карточки (TTL 20с) может пережить деплой: старая запись без
    stock_level/stock_qty/category/variant_stock/show_stock_qty (записанная
    до промпта B1) должна читаться с безопасными дефолтами, не падать."""
    old_shape = {
        "shop_name": "Магазин",
        "product": {
            "id": 1,
            "name": "Старый товар",
            "unit_code": "pcs",
            "purchase_price": "100",
            "retail_price": "200",
            "compare_at_price": None,
            "sku": "",
            "barcode": None,
            "category_id": None,
            "photo": "",
            "description": "",
            "storefront_photos": [],
            "min_stock": "0",
            "show_on_storefront": True,
            "storefront_min_qty": None,
            "storefront_step_qty": None,
            "variants": [
                {
                    "id": 1, "size": "M", "color": "Красный",
                    "barcode": None, "photo": "", "price": None,
                    # намеренно без "name" — как в записях до B1
                }
            ],
        },
        "in_stock": True,
        "sold_count": "0",
        # намеренно без stock_level/stock_qty/show_stock_qty/variant_stock/category
    }

    result = StorefrontProductResult.from_json(old_shape)

    assert result.in_stock is True
    assert result.stock_level == "in"  # выведено из старого in_stock
    assert result.stock_qty is None
    assert result.show_stock_qty is False
    assert result.variant_stock == {}
    assert result.category is None
    assert result.product.warranty_text == ""
    assert result.product.variants[0].name == ""
    assert result.views_90d == 0  # пересчитывается отдельно в execute(), не из кеша


def test_storefront_product_result_roundtrip_with_new_fields():
    """Новый формат (to_json -> from_json) сохраняет все поля B1, кроме
    views_90d — он намеренно не участвует в кеше (см. get_product.py)."""
    from app.application.storefront.get_product import CategoryWithParent, VariantStock
    from app.domain.catalog.entities import Category, Product, ProductVariant
    from app.domain.common.money import Money
    from app.domain.common.quantity import UNITS
    from app.domain.reviews.repository import ProductRatingAggregate

    product = Product(
        id=1, name="Товар", unit=UNITS["pcs"],
        purchase_price=Money.of("100"), retail_price=Money.of("200"),
        warranty_text="Гарантия 12 месяцев",
        variants=[ProductVariant(id=5, size="M", color="Красный", name="Aurum")],
    )
    result = StorefrontProductResult(
        shop_name="Магазин",
        product=product,
        in_stock=True,
        stock_level="low",
        stock_qty=Decimal("3"),
        show_stock_qty=True,
        variant_stock={5: VariantStock(variant_id=5, in_stock=True, stock_level="low", quantity=Decimal("3"))},
        category=CategoryWithParent(
            category=Category(id=2, name="Наушники", parent_id=1),
            parent=Category(id=1, name="Электроника"),
        ),
        sold_count=Decimal("10"),
        rating=ProductRatingAggregate(average_rating=4.5, reviews_count=2),
        views_90d=42,
    )

    restored = StorefrontProductResult.from_json(result.to_json())

    assert restored.stock_level == "low"
    assert restored.stock_qty == Decimal("3")
    assert restored.show_stock_qty is True
    assert restored.variant_stock[5].in_stock is True
    assert restored.category.category.name == "Наушники"
    assert restored.category.parent.name == "Электроника"
    assert restored.product.warranty_text == "Гарантия 12 месяцев"
    assert restored.product.variants[0].name == "Aurum"
    assert restored.views_90d == 0  # намеренно не сериализуется, см. to_json()


async def _enable_storefront_with_warehouse(client, owner_headers, warehouse_id: int = 1):
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    response = await client.put(
        f"/api/inventory/warehouses/{warehouse_id}",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )
    assert response.status_code == 200, response.text


async def test_variant_display_name_three_cases_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)

    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Наушники",
                "purchase_price": "1000",
                "retail_price": "2000",
                "variants": [
                    {"size": "", "color": "", "name": "Aurum"},  # 1: явное имя
                    {"size": "M", "color": "Красный"},  # 2: цвет · размер
                    {"size": "", "color": ""},  # 3: ни имени, ни цвета/размера
                ],
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

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    variants = response.json()["product"]["variants"]
    by_id = {v["id"]: v for v in variants}
    ordered = [by_id[v["id"]] for v in product["variants"]]

    assert ordered[0]["display_name"] == "Aurum"
    assert ordered[1]["display_name"] == "Красный · M"
    assert ordered[2]["display_name"] == "Вариант 3"


async def test_variant_out_of_stock_product_in_stock_via_api(client, owner_headers):
    """Один вариант без остатка не должен считаться в наличии, даже если
    товар в целом (по другому варианту) есть на складе."""
    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)

    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Платье",
                "purchase_price": "500",
                "retail_price": "1500",
                "variants": [{"size": "M", "color": "Красный"}, {"size": "L", "color": "Красный"}],
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
    in_stock_variant_id = product["variants"][0]["id"]
    out_of_stock_variant_id = product["variants"][1]["id"]

    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [
                {
                    "product_id": product["id"],
                    "variant_id": in_stock_variant_id,
                    "quantity": "5",
                    "cost": "500",
                }
            ],
        },
    )
    assert response.status_code == 201, response.text

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    body = response.json()["product"]
    assert body["in_stock"] is True  # товар в целом есть на складе

    variants_by_id = {v["id"]: v for v in body["variants"]}
    assert variants_by_id[in_stock_variant_id]["in_stock"] is True
    assert variants_by_id[out_of_stock_variant_id]["in_stock"] is False
    assert variants_by_id[out_of_stock_variant_id]["stock_level"] == "out"


async def test_stock_qty_null_or_number_by_shop_setting_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)

    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Кроссовки", "purchase_price": "1000", "retail_price": "3000"},
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
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "7", "cost": "1000"}]},
    )

    # настройка выключена по умолчанию — stock_qty скрыт
    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["product"]["stock_qty"] is None

    # владелец включает точный остаток
    response = await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "storefront_show_stock_qty": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["storefront_show_stock_qty"] is True

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["product"]["stock_qty"] == "7.000"


async def test_hidden_warehouse_stock_not_visible_publicly_via_api(client, owner_headers):
    """Остаток на скрытом от витрины складе не должен ни попадать в
    публичный stock_qty, ни делать товар «в наличии»."""
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": "Магазин Беркат", "storefront_enabled": True, "storefront_show_stock_qty": True},
    )
    # склад 1 остаётся скрытым от витрины (дефолт show_on_storefront=False)
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар со скрытого склада", "purchase_price": "10", "retail_price": "50"},
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
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "20", "cost": "10"}]},
    )
    assert response.status_code == 201, response.text

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    body = response.json()["product"]
    assert body["in_stock"] is False
    # настройка включена, но остаток скрытого склада не должен в неё попасть —
    # видимый остаток равен нулю, а не 20 (реальному остатку на скрытом складе)
    assert body["stock_qty"] == "0.000"
    assert body["stock_level"] == "out"


async def test_category_with_parent_and_unit_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)

    parent = (
        await client.post("/api/products/categories", headers=owner_headers, json={"name": "Электроника"})
    ).json()
    child = (
        await client.post(
            "/api/products/categories",
            headers=owner_headers,
            json={"name": "Наушники", "parent_id": parent["id"]},
        )
    ).json()
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "AirPods",
                "purchase_price": "1000",
                "retail_price": "2000",
                "category_id": child["id"],
                "unit_code": "pcs",
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

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    body = response.json()["product"]
    assert body["category"]["id"] == child["id"]
    assert body["category"]["name"] == "Наушники"
    assert body["category"]["parent"] == {"id": parent["id"], "name": "Электроника"}
    assert body["unit_code"] == "pcs"
    assert body["unit_label"] == "шт"

    # товар без категории — category: null
    no_category = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Без категории", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    no_category = (
        await client.put(
            f"/api/products/{no_category['id']}",
            headers=owner_headers,
            json={**no_category, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()
    response = await client.get(f"/api/storefront/{slug}/products/{no_category['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["product"]["category"] is None


async def test_warranty_text_on_storefront_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)

    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Телефон",
                "purchase_price": "10000",
                "retail_price": "20000",
                "warranty_text": "Гарантия 12 месяцев",
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

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["product"]["warranty_text"] == "Гарантия 12 месяцев"

    # в каталоге гарантии нет — список остаётся лёгким
    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 200, response.text
    listed = next(p for p in response.json()["products"] if p["id"] == product["id"])
    assert "warranty_text" not in listed


async def test_record_product_view_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар для просмотров", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()

    response = await client.post(f"/api/storefront/{slug}/products/{product['id']}/view")
    assert response.status_code == 204, response.text

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["product"]["views_90d"] == 1

    # без авторизации, без тела — доступно анонимному покупателю
    response = await client.post(f"/api/storefront/{slug}/products/{product['id']}/view")
    assert response.status_code == 204, response.text


async def test_repeat_view_same_ip_not_double_counted_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар дедупликации", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()

    for _ in range(3):
        response = await client.post(f"/api/storefront/{slug}/products/{product['id']}/view")
        assert response.status_code == 204, response.text

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    # тестовый httpx-клиент всегда бьёт с одного IP (127.0.0.1 у ASGITransport) —
    # повторные просмотры в течение TTL дедупликации не должны увеличивать счётчик
    assert response.json()["product"]["views_90d"] == 1


async def test_view_hidden_or_missing_product_404_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)
    hidden = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Скрытый товар", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()

    response = await client.post(f"/api/storefront/{slug}/products/{hidden['id']}/view")
    assert response.status_code == 404, response.text

    response = await client.post(f"/api/storefront/{slug}/products/999999/view")
    assert response.status_code == 404, response.text

    response = await client.post(f"/api/storefront/no-such-shop/products/{hidden['id']}/view")
    assert response.status_code == 404, response.text


async def test_views_90d_ignores_older_than_90_days_via_api(client, owner_headers, make_uow):
    """views_90d — сумма только за последние 90 дней; старые записи
    product_view_daily не должны учитываться."""
    from datetime import date, timedelta

    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар с историей просмотров", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    product = (
        await client.put(
            f"/api/products/{product['id']}",
            headers=owner_headers,
            json={**product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()

    tenant_slug_response = await client.get("/api/auth/shop", headers=owner_headers)
    tenant_id = tenant_slug_response.json()["id"]

    async with make_uow(tenant_id) as uow:
        await uow.product_views.record_view(product["id"], date.today() - timedelta(days=200))
        await uow.product_views.record_view(product["id"], date.today() - timedelta(days=95))
        await uow.product_views.record_view(product["id"], date.today() - timedelta(days=10))
        await uow.product_views.record_view(product["id"], date.today())
        await uow.commit()

    response = await client.get(f"/api/storefront/{slug}/products/{product['id']}")
    assert response.status_code == 200, response.text
    # только последние две записи (10 дней назад и сегодня) попадают в окно 90 дней
    assert response.json()["product"]["views_90d"] == 2


async def test_storefront_product_page_v2_tenant_isolation_via_api(client, owner_headers, random_phone):
    """Товар другого магазина по чужому product_id — 404, как и раньше."""
    other_response = await client.post(
        "/api/auth/register",
        json={
            "shop_name": "Другой магазин",
            "owner_name": "Другой владелец",
            "phone": random_phone(),
            "password": "secret123",
        },
    )
    other_headers = {"Authorization": f"Bearer {other_response.json()['access_token']}"}
    await client.patch(
        "/api/auth/shop", headers=other_headers, json={"name": "Другой магазин", "storefront_enabled": True}
    )
    other_product = (
        await client.post(
            "/api/products",
            headers=other_headers,
            json={"name": "Чужой товар", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    other_product = (
        await client.put(
            f"/api/products/{other_product['id']}",
            headers=other_headers,
            json={**other_product, "photo": "https://example.com/test.jpg", "show_on_storefront": True},
        )
    ).json()

    slug = "magazin-berkat"
    await _enable_storefront_with_warehouse(client, owner_headers)

    # чужой product_id под своим slug магазина — 404
    response = await client.get(f"/api/storefront/{slug}/products/{other_product['id']}")
    assert response.status_code == 404, response.text

    response = await client.post(f"/api/storefront/{slug}/products/{other_product['id']}/view")
    assert response.status_code == 404, response.text
