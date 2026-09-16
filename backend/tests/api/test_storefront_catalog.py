async def test_storefront_catalog_via_api(client, owner_headers):
    slug = "magazin-berkat"  # slugify("Магазин Беркат") — детерминирован, см. owner_headers

    # магазин только что зарегистрирован — витрина выключена по умолчанию
    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 404, response.text

    hidden = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Скрытый товар", "purchase_price": "50", "retail_price": "100"},
        )
    ).json()
    visible = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Видимый товар",
                "purchase_price": "50",
                "retail_price": "150",
                "show_on_storefront": True,
            },
        )
    ).json()
    assert visible["show_on_storefront"] is True
    assert hidden["show_on_storefront"] is False  # дефолт — скрыт, пока владелец явно не включит

    # витрина ещё выключена целиком — даже видимый товар недоступен публично
    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 404, response.text

    response = await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    assert response.status_code == 200, response.text
    assert response.json()["storefront_enabled"] is True

    # склад тоже должен быть явно показан на витрине — иначе наличие не считается
    await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )

    # без авторизации — публичный доступ
    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [p["id"] for p in body["products"]]
    assert visible["id"] in ids
    assert hidden["id"] not in ids  # флаг товара скрывает его даже при включённой витрине

    product = body["products"][0]
    assert "purchase_price" not in product  # закупочная цена никогда не отдаётся публично
    assert "margin" not in product
    assert set(product.keys()) == {
        "id", "name", "retail_price", "photo", "category_id", "in_stock",
        "min_order_qty", "order_step_qty", "sold_count",
        "average_rating", "reviews_count",
    }

    response = await client.get(f"/api/storefront/{slug}", params={"query": "Скрытый"})
    assert response.status_code == 200, response.text
    assert response.json()["products"] == []  # запрос не обходит show_on_storefront

    response = await client.get("/api/storefront/no-such-shop")
    assert response.status_code == 404, response.text


async def test_storefront_catalog_filtered_by_warehouse_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    second_warehouse = (
        await client.post("/api/inventory/warehouses", headers=owner_headers, json={"name": "Филиал"})
    ).json()
    await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )
    await client.put(
        f"/api/inventory/warehouses/{second_warehouse['id']}",
        headers=owner_headers,
        json={"name": "Филиал", "show_on_storefront": True},
    )

    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Товар только на складе 1",
                "purchase_price": "50",
                "retail_price": "100",
                "show_on_storefront": True,
            },
        )
    ).json()
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "5", "cost": "50"}]},
    )
    assert response.status_code == 201, response.text

    # без warehouse_id — «в наличии» суммарно по всем складам
    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 200, response.text
    assert next(p for p in response.json()["products"] if p["id"] == product["id"])["in_stock"] is True

    # склад 1 — товар есть
    response = await client.get(f"/api/storefront/{slug}", params={"warehouse_id": 1})
    assert response.status_code == 200, response.text
    assert next(p for p in response.json()["products"] if p["id"] == product["id"])["in_stock"] is True

    # склад «Филиал» — товар виден (флаг товара это не меняет), но остатка там нет
    response = await client.get(f"/api/storefront/{slug}", params={"warehouse_id": second_warehouse["id"]})
    assert response.status_code == 200, response.text
    listed = next(p for p in response.json()["products"] if p["id"] == product["id"])
    assert listed["in_stock"] is False

    # несуществующий склад — фильтр тихо игнорируется, не 404/400
    response = await client.get(f"/api/storefront/{slug}", params={"warehouse_id": 999999})
    assert response.status_code == 200, response.text
    assert next(p for p in response.json()["products"] if p["id"] == product["id"])["in_stock"] is True


async def test_storefront_warehouse_hidden_from_catalog_via_api(client, owner_headers):
    """Склад скрыт от витрины отдельно от товара (show_on_storefront владельца) —
    товар, есть только на скрытом складе, не должен считаться «в наличии» публично,
    и сам склад не должен попадать в список для выбора."""
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    # склад 1 остаётся скрытым от витрины (дефолт show_on_storefront=False)
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Товар со скрытого склада",
                "purchase_price": "50",
                "retail_price": "100",
                "show_on_storefront": True,
            },
        )
    ).json()
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "5", "cost": "50"}]},
    )
    assert response.status_code == 201, response.text

    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["warehouses"] == []  # ни один склад не показан на витрине
    listed = next(p for p in body["products"] if p["id"] == product["id"])
    assert listed["in_stock"] is False  # остаток на скрытом складе не считается наличием

    # владелец включает витрину именно для этого склада
    response = await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["show_on_storefront"] is True

    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [w["id"] for w in body["warehouses"]] == [1]
    listed = next(p for p in body["products"] if p["id"] == product["id"])
    assert listed["in_stock"] is True


async def test_storefront_product_page_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    visible = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Платье летнее",
                "sku": "DR-001",
                "purchase_price": "300",
                "retail_price": "600",
                "show_on_storefront": True,
                "variants": [{"size": "M", "color": "Красный"}],
            },
        )
    ).json()
    hidden = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Скрытый товар", "purchase_price": "50", "retail_price": "100"},
        )
    ).json()

    response = await client.get(f"/api/storefront/{slug}/products/{visible['id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["product"]["id"] == visible["id"]
    assert body["product"]["sku"] == "DR-001"
    assert body["product"]["variants"][0]["size"] == "M"
    assert "purchase_price" not in body["product"]  # закупочная цена не отдаётся

    # скрытый товар — 404, даже если знаешь его id
    response = await client.get(f"/api/storefront/{slug}/products/{hidden['id']}")
    assert response.status_code == 404, response.text

    # несуществующий товар — тоже 404
    response = await client.get(f"/api/storefront/{slug}/products/999999")
    assert response.status_code == 404, response.text

    # витрина выключена — 404 даже на существующий видимый товар
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": False}
    )
    response = await client.get(f"/api/storefront/{slug}/products/{visible['id']}")
    assert response.status_code == 404, response.text


async def test_storefront_og_html_for_bots(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Платье OG",
                "purchase_price": "300",
                "retail_price": "600",
                "show_on_storefront": True,
                "description": "Лёгкое летнее платье",
            },
        )
    ).json()

    catalog_og = await client.get(f"/api/storefront/{slug}/og")
    assert catalog_og.status_code == 200, catalog_og.text
    assert "text/html" in catalog_og.headers["content-type"]
    assert 'property="og:title"' in catalog_og.text
    assert "Магазин Беркат" in catalog_og.text

    product_og = await client.get(f"/api/storefront/{slug}/products/{product['id']}/og")
    assert product_og.status_code == 200, product_og.text
    assert "Платье OG" in product_og.text
    assert "Лёгкое летнее платье" in product_og.text
    assert 'property="og:url"' in product_og.text


async def test_storefront_catalog_sort_and_category_counts_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    category = (
        await client.post("/api/products/categories", headers=owner_headers, json={"name": "Одежда"})
    ).json()

    cheap = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Дешёвый",
                "purchase_price": "10",
                "retail_price": "50",
                "show_on_storefront": True,
                "category_id": category["id"],
            },
        )
    ).json()
    pricey = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Дорогой",
                "purchase_price": "100",
                "retail_price": "500",
                "show_on_storefront": True,
                "category_id": category["id"],
            },
        )
    ).json()
    # товар без show_on_storefront не должен попадать в счётчик категории
    await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Скрытый в той же категории",
            "purchase_price": "1",
            "retail_price": "2",
            "category_id": category["id"],
        },
    )

    response = await client.get(f"/api/storefront/{slug}", params={"sort": "price_asc"})
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [p["id"] for p in body["products"] if p["id"] in (cheap["id"], pricey["id"])]
    assert ids == [cheap["id"], pricey["id"]]

    response = await client.get(f"/api/storefront/{slug}", params={"sort": "price_desc"})
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["products"] if p["id"] in (cheap["id"], pricey["id"])]
    assert ids == [pricey["id"], cheap["id"]]

    cat_response = next(c for c in body["categories"] if c["id"] == category["id"])
    assert cat_response["product_count"] == 2  # скрытый товар не учтён

    response = await client.get(f"/api/storefront/{slug}", params={"sort": "not_a_real_sort"})
    assert response.status_code == 400, response.text


async def test_storefront_catalog_price_and_in_stock_filters_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    await client.put(
        "/api/inventory/warehouses/1",
        headers=owner_headers,
        json={"name": "Основной склад", "show_on_storefront": True},
    )
    cheap = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Дешёвый", "purchase_price": "10", "retail_price": "50", "show_on_storefront": True},
        )
    ).json()
    expensive_out_of_stock = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Дорогой без остатка", "purchase_price": "100", "retail_price": "500", "show_on_storefront": True},
        )
    ).json()
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": cheap["id"], "quantity": "10", "cost": "10"}]},
    )

    # диапазон цены — только дешёвый попадает
    response = await client.get(f"/api/storefront/{slug}", params={"max_price": "100"})
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["products"]]
    assert cheap["id"] in ids
    assert expensive_out_of_stock["id"] not in ids

    # только в наличии — дорогой без остатка отсекается
    response = await client.get(f"/api/storefront/{slug}", params={"in_stock_only": "true"})
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["products"]]
    assert cheap["id"] in ids
    assert expensive_out_of_stock["id"] not in ids


async def test_storefront_catalog_variant_filter_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    dress_red_m = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Платье",
                "purchase_price": "500",
                "retail_price": "1500",
                "show_on_storefront": True,
                "variants": [{"size": "M", "color": "Красный"}],
            },
        )
    ).json()
    shoes_blue = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Кроссовки",
                "purchase_price": "800",
                "retail_price": "2500",
                "show_on_storefront": True,
                "variants": [{"size": "42", "color": "Синий"}],
            },
        )
    ).json()

    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body["available_sizes"]) == {"M", "42"}
    assert set(body["available_colors"]) == {"Красный", "Синий"}

    response = await client.get(f"/api/storefront/{slug}", params={"variant_size": "M"})
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["products"]]
    assert dress_red_m["id"] in ids
    assert shoes_blue["id"] not in ids

    response = await client.get(f"/api/storefront/{slug}", params={"variant_color": "Синий"})
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()["products"]]
    assert shoes_blue["id"] in ids
    assert dress_red_m["id"] not in ids
