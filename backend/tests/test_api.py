from decimal import Decimal
from io import BytesIO

import openpyxl


async def test_register_login_flow(client, random_phone):
    phone = random_phone()
    response = await client.post(
        "/api/auth/register",
        json={
            "shop_name": "Лавка",
            "owner_name": "Муса",
            "phone": phone,
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "owner"
    assert response.json()["shop_slug"] == "lavka"

    response = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "secret123"}
    )
    assert response.status_code == 200
    assert response.json()["shop_slug"] is None  # слаг возвращается только при регистрации

    response = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "wrong"}
    )
    assert response.status_code == 403

    response = await client.get("/api/products")
    assert response.status_code == 401  # без токена


async def test_validation_error_returns_422(client, random_phone):
    response = await client.post(
        "/api/auth/register",
        json={
            "shop_name": "Лавка",
            "owner_name": "Муса",
            "phone": random_phone(),
            "password": "123",  # короче 6 символов
        },
    )
    assert response.status_code == 422


async def test_not_found_returns_404(client, owner_headers):
    response = await client.get("/api/products/999999", headers=owner_headers)
    assert response.status_code == 404


async def test_full_trading_flow(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Духи масляные 6мл",
            "unit_code": "pcs",
            "purchase_price": "150",
            "retail_price": "250",
            "barcode": "4600000000017",
        },
    )
    assert response.status_code == 201, response.text
    product = response.json()
    assert product["purchase_price"] == "150.00"  # владелец видит закупочную

    # склад создан при регистрации — id всегда 1 на чистой схеме теста
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [{"product_id": product["id"], "quantity": "10", "cost": "150"}],
        },
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product["id"], "quantity": "2", "price": "250"}],
            "cash_received": "1000",
        },
    )
    assert response.status_code == 201, response.text
    sale = response.json()
    assert sale["total"] == "500.00"
    assert sale["change"] == "500.00"

    response = await client.post(
        "/api/counterparties/clients",
        headers=owner_headers,
        json={"name": "Ахмед", "debt_limit": "1000"},
    )
    assert response.status_code == 201
    client_id = response.json()["id"]

    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "credit",
            "items": [{"product_id": product["id"], "quantity": "3", "price": "250"}],
            "client_id": client_id,
        },
    )
    assert response.status_code == 201

    response = await client.get(f"/api/debts/client/{client_id}", headers=owner_headers)
    debts = response.json()
    assert len(debts) == 1
    assert debts[0]["balance"] == "750.00"

    response = await client.post(
        f"/api/debts/{debts[0]['id']}/repayments",
        headers=owner_headers,
        json={"amount": "250"},
    )
    assert response.status_code == 200
    assert response.json()["balance"] == "500.00"

    # нехватка остатка: осталось 5, просим 100 → 400 с именем товара
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product["id"], "quantity": "100", "price": "250"}],
        },
    )
    assert response.status_code == 400
    assert "Духи" in response.json()["detail"]


async def test_inventory_write_off_and_stocktake_endpoints(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Орехи грецкие",
            "unit_code": "kg",
            "purchase_price": "600",
            "retail_price": "900",
        },
    )
    product_id = response.json()["id"]

    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "50"}]},
    )

    response = await client.post(
        "/api/inventory/write-off",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [{"product_id": product_id, "quantity": "5"}],
            "note": "усушка",
        },
    )
    assert response.status_code == 201
    assert response.json()["type"] == "write_off"

    response = await client.post(
        "/api/inventory/stocktake",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "40"}]},
    )
    assert response.status_code == 201
    discrepancies = response.json()["discrepancies"]
    assert len(discrepancies) == 1
    assert Decimal(discrepancies[0]["delta"]) == Decimal("-5")  # получено 50 - списано 5 = 45, факт 40


async def test_order_full_lifecycle_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Торт на заказ", "purchase_price": "1500", "retail_price": "3000"},
    )
    product_id = response.json()["id"]

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Милана"}
    )
    client_id = response.json()["id"]

    response = await client.post(
        "/api/orders",
        headers=owner_headers,
        json={
            "client_id": client_id,
            "items": [{"product_id": product_id, "quantity": "1", "price": "3000"}],
            "prepayment": "1000",
            "note": "надпись «С юбилеем»",
        },
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["to_pay"] == "2000.00"
    order_id = order["id"]

    response = await client.patch(
        f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": "in_progress"}
    )
    assert response.status_code == 200

    # нельзя перескочить сразу в "выдан" из "в работе"
    response = await client.patch(
        f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": "issued"}
    )
    assert response.status_code == 400

    response = await client.patch(
        f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": "ready"}
    )
    assert response.status_code == 200

    response = await client.patch(
        f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": "issued"}
    )
    assert response.status_code == 200

    response = await client.get("/api/orders", headers=owner_headers)
    assert response.json() == []  # выданные заказы не входят в список активных


async def test_audit_log_records_actions_and_guards_access(client, owner_headers, random_phone):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Мёд горный",
            "unit_code": "kg",
            "purchase_price": "400",
            "retail_price": "700",
        },
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "10"}]},
    )
    await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "1.5", "price": "700"}],
        },
    )

    response = await client.get("/api/audit", headers=owner_headers)
    assert response.status_code == 200
    actions = [entry["action"] for entry in response.json()]
    # журнал в обратном хронологическом порядке
    assert actions == ["sale.create", "stock.receive", "product.create", "shop.register"]
    sale_entry = response.json()[0]
    assert sale_entry["details"]["total"] == "1050.00"

    # продавцу журнал недоступен
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
    response = await client.get("/api/audit", headers=seller_headers)
    assert response.status_code == 403


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

    response = await client.post(
        f"/api/products/{product_id}/photo",
        headers=owner_headers,
        files={"file": ("photo.jpg", b"\xff\xd8\xff-fake-jpeg-bytes", "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    photo_url = response.json()["photo"]
    assert photo_url.startswith("/uploads/") and photo_url.endswith(".jpg")
    saved = list(tmp_path.iterdir())
    assert len(saved) == 1 and saved[0].read_bytes() == b"\xff\xd8\xff-fake-jpeg-bytes"

    response = await client.post(
        f"/api/products/{product_id}/photo",
        headers=owner_headers,
        files={"file": ("virus.exe", b"not-an-image", "application/octet-stream")},
    )
    assert response.status_code == 400  # недопустимое расширение

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
        files={"file": ("photo.jpg", b"\xff\xd8\xff-fake-jpeg-bytes", "image/jpeg")},
    )
    assert response.status_code == 403


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
