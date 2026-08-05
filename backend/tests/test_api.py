from datetime import date, timedelta
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


async def test_supplier_debt_and_due_debts_via_api(client, owner_headers):
    response = await client.post(
        "/api/counterparties/suppliers",
        headers=owner_headers,
        json={"name": "ООО СтройПоставка"},
    )
    assert response.status_code == 201, response.text
    supplier_id = response.json()["id"]

    today = date.today().isoformat()
    response = await client.post(
        "/api/debts/suppliers",
        headers=owner_headers,
        json={"supplier_id": supplier_id, "amount": "50000", "due_date": today, "note": "цемент"},
    )
    assert response.status_code == 201, response.text
    debt = response.json()
    assert debt["client_id"] is None
    assert debt["supplier_id"] == supplier_id

    response = await client.get(f"/api/debts/supplier/{supplier_id}", headers=owner_headers)
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_balance"] == "50000.00"
    assert len(summary["debts"]) == 1

    response = await client.get("/api/debts/due", headers=owner_headers)
    assert response.status_code == 200
    assert debt["id"] in [d["id"] for d in response.json()]

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    response = await client.get(f"/api/debts/due?on={tomorrow}", headers=owner_headers)
    assert debt["id"] not in [d["id"] for d in response.json()]


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
    summary = response.json()
    assert len(summary["debts"]) == 1
    assert summary["total_balance"] == "750.00"
    assert summary["debts"][0]["balance"] == "750.00"

    response = await client.post(
        f"/api/debts/{summary['debts'][0]['id']}/repayments",
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


async def test_sale_return_via_api(client, owner_headers, random_phone):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Платье летнее", "purchase_price": "1000", "retail_price": "2000"},
    )
    product = response.json()

    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "10"}]},
    )

    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product["id"], "quantity": "3", "price": "2000"}],
        },
    )
    sale = response.json()
    sale_line_id = sale["lines"][0]["id"]

    response = await client.post(
        f"/api/sales/{sale['id']}/returns",
        headers=owner_headers,
        json={"items": [{"sale_line_id": sale_line_id, "quantity": "1"}], "note": "не подошло"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["refund"] == "2000.00"

    # остаток теперь 8 (10 получено - 3 продано + 1 возвращено): продадим весь остаток, чтобы проверить
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            # было 10, продано 3, возвращено 1 → остаток 8
            "items": [{"product_id": product["id"], "quantity": "8", "price": "2000"}],
        },
    )
    assert response.status_code == 201, response.text

    # перевозврат: продано 3, уже возвращён 1 → доступно к возврату 2, просим 3
    response = await client.post(
        f"/api/sales/{sale['id']}/returns",
        headers=owner_headers,
        json={"items": [{"sale_line_id": sale_line_id, "quantity": "3"}]},
    )
    assert response.status_code == 400

    # кладовщику возврат недоступен
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Руслан", "phone": random_phone(), "password": "secret123",
            "role": "storekeeper",
        },
    )
    login = await client.post(
        "/api/auth/login",
        json={"phone": response.json()["phone"], "password": "secret123"},
    )
    storekeeper_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post(
        f"/api/sales/{sale['id']}/returns",
        headers=storekeeper_headers,
        json={"items": [{"sale_line_id": sale_line_id, "quantity": "1"}]},
    )
    assert response.status_code == 403


async def test_sale_receipt_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Мёд горный", "purchase_price": "400", "retail_price": "700"},
    )
    product = response.json()
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "5"}]},
    )

    # продажа без клиента — ссылки на WhatsApp быть не должно
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product["id"], "quantity": "1", "price": "700"}],
        },
    )
    sale_id = response.json()["id"]

    response = await client.get(f"/api/sales/{sale_id}/receipt", headers=owner_headers)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert "Мёд горный" in receipt["text"]
    assert "Итого: 700.00 ₽" in receipt["text"]
    assert receipt["whatsapp_link"] is None

    # продажа клиенту с телефоном — ссылка должна появиться
    response = await client.post(
        "/api/counterparties/clients",
        headers=owner_headers,
        json={"name": "Ахмед", "whatsapp": "+79280001122"},
    )
    client_id = response.json()["id"]
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product["id"], "quantity": "1", "price": "700"}],
            "client_id": client_id,
        },
    )
    sale_id = response.json()["id"]

    response = await client.get(f"/api/sales/{sale_id}/receipt", headers=owner_headers)
    receipt = response.json()
    assert receipt["whatsapp_link"].startswith("https://wa.me/79280001122?text=")
    assert "Клиент: Ахмед" in receipt["text"]


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

    response = await client.get(f"/api/orders/{order_id}", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "issued"


async def test_storekeeper_cannot_view_orders_via_api(client, owner_headers, random_phone):
    storekeeper_phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Иса",
            "phone": storekeeper_phone,
            "password": "secret123",
            "role": "storekeeper",
        },
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        "/api/auth/login", json={"phone": storekeeper_phone, "password": "secret123"}
    )
    storekeeper_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.get("/api/orders", headers=storekeeper_headers)
    assert response.status_code == 403

    response = await client.get("/api/orders/1", headers=storekeeper_headers)
    assert response.status_code == 403


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


async def test_analytics_endpoints_via_api(client, owner_headers, random_phone):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар аналитики", "purchase_price": "100", "retail_price": "200"},
    )
    product_id = response.json()["id"]

    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [{"product_id": product_id, "quantity": "5", "cost": "100"}],
        },
    )
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "2", "price": "200"}],
        },
    )
    assert response.status_code == 201, response.text

    response = await client.get("/api/analytics/dashboard", headers=owner_headers)
    assert response.status_code == 200, response.text
    dashboard = response.json()
    assert dashboard["today"]["sales_count"] == 1
    assert dashboard["today"]["revenue"] == "400.00"
    assert dashboard["today"]["profit"] == "200.00"

    response = await client.get("/api/analytics/top-products", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()[0]["product_name"] == "Товар аналитики"

    response = await client.get("/api/analytics/stock-value", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["total_value"] == "300.00"  # 3 осталось * 100

    response = await client.get("/api/analytics/dead-stock?stale_days=0", headers=owner_headers)
    assert response.status_code == 200
    assert response.json() == []  # только что продавался

    seller_phone = random_phone()
    await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={"name": "Продавец", "phone": seller_phone, "password": "secret123", "role": "seller"},
    )
    login = await client.post(
        "/api/auth/login", json={"phone": seller_phone, "password": "secret123"}
    )
    seller_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get("/api/analytics/dashboard", headers=seller_headers)
    assert response.status_code == 403
