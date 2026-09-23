from datetime import date, timedelta
from decimal import Decimal


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

    response = await client.get("/api/products/barcode/4600000000017", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["id"] == product["id"]

    response = await client.get("/api/products/barcode/0000000000000", headers=owner_headers)
    assert response.status_code == 200
    assert response.json() is None

    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Другой товар с тем же ШК",
            "unit_code": "pcs",
            "purchase_price": "10",
            "retail_price": "20",
            "barcode": "4600000000017",
        },
    )
    assert response.status_code == 400

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
            "debt_due_date": str(date.today() + timedelta(days=7)),
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
    assert "Итого: 700 ₽" in receipt["text"]
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

    # квитанция PDF-документом — та же продажа
    response = await client.get(f"/api/sales/{sale_id}/receipt.pdf", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:5] == b"%PDF-"


async def test_inventory_receive_updates_purchase_price_via_api(client, owner_headers):
    # закупочная цена товара = цена последней приёмки — иначе маржа в
    # аналитике продолжает считаться по устаревшей цене
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар с меняющейся ценой", "purchase_price": "100", "retail_price": "200"},
    )
    product_id = response.json()["id"]

    # приёмка без cost — цену не трогаем
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "5"}]},
    )
    response = await client.get(f"/api/products/{product_id}", headers=owner_headers)
    assert response.json()["purchase_price"] == "100.00"

    # приёмка с новой ценой — обновляет закупочную цену товара
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "5", "cost": "130"}]},
    )
    response = await client.get(f"/api/products/{product_id}", headers=owner_headers)
    assert response.json()["purchase_price"] == "130.00"

    # несколько строк одного товара в одной приёмке — побеждает последняя по порядку
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [
                {"product_id": product_id, "quantity": "1", "cost": "140"},
                {"product_id": product_id, "quantity": "1", "cost": "150"},
            ],
        },
    )
    response = await client.get(f"/api/products/{product_id}", headers=owner_headers)
    assert response.json()["purchase_price"] == "150.00"


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

    response = await client.get("/api/inventory/stock", headers=owner_headers)
    assert response.status_code == 200
    stock = [i for i in response.json() if i["product_id"] == product_id]
    assert len(stock) == 1
    assert stock[0]["quantity"] == "40.000"


async def test_warehouses_via_api(client, owner_headers):
    response = await client.get("/api/inventory/warehouses", headers=owner_headers)
    assert response.status_code == 200
    warehouses = response.json()
    assert len(warehouses) == 1  # основной склад создан при регистрации
    assert warehouses[0]["name"] == "Основной склад"

    response = await client.post(
        "/api/inventory/warehouses",
        headers=owner_headers,
        json={"name": "Склад на Кадырова", "address": "ул. Кадырова, 12"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["name"] == "Склад на Кадырова"

    response = await client.get("/api/inventory/warehouses", headers=owner_headers)
    assert len(response.json()) == 2


async def test_update_warehouse_details_via_api(client, owner_headers):
    warehouses = (
        await client.get("/api/inventory/warehouses", headers=owner_headers)
    ).json()
    warehouse_id = warehouses[0]["id"]

    response = await client.put(
        f"/api/inventory/warehouses/{warehouse_id}",
        headers=owner_headers,
        json={"name": "Склад на Кадырова", "address": "ул. Кадырова, 12"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Склад на Кадырова"
    assert body["address"] == "ул. Кадырова, 12"

    response = await client.get("/api/inventory/warehouses", headers=owner_headers)
    updated = next(w for w in response.json() if w["id"] == warehouse_id)
    assert updated["name"] == "Склад на Кадырова"
    assert updated["address"] == "ул. Кадырова, 12"
