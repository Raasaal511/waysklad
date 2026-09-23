from io import BytesIO

import openpyxl
from PIL import Image


def _excel_file(rows: list[tuple]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(
        ["Название", "Артикул", "Штрихкод", "Ед. изм.", "Закупочная цена", "Розничная цена", "Мин. остаток"]
    )
    for row in rows:
        sheet.append(list(row))
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _test_photo_bytes(size: tuple[int, int] = (2000, 1500)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(90, 140, 200)).save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


async def test_import_products_from_excel_via_api(client, owner_headers, random_phone):
    file_bytes = _excel_file(
        [
            ("Мёд горный", "", "", "kg", 400, 700, 0),
            ("Без цены", "", "", "pcs", "не число", 700, 0),
        ]
    )
    response = await client.post(
        "/api/products/import",
        headers=owner_headers,
        files={
            "file": (
                "products.xlsx",
                file_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1 and body["errors"][0]["row"] == 3

    response = await client.get("/api/products", headers=owner_headers)
    assert [p["name"] for p in response.json()] == ["Мёд горный"]

    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={"name": "Зара", "phone": random_phone(), "password": "secret123", "role": "seller"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"phone": response.json()["phone"], "password": "secret123"},
    )
    seller_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post(
        "/api/products/import",
        headers=seller_headers,
        files={
            "file": (
                "products.xlsx",
                _excel_file([("Товар", "", "", "pcs", 1, 2, 0)]),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 403


async def test_product_photo_upload_via_api(client, owner_headers, random_phone, tmp_path):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Платье летнее", "purchase_price": "1000", "retail_price": "2000"},
    )
    product_id = response.json()["id"]

    original = _test_photo_bytes()
    response = await client.post(
        f"/api/products/{product_id}/photo",
        headers=owner_headers,
        files={"file": ("photo.jpg", original, "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    body = response.json()

    # оригинал переупаковывается в WebP, а не сохраняется как есть
    assert body["photo"].startswith("/uploads/") and body["photo"].endswith(".webp")

    full_path = tmp_path / body["photo"].removeprefix("/uploads/")
    assert full_path.exists()

    with Image.open(full_path) as full_image:
        assert max(full_image.size) <= 1200

    # реальное фото с телефона весит существенно больше, чем пережатый WebP
    assert full_path.stat().st_size < len(original)

    response = await client.post(
        f"/api/products/{product_id}/photo",
        headers=owner_headers,
        files={"file": ("virus.exe", b"not-an-image", "application/octet-stream")},
    )
    assert response.status_code == 400  # недопустимое расширение

    response = await client.post(
        f"/api/products/{product_id}/photo",
        headers=owner_headers,
        files={"file": ("not-an-image.jpg", b"totally not a jpeg", "image/jpeg")},
    )
    assert response.status_code == 400  # расширение верное, но не изображение

    response = await client.post(
        f"/api/products/{product_id}/photo",
        headers=owner_headers,
        files={"file": ("big.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")},
    )
    assert response.status_code == 400  # превышен лимит 5 МБ

    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={"name": "Зара", "phone": random_phone(), "password": "secret123", "role": "seller"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"phone": response.json()["phone"], "password": "secret123"},
    )
    seller_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post(
        f"/api/products/{product_id}/photo",
        headers=seller_headers,
        files={"file": ("photo.jpg", original, "image/jpeg")},
    )
    assert response.status_code == 403


async def test_variant_price_and_photo_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Носки",
            "purchase_price": "50",
            "retail_price": "100",
            "variants": [{"size": "M", "price": "90"}, {"size": "L"}],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    by_size = {v["size"]: v for v in body["variants"]}
    assert by_size["M"]["price"] == "90.00"
    assert by_size["L"]["price"] is None
    product_id = body["id"]
    variant_id = by_size["M"]["id"]

    response = await client.post(
        f"/api/products/{product_id}/variants/{variant_id}/photo",
        headers=owner_headers,
        files={"file": ("photo.jpg", _test_photo_bytes(), "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    variant = next(v for v in body["variants"] if v["id"] == variant_id)
    assert variant["photo"].startswith("/uploads/") and variant["photo"].endswith(".webp")
    # фото другого варианта того же товара не затронуто
    other = next(v for v in body["variants"] if v["id"] != variant_id)
    assert other["photo"] == ""

    response = await client.post(
        f"/api/products/{product_id}/variants/999999/photo",
        headers=owner_headers,
        files={"file": ("photo.jpg", _test_photo_bytes(), "image/jpeg")},
    )
    assert response.status_code == 400  # несуществующий вариант


async def test_variant_name_and_warranty_text_via_api(client, owner_headers):
    """Промпт B1 п.1, п.4 — название варианта и гарантия принимаются/отдаются
    в API владельца точно так же, как остальные поля товара/варианта."""
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Наушники",
            "purchase_price": "1000",
            "retail_price": "2000",
            "warranty_text": "Гарантия 12 месяцев от производителя",
            "variants": [{"size": "", "color": "Чёрный", "name": "Aurum"}],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["warranty_text"] == "Гарантия 12 месяцев от производителя"
    assert body["variants"][0]["name"] == "Aurum"
    product_id = body["id"]
    variant_id = body["variants"][0]["id"]

    response = await client.put(
        f"/api/products/{product_id}",
        headers=owner_headers,
        json={
            "name": "Наушники",
            "purchase_price": "1000",
            "retail_price": "2000",
            "warranty_text": "Гарантия 24 месяца",
            "variants": [{"id": variant_id, "size": "", "color": "Чёрный", "name": "Aurum Pro"}],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["warranty_text"] == "Гарантия 24 месяца"
    assert body["variants"][0]["name"] == "Aurum Pro"

    # дефолт — пустая строка, как у description
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Без гарантии", "purchase_price": "10", "retail_price": "20"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["warranty_text"] == ""


async def test_custom_unit_via_api(client, owner_headers):
    response = await client.post(
        "/api/products/units",
        headers=owner_headers,
        json={"code": "box", "name": "коробка"},
    )
    assert response.status_code == 201, response.text
    assert response.json() == {"code": "box", "name": "коробка", "fractional": False}

    response = await client.get("/api/products/units", headers=owner_headers)
    codes = [u["code"] for u in response.json()]
    assert "box" in codes and "pcs" in codes  # свои единицы соседствуют с предустановленными

    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Плитка облицовочная",
            "unit_code": "box",
            "purchase_price": "500",
            "retail_price": "800",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["unit_code"] == "box"

    response = await client.post(
        "/api/products/units",
        headers=owner_headers,
        json={"code": "box", "name": "ещё коробка"},
    )
    assert response.status_code == 400  # код единицы уже занят


async def test_seller_permissions_via_api(client, owner_headers, random_phone):
    seller_phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Зара",
            "phone": seller_phone,
            "password": "secret123",
            "role": "seller",
        },
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        "/api/auth/login", json={"phone": seller_phone, "password": "secret123"}
    )
    seller_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.post(
        "/api/products",
        headers=seller_headers,
        json={"name": "Товар", "purchase_price": "1", "retail_price": "2"},
    )
    assert response.status_code == 403

    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Платье", "purchase_price": "1000", "retail_price": "2000"},
    )
    assert response.status_code == 201

    response = await client.get("/api/products", headers=seller_headers)
    products = response.json()
    assert products[0]["purchase_price"] is None
    assert products[0]["margin"] is None
    assert products[0]["retail_price"] == "2000.00"


async def test_product_history_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Свеча ароматическая", "purchase_price": "100", "retail_price": "200"},
    )
    assert response.status_code == 201, response.text
    product = response.json()

    response = await client.put(
        f"/api/products/{product['id']}",
        headers=owner_headers,
        json={"name": "Свеча ароматическая (лаванда)", "purchase_price": "100", "retail_price": "220"},
    )
    assert response.status_code == 200, response.text

    response = await client.get(f"/api/products/{product['id']}/history", headers=owner_headers)
    assert response.status_code == 200, response.text
    actions = [e["action"] for e in response.json()]
    assert actions == ["product.update", "product.create"]


async def test_import_products_from_csv_via_api(client, owner_headers):
    csv_text = (
        "Название,Артикул,Штрихкод,Ед. изм.,Закупочная цена,Розничная цена,Мин. остаток\n"
        "Соль морская,,,kg,50,90,0\n"
        "Без цены,,,pcs,не число,90,0\n"
    )
    response = await client.post(
        "/api/products/import",
        headers=owner_headers,
        files={"file": ("products.csv", csv_text.encode("utf-8-sig"), "text/csv")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1 and body["errors"][0]["row"] == 3

    response = await client.get("/api/products", headers=owner_headers)
    assert "Соль морская" in [p["name"] for p in response.json()]


async def test_export_products_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Йогурт питьевой", "purchase_price": "60", "retail_price": "100"},
    )
    assert response.status_code == 201, response.text

    response = await client.get("/api/products/export.xlsx", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(response.content) > 0

    response = await client.get("/api/products/export.csv", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "Йогурт питьевой" in response.content.decode("utf-8-sig")

    response = await client.get("/api/products/export.pdf", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


async def test_products_pagination_via_api(client, owner_headers):
    for i in range(55):
        response = await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": f"Пагинация {i:03d}", "purchase_price": "10", "retail_price": "20"},
        )
        assert response.status_code == 201, response.text

    # без limit/offset — дефолтная страница из 50, но X-Total-Count честно больше
    response = await client.get("/api/products", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert len(response.json()) == 50
    assert int(response.headers["x-total-count"]) >= 55

    # вторая страница — оставшиеся товары
    response = await client.get(
        "/api/products", headers=owner_headers, params={"limit": 50, "offset": 50}
    )
    assert response.status_code == 200, response.text
    assert len(response.json()) >= 5

    # экспорт не должен быть обрезан лимитом страницы
    response = await client.get("/api/products/export.csv", headers=owner_headers)
    assert response.status_code == 200, response.text
    rows = response.content.decode("utf-8-sig").strip().splitlines()
    assert len(rows) - 1 >= 55  # минус строка заголовка


async def test_products_generic_filter_via_api(client, owner_headers):
    cheap = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Дешёвый товар", "sku": "SKU-CHEAP", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    pricey = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Дорогой товар", "sku": "SKU-PRICEY", "purchase_price": "500", "retail_price": "900"},
        )
    ).json()

    # поиск по sku — попадает в объединённое search_text (name/sku/barcode)
    response = await client.get("/api/products", headers=owner_headers, params={"query": "SKU-PRICEY"})
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()]
    assert ids == [pricey["id"]]

    # сортировка по возрастанию розничной цены
    response = await client.get(
        "/api/products", headers=owner_headers, params={"sort": "price_asc", "limit": 50}
    )
    assert response.status_code == 200, response.text
    products = response.json()
    prices = [float(p["retail_price"]) for p in products if p["id"] in (cheap["id"], pricey["id"])]
    assert prices == sorted(prices)
    assert products[0]["id"] == cheap["id"]

    # сортировка по убыванию маржи (retail - purchase) — дорогой товар с большей маржой первым
    response = await client.get(
        "/api/products", headers=owner_headers, params={"sort": "margin_desc", "limit": 50}
    )
    assert response.status_code == 200, response.text
    products = response.json()
    assert products[0]["id"] == pricey["id"]

    # остаток: только у "дешёвого" делаем приёмку — in_stock_only отсекает "дорогой"
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [{"product_id": cheap["id"], "quantity": "5", "cost": "10"}],
        },
    )
    assert response.status_code == 201, response.text

    response = await client.get(
        "/api/products", headers=owner_headers, params={"in_stock_only": "true", "limit": 50}
    )
    assert response.status_code == 200, response.text
    ids = [p["id"] for p in response.json()]
    assert cheap["id"] in ids
    assert pricey["id"] not in ids

    # сортировка по остатку на конкретном складе (id=1 — создан при регистрации)
    response = await client.get(
        "/api/products",
        headers=owner_headers,
        params={"sort": "stock_desc", "warehouse_id": 1, "limit": 50},
    )
    assert response.status_code == 200, response.text
    products = response.json()
    assert products[0]["id"] == cheap["id"]

    # неизвестное поле сортировки — понятная ошибка, не 500
    response = await client.get("/api/products", headers=owner_headers, params={"sort": "not_a_field"})
    assert response.status_code == 400, response.text


async def test_products_search_by_barcode_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Шоколад молочный",
            "purchase_price": "80",
            "retail_price": "150",
            "barcode": "4600000000123",
        },
    )
    assert response.status_code == 201, response.text

    response = await client.get(
        "/api/products", headers=owner_headers, params={"query": "4600000000123"}
    )
    assert response.status_code == 200, response.text
    assert [p["name"] for p in response.json()] == ["Шоколад молочный"]


async def test_products_category_and_sort_via_api(client, owner_headers):
    category = await client.post(
        "/api/products/categories", headers=owner_headers, json={"name": "Напитки"}
    )
    category_id = category.json()["id"]

    await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Сок яблочный", "purchase_price": "50", "retail_price": "100",
            "category_id": category_id,
        },
    )
    await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Сок вишнёвый", "purchase_price": "60", "retail_price": "90",
            "category_id": category_id,
        },
    )
    await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Гвозди", "purchase_price": "5", "retail_price": "10"},
    )

    response = await client.get(
        "/api/products", headers=owner_headers, params={"category_id": category_id}
    )
    assert response.status_code == 200, response.text
    names = [p["name"] for p in response.json()]
    assert set(names) == {"Сок яблочный", "Сок вишнёвый"}

    response = await client.get(
        "/api/products",
        headers=owner_headers,
        params={"category_id": category_id, "sort": "price_asc"},
    )
    assert [p["name"] for p in response.json()] == ["Сок вишнёвый", "Сок яблочный"]

    response = await client.get(
        "/api/products",
        headers=owner_headers,
        params={"category_id": category_id, "sort": "price_desc"},
    )
    assert [p["name"] for p in response.json()] == ["Сок яблочный", "Сок вишнёвый"]

    response = await client.get(
        "/api/products",
        headers=owner_headers,
        params={"category_id": category_id, "sort": "created_desc"},
    )
    assert [p["name"] for p in response.json()] == ["Сок вишнёвый", "Сок яблочный"]

    response = await client.get(
        "/api/products",
        headers=owner_headers,
        params={"category_id": category_id, "sort": "created_asc"},
    )
    assert [p["name"] for p in response.json()] == ["Сок яблочный", "Сок вишнёвый"]


async def test_search_by_digits_part_of_sku(client, owner_headers):
    """Артикул генерируется как «СКО-1928463750124» (префикс из названия +
    13 цифр), и владелец часто помнит/диктует только цифровую часть —
    поиск по ней одной должен находить товар."""
    created = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Смарт-часы Watch Ultra",
                "sku": "СМА-1928463750124",
                "purchase_price": "100",
                "retail_price": "200",
            },
        )
    ).json()
    await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Кофта оверсайз",
            "sku": "КОФ-9051432687193",
            "purchase_price": "100",
            "retail_price": "200",
        },
    )

    # только цифры, без буквенного префикса
    response = await client.get(
        "/api/products", headers=owner_headers, params={"query": "1928463750124"}
    )
    assert response.status_code == 200, response.text
    assert [p["id"] for p in response.json()] == [created["id"]]

    # часть цифр в середине артикула — ILIKE ищет подстроку
    response = await client.get(
        "/api/products", headers=owner_headers, params={"query": "846375"}
    )
    assert [p["id"] for p in response.json()] == [created["id"]]
