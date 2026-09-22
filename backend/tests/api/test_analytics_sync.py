from datetime import date, timedelta


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

    response = await client.get("/api/analytics/timeline", headers=owner_headers)
    assert response.status_code == 200, response.text
    timeline = response.json()
    assert len(timeline) == 1
    assert timeline[0]["revenue"] == "400.00"
    assert timeline[0]["profit"] == "200.00"
    assert timeline[0]["sales_count"] == 1

    response = await client.get(
        "/api/analytics/timeline", headers=owner_headers, params={"bucket": "bogus"}
    )
    assert response.status_code == 422

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


async def test_restock_recommendations_via_api(client, owner_headers):
    # раскупаемый товар: остаток 2 <= min_stock 5, продавался — должен попасть в рекомендации
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Ходовой товар", "purchase_price": "100", "retail_price": "200",
            "min_stock": "5",
        },
    )
    hot_product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [{"product_id": hot_product_id, "quantity": "5", "cost": "100"}],
        },
    )
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": hot_product_id, "quantity": "3", "price": "200"}],
        },
    )
    assert response.status_code == 201, response.text

    # тоже мало на остатке, но никогда не продавался — не должен попасть в рекомендации
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={
            "name": "Незнакомец", "purchase_price": "50", "retail_price": "100",
            "min_stock": "5",
        },
    )
    cold_product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [{"product_id": cold_product_id, "quantity": "1", "cost": "50"}],
        },
    )

    response = await client.get("/api/inventory/restock-recommendations", headers=owner_headers)
    assert response.status_code == 200, response.text
    names = [item["product_name"] for item in response.json()]
    assert "Ходовой товар" in names
    assert "Незнакомец" not in names


async def test_sync_sales_offline_queue_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар офлайн", "purchase_price": "50", "retail_price": "100"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "10"}]},
    )

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Клиент офлайн"}
    )
    client_id = response.json()["id"]

    batch = {
        "sales": [
            {
                "client_op_id": "device-a-1",
                "warehouse_id": 1,
                "payment_method": "cash",
                "items": [{"product_id": product_id, "quantity": "2", "price": "100"}],
            },
            {
                "client_op_id": "device-a-2",
                "warehouse_id": 1,
                "payment_method": "cash",
                "items": [{"product_id": product_id, "quantity": "100", "price": "100"}],
            },
            {
                # продажа в долг — самый частый способ оплаты в регионе; должна
                # применяться из офлайн-очереди наравне с обычной продажей
                "client_op_id": "device-a-3",
                "warehouse_id": 1,
                "payment_method": "credit",
                "items": [{"product_id": product_id, "quantity": "1", "price": "100"}],
                "client_id": client_id,
                "debt_due_date": str(date.today() + timedelta(days=7)),
            },
        ]
    }
    response = await client.post("/api/sync/sales", headers=owner_headers, json=batch)
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["applied"]) == 2
    assert len(result["errors"]) == 1
    assert result["errors"][0]["client_op_id"] == "device-a-2"
    assert {s["client_op_id"] for s in result["applied"]} == {"device-a-1", "device-a-3"}

    response = await client.get(f"/api/debts/client/{client_id}", headers=owner_headers)
    summary = response.json()
    assert len(summary["debts"]) == 1
    assert summary["debts"][0]["balance"] == "100.00"

    # повторная отправка той же пачки (обрыв связи после ответа) не задваивает продажу
    response = await client.post("/api/sync/sales", headers=owner_headers, json=batch)
    assert response.status_code == 200
    result_retry = response.json()
    assert len(result_retry["applied"]) == 2
    assert {s["id"] for s in result_retry["applied"]} == {s["id"] for s in result["applied"]}

    # долг не задвоился повторной отправкой той же офлайн-пачки
    response = await client.get(f"/api/debts/client/{client_id}", headers=owner_headers)
    assert len(response.json()["debts"]) == 1


async def test_sync_sales_duplicate_client_op_id_in_same_batch_via_api(client, owner_headers):
    # обрыв связи → клиент повторяет продажу в той же офлайн-пачке под тем же
    # client_op_id — второе вхождение бьётся об UNIQUE(tenant_id, client_op_id),
    # это не должно ронять обработку остальных продаж пачки необработанным 500
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар дубль", "purchase_price": "50", "retail_price": "100"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "10"}]},
    )

    batch = {
        "sales": [
            {
                "client_op_id": "device-b-1",
                "warehouse_id": 1,
                "payment_method": "cash",
                "items": [{"product_id": product_id, "quantity": "1", "price": "100"}],
            },
            {
                "client_op_id": "device-b-1",  # дубль первой продажи в этой же пачке
                "warehouse_id": 1,
                "payment_method": "cash",
                "items": [{"product_id": product_id, "quantity": "1", "price": "100"}],
            },
            {
                "client_op_id": "device-b-2",
                "warehouse_id": 1,
                "payment_method": "cash",
                "items": [{"product_id": product_id, "quantity": "1", "price": "100"}],
            },
        ]
    }
    response = await client.post("/api/sync/sales", headers=owner_headers, json=batch)
    assert response.status_code == 200, response.text
    result = response.json()
    # обе попытки под дублирующим client_op_id резолвятся в одну и ту же продажу
    # (без 500 на весь синк), третья независимая продажа применяется как обычно
    assert len(result["errors"]) == 0
    assert len(result["applied"]) == 3
    applied_ids = {s["id"] for s in result["applied"] if s["client_op_id"] == "device-b-1"}
    assert len(applied_ids) == 1
    assert any(s["client_op_id"] == "device-b-2" for s in result["applied"])


async def test_sync_returns_receipts_writeoffs_via_api(client, owner_headers):
    # один и тот же офлайн-синк принимает все четыре типа операций сразу —
    # проверяем успешное применение и идемпотентность повторной отправки пачки
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар для синка", "purchase_price": "50", "retail_price": "100"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "20"}]},
    )
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "5", "price": "100"}],
        },
    )
    sale = response.json()
    sale_line_id = sale["lines"][0]["id"]

    batch = {
        "returns": [
            {
                "client_op_id": "return-1",
                "sale_id": sale["id"],
                "items": [{"sale_line_id": sale_line_id, "quantity": "1"}],
                "note": "не подошло",
            }
        ],
        "receipts": [
            {
                "client_op_id": "receipt-1",
                "warehouse_id": 1,
                "lines": [{"product_id": product_id, "quantity": "10", "cost": "50"}],
            }
        ],
        "writeoffs": [
            {
                "client_op_id": "writeoff-1",
                "warehouse_id": 1,
                "lines": [{"product_id": product_id, "quantity": "2"}],
                "note": "бой",
            }
        ],
    }
    response = await client.post("/api/sync/sales", headers=owner_headers, json=batch)
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["errors"]) == 0
    assert len(result["applied_returns"]) == 1
    assert result["applied_returns"][0]["client_op_id"] == "return-1"
    assert len(result["applied_receipts"]) == 1
    assert result["applied_receipts"][0]["client_op_id"] == "receipt-1"
    assert len(result["applied_writeoffs"]) == 1
    assert result["applied_writeoffs"][0]["client_op_id"] == "writeoff-1"

    # остаток: 20 - 5 (продажа) + 1 (возврат) + 10 (приёмка) - 2 (списание) = 24
    response = await client.get("/api/inventory/stock", headers=owner_headers)
    item = next(i for i in response.json() if i["product_id"] == product_id)
    assert item["quantity"] == "24.000"

    # повторная отправка той же пачки не задваивает ни одну из операций
    response = await client.post("/api/sync/sales", headers=owner_headers, json=batch)
    assert response.status_code == 200, response.text
    retry = response.json()
    assert len(retry["errors"]) == 0
    assert retry["applied_returns"][0]["id"] == result["applied_returns"][0]["id"]
    assert retry["applied_receipts"][0]["id"] == result["applied_receipts"][0]["id"]
    assert retry["applied_writeoffs"][0]["id"] == result["applied_writeoffs"][0]["id"]

    response = await client.get("/api/inventory/stock", headers=owner_headers)
    item = next(i for i in response.json() if i["product_id"] == product_id)
    assert item["quantity"] == "24.000"


async def test_sync_error_has_typed_code_via_api(client, owner_headers):
    # code = имя класса исключения — фронт различает причину отказа без
    # парсинга текста сообщения
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар с кодом ошибки", "purchase_price": "50", "retail_price": "100"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "1"}]},
    )

    batch = {
        "sales": [
            {
                "client_op_id": "op-insufficient-stock",
                "warehouse_id": 1,
                "payment_method": "cash",
                "items": [{"product_id": product_id, "quantity": "1000", "price": "100"}],
            }
        ]
    }
    response = await client.post("/api/sync/sales", headers=owner_headers, json=batch)
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["errors"]) == 1
    error = result["errors"][0]
    assert error["op_type"] == "sale"
    assert error["code"] == "InsufficientStockError"
    assert error["client_op_id"] == "op-insufficient-stock"


async def test_sync_credit_sale_with_paid_now_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Офлайн частичный", "purchase_price": "50", "retail_price": "500"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "10"}]},
    )
    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Офлайн долг"}
    )
    client_id = response.json()["id"]

    batch = {
        "sales": [
            {
                "client_op_id": "paid-now-offline-1",
                "warehouse_id": 1,
                "payment_method": "credit",
                "items": [{"product_id": product_id, "quantity": "1", "price": "5000"}],
                "client_id": client_id,
                "debt_due_date": str(date.today() + timedelta(days=7)),
                "paid_now": "3000",
            }
        ]
    }
    response = await client.post("/api/sync/sales", headers=owner_headers, json=batch)
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["applied"]) == 1
    assert result["applied"][0]["total"] == "5000.00"

    response = await client.get(f"/api/debts/client/{client_id}", headers=owner_headers)
    debts = response.json()["debts"]
    assert len(debts) == 1
    assert debts[0]["amount"] == "2000.00"
    assert debts[0]["balance"] == "2000.00"

    # повтор той же client_op_id не задваивает
    response = await client.post("/api/sync/sales", headers=owner_headers, json=batch)
    assert response.status_code == 200
    assert len(response.json()["applied"]) == 1
    response = await client.get(f"/api/debts/client/{client_id}", headers=owner_headers)
    assert len(response.json()["debts"]) == 1
