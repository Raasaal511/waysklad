from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import openpyxl
import pytest
from PIL import Image


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
        json={
            "supplier_id": supplier_id,
            "warehouse_id": 1,
            "amount": "50000",
            "due_date": today,
            "note": "цемент",
        },
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


async def test_debts_client_summary_as_of_via_api(client, owner_headers):
    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Ахмед"},
    )
    client_id = response.json()["id"]

    response = await client.post(
        "/api/debts",
        headers=owner_headers,
        json={"client_id": client_id, "warehouse_id": 1, "amount": "1000"},
    )
    assert response.status_code == 201, response.text
    debt_id = response.json()["id"]

    before = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()
    after = (date.today() + timedelta(days=1)).isoformat()

    response = await client.post(
        f"/api/debts/{debt_id}/repayments",
        headers=owner_headers,
        json={"amount": "300", "paid_on": before},
    )
    assert response.status_code == 200, response.text

    response = await client.post(
        f"/api/debts/{debt_id}/repayments",
        headers=owner_headers,
        json={"amount": "200", "paid_on": after},
    )
    assert response.status_code == 200, response.text

    # снимок на «сегодня» видит только первое погашение (before), не второе (after)
    response = await client.get(f"/api/debts/client/{client_id}?on={today}", headers=owner_headers)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["total_balance"] == "700.00"
    assert len(summary["debts"][0]["repayments"]) == 1

    # без ?on= — текущий момент, видны оба погашения
    response = await client.get(f"/api/debts/client/{client_id}", headers=owner_headers)
    summary = response.json()
    assert summary["total_balance"] == "500.00"
    assert len(summary["debts"][0]["repayments"]) == 2


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


async def test_storekeeper_limited_to_assigned_warehouse_via_api(
    client, owner_headers, random_phone
):
    # заводим кладовщика и второй склад, назначаем его только на второй склад
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Руслан", "phone": random_phone(), "password": "secret123",
            "role": "storekeeper",
        },
    )
    storekeeper_id = response.json()["id"]

    login = await client.post(
        "/api/auth/login",
        json={"phone": response.json()["phone"], "password": "secret123"},
    )
    storekeeper_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    warehouses = (await client.get("/api/inventory/warehouses", headers=owner_headers)).json()
    main_warehouse_id = warehouses[0]["id"]

    # в момент создания кладовщика склад был единственным — сотрудник привязан
    # к нему автоматически; снимаем эту привязку, чтобы проверить ограничение
    # доступа именно ко второму (явно не назначенному) складу
    response = await client.put(
        f"/api/inventory/warehouses/{main_warehouse_id}/assignments",
        headers=owner_headers,
        json={"user_ids": []},
    )
    assert response.status_code == 200, response.text

    response = await client.post(
        "/api/inventory/warehouses",
        headers=owner_headers,
        json={"name": "Склад Б", "assigned_user_ids": [storekeeper_id]},
    )
    assert response.status_code == 201, response.text
    second_warehouse = response.json()
    assert second_warehouse["assigned_user_ids"] == [storekeeper_id]

    # кладовщик видит только назначенный склад
    response = await client.get("/api/inventory/warehouses", headers=storekeeper_headers)
    assert [w["id"] for w in response.json()] == [second_warehouse["id"]]

    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Кирпич", "purchase_price": "10", "retail_price": "15"},
        )
    ).json()

    # приёмка на назначенный склад — можно
    response = await client.post(
        "/api/inventory/receive",
        headers=storekeeper_headers,
        json={
            "warehouse_id": second_warehouse["id"],
            "lines": [{"product_id": product["id"], "quantity": "10"}],
        },
    )
    assert response.status_code == 201, response.text

    # приёмка на чужой (не назначенный) склад — запрещена
    response = await client.post(
        "/api/inventory/receive",
        headers=storekeeper_headers,
        json={
            "warehouse_id": main_warehouse_id,
            "lines": [{"product_id": product["id"], "quantity": "10"}],
        },
    )
    assert response.status_code == 403

    # владелец меняет назначения — снимает кладовщика со склада
    response = await client.put(
        f"/api/inventory/warehouses/{second_warehouse['id']}/assignments",
        headers=owner_headers,
        json={"user_ids": []},
    )
    assert response.status_code == 200, response.text
    assert response.json()["assigned_user_ids"] == []

    response = await client.get("/api/inventory/warehouses", headers=storekeeper_headers)
    assert response.json() == []


async def test_counterparties_scoped_by_warehouse_via_api(client, owner_headers, random_phone):
    # клиент/поставщик привязаны к складу транзитивно — через продажу/приёмку
    # на этом складе (warehouse_client_links/warehouse_supplier_links); продавец,
    # привязанный только к своему складу, не должен видеть чужих контрагентов
    warehouses = (await client.get("/api/inventory/warehouses", headers=owner_headers)).json()
    main_warehouse_id = warehouses[0]["id"]

    response = await client.post(
        "/api/inventory/warehouses", headers=owner_headers, json={"name": "Склад Б"}
    )
    assert response.status_code == 201, response.text
    second_warehouse_id = response.json()["id"]

    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар для контрагентов", "purchase_price": "50", "retail_price": "100"},
    )
    product_id = response.json()["id"]
    for warehouse_id in (main_warehouse_id, second_warehouse_id):
        await client.post(
            "/api/inventory/receive",
            headers=owner_headers,
            json={"warehouse_id": warehouse_id, "lines": [{"product_id": product_id, "quantity": "10"}]},
        )

    client_main = (
        await client.post(
            "/api/counterparties/clients", headers=owner_headers, json={"name": "Клиент склада А"}
        )
    ).json()
    client_second = (
        await client.post(
            "/api/counterparties/clients", headers=owner_headers, json={"name": "Клиент склада Б"}
        )
    ).json()
    supplier_main = (
        await client.post(
            "/api/counterparties/suppliers", headers=owner_headers, json={"name": "Поставщик склада А"}
        )
    ).json()
    supplier_second = (
        await client.post(
            "/api/counterparties/suppliers", headers=owner_headers, json={"name": "Поставщик склада Б"}
        )
    ).json()

    # засвечиваем каждого контрагента на своём складе продажей/приёмкой
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": main_warehouse_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "1", "price": "100"}],
            "client_id": client_main["id"],
        },
    )
    assert response.status_code == 201, response.text
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": second_warehouse_id,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "1", "price": "100"}],
            "client_id": client_second["id"],
        },
    )
    assert response.status_code == 201, response.text
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": main_warehouse_id,
            "lines": [{"product_id": product_id, "quantity": "1", "cost": "50"}],
            "supplier_id": supplier_main["id"],
            "debt_due_date": str(date.today() + timedelta(days=7)),
        },
    )
    assert response.status_code == 201, response.text
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": second_warehouse_id,
            "lines": [{"product_id": product_id, "quantity": "1", "cost": "50"}],
            "supplier_id": supplier_second["id"],
            "debt_due_date": str(date.today() + timedelta(days=7)),
        },
    )
    assert response.status_code == 201, response.text

    # владелец видит всех
    response = await client.get("/api/counterparties/clients", headers=owner_headers)
    names = {c["name"] for c in response.json()}
    assert {"Клиент склада А", "Клиент склада Б"} <= names
    response = await client.get("/api/counterparties/suppliers", headers=owner_headers)
    names = {s["name"] for s in response.json()}
    assert {"Поставщик склада А", "Поставщик склада Б"} <= names

    # продавец, назначенный только на склад А, видит только своих контрагентов
    seller_phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Продавец А", "phone": seller_phone, "password": "secret123",
            "role": "seller", "warehouse_ids": [main_warehouse_id],
        },
    )
    assert response.status_code == 201, response.text
    login = await client.post(
        "/api/auth/login", json={"phone": seller_phone, "password": "secret123"}
    )
    seller_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await client.get("/api/counterparties/clients", headers=seller_headers)
    names = {c["name"] for c in response.json()}
    assert "Клиент склада А" in names
    assert "Клиент склада Б" not in names

    response = await client.get("/api/counterparties/suppliers", headers=seller_headers)
    names = {s["name"] for s in response.json()}
    assert "Поставщик склада А" in names
    assert "Поставщик склада Б" not in names


async def test_order_full_lifecycle_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Торт на заказ", "purchase_price": "1500", "retail_price": "3000"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "1"}]},
    )

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Милана"}
    )
    client_id = response.json()["id"]

    response = await client.post(
        "/api/orders",
        headers=owner_headers,
        json={
            "client_id": client_id,
            "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "1", "price": "3000"}],
            "due_date": date.today().isoformat(),
            "prepayment": "1000",
            "source": "whatsapp",
            "note": "надпись «С юбилеем»",
        },
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["to_pay"] == "2000.00"
    assert order["source"] == "whatsapp"
    assert order["number"] is not None
    order_id = order["id"]

    # остаток зарезервирован под заказ — обычная продажа не пройдёт
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "1", "price": "3000"}],
        },
    )
    assert response.status_code == 400

    response = await client.patch(
        f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": "in_progress"}
    )
    assert response.status_code == 200

    # нельзя перескочить сразу в "выдан" из "в работе" сменой статуса — только через /issue
    response = await client.patch(
        f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": "issued"}
    )
    assert response.status_code == 400

    response = await client.patch(
        f"/api/orders/{order_id}/status", headers=owner_headers, json={"new_status": "ready"}
    )
    assert response.status_code == 200

    response = await client.post(
        f"/api/orders/{order_id}/issue",
        headers=owner_headers,
        json={"payment_method": "cash", "cash_received": "2000"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["sale"]["total"] == "2000.00"  # доплата, не полная сумма заказа
    assert result["sale"]["change"] == "0.00"
    assert result["order"]["status"] == "issued"
    assert result["order"]["sale_id"] == result["sale"]["id"]
    assert result["sale"]["order_id"] == order_id

    response = await client.get("/api/orders", headers=owner_headers)
    assert response.json() == []  # выданные заказы не входят в список активных

    response = await client.get("/api/orders/completed", headers=owner_headers)
    assert response.status_code == 200
    completed = response.json()
    assert len(completed) == 1
    assert completed[0]["id"] == order_id
    assert completed[0]["status"] == "issued"
    assert completed[0]["number"] is not None

    response = await client.get(f"/api/orders/{order_id}", headers=owner_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "issued"

    response = await client.get(f"/api/orders/{order_id}/history", headers=owner_headers)
    assert response.status_code == 200
    actions = [e["action"] for e in response.json()]
    assert "order.create" in actions
    assert "order.issue" in actions

    # остаток физически списан (весь куплен) — позиция с нулевым остатком не
    # входит в список (GET /inventory/stock отдаёт только ненулевые остатки)
    response = await client.get("/api/inventory/stock", headers=owner_headers)
    assert all(i["product_id"] != product_id for i in response.json())


async def test_order_edit_and_cancel_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Платье", "purchase_price": "1000", "retail_price": "2000"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "5"}]},
    )

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Хава"}
    )
    client_id = response.json()["id"]

    response = await client.post(
        "/api/orders",
        headers=owner_headers,
        json={
            "client_id": client_id,
            "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "2", "price": "2000"}],
            "due_date": date.today().isoformat(),
        },
    )
    order_id = response.json()["id"]

    # редактирование состава пересчитывает резерв
    response = await client.patch(
        f"/api/orders/{order_id}",
        headers=owner_headers,
        json={
            "client_id": client_id,
            "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "4", "price": "2000"}],
            "due_date": date.today().isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == "8000.00"

    response = await client.get("/api/inventory/stock", headers=owner_headers)
    stock = next(i for i in response.json() if i["product_id"] == product_id)
    assert stock["reserved"] == "4.000"

    # отмена освобождает резерв
    response = await client.post(
        f"/api/orders/{order_id}/cancel", headers=owner_headers, json={"reason": "передумала"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    response = await client.get("/api/inventory/stock", headers=owner_headers)
    stock = next(i for i in response.json() if i["product_id"] == product_id)
    assert stock["reserved"] == "0.000"

    response = await client.get("/api/orders/completed", headers=owner_headers)
    completed = response.json()
    assert len(completed) == 1
    assert completed[0]["status"] == "cancelled"

    # отменённый заказ нельзя редактировать/выдать
    response = await client.patch(
        f"/api/orders/{order_id}",
        headers=owner_headers,
        json={
            "client_id": client_id,
            "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "1", "price": "2000"}],
        },
    )
    assert response.status_code == 400


async def test_notifications_websocket_push(client, owner_headers, random_phone, db_session_factory):
    # push вместо периодического опроса GET /notifications: задача, назначенная
    # сотруднику, должна прилететь в открытый WS-сокет этого сотрудника сразу
    from starlette.testclient import TestClient

    from app.main import app as fastapi_app

    phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={"name": "Хеда", "phone": phone, "password": "secret123", "role": "seller"},
    )
    employee_id = response.json()["id"]
    login = await client.post("/api/auth/login", json={"phone": phone, "password": "secret123"})
    employee_token = login.json()["access_token"]

    sync_client = TestClient(fastapi_app)
    with sync_client.websocket_connect(f"/api/notifications/ws?token={employee_token}") as ws:
        response = await client.post(
            "/api/tasks",
            headers=owner_headers,
            json={"title": "Через WS", "assigned_user_id": employee_id},
        )
        assert response.status_code == 201, response.text
        task_id = response.json()["id"]

        event = ws.receive_json()
        assert event["kind"] == "task_assigned"
        assert event["entity_id"] == task_id


async def test_notifications_websocket_rejects_invalid_token(client, owner_headers):
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    from app.main import app as fastapi_app

    sync_client = TestClient(fastapi_app)
    with pytest.raises(WebSocketDisconnect):
        with sync_client.websocket_connect("/api/notifications/ws?token=garbage"):
            pass


async def test_task_full_lifecycle_via_api(client, owner_headers, random_phone):
    # 1. сотрудник, которому назначим задачу
    phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={"name": "Хеда", "phone": phone, "password": "secret123", "role": "seller"},
    )
    assert response.status_code == 201, response.text
    employee_id = response.json()["id"]

    response = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "secret123"}
    )
    employee_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    # 2. владелец ставит задачу сотруднику
    response = await client.post(
        "/api/tasks",
        headers=owner_headers,
        json={
            "title": "Позвонить поставщику",
            "assigned_user_id": employee_id,
            "note": "по цементу",
            "due_date": date.today().isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    task = response.json()
    task_id = task["id"]
    assert task["status"] == "new"
    assert task["number"] is not None
    assert task["assigned_user_name"] == "Хеда"

    # 3. уведомление о назначении пришло сотруднику, а не владельцу
    response = await client.get("/api/notifications", headers=employee_headers)
    assert response.status_code == 200
    notifications = response.json()
    assert notifications["unread"] == 1
    assert notifications["items"][0]["kind"] == "task_assigned"

    response = await client.get("/api/notifications", headers=owner_headers)
    assert response.json()["unread"] == 0

    # 4. сотрудник видит только свою задачу и ведёт её по доске
    response = await client.get("/api/tasks", headers=employee_headers)
    assert [t["id"] for t in response.json()] == [task_id]

    response = await client.patch(
        f"/api/tasks/{task_id}/status", headers=employee_headers, json={"new_status": "in_progress"}
    )
    assert response.status_code == 200

    response = await client.patch(
        f"/api/tasks/{task_id}/status", headers=employee_headers, json={"new_status": "done"}
    )
    assert response.status_code == 200

    # done — терминальный статус
    response = await client.patch(
        f"/api/tasks/{task_id}/status", headers=employee_headers, json={"new_status": "new"}
    )
    assert response.status_code == 400

    # 5. активные/завершённые списки и история
    response = await client.get("/api/tasks", headers=owner_headers)
    assert response.json() == []

    response = await client.get("/api/tasks/completed", headers=owner_headers)
    completed = response.json()
    assert len(completed) == 1 and completed[0]["status"] == "done"

    response = await client.get(f"/api/tasks/{task_id}/history", headers=owner_headers)
    actions = [e["action"] for e in response.json()]
    assert actions == ["task.status", "task.status", "task.create"]

    # 6. автор получил уведомление о выполнении
    response = await client.get("/api/notifications", headers=owner_headers)
    owner_notifications = response.json()
    assert owner_notifications["unread"] == 1
    assert owner_notifications["items"][0]["kind"] == "task_done"
    notification_id = owner_notifications["items"][0]["id"]

    response = await client.post(
        f"/api/notifications/{notification_id}/read", headers=owner_headers
    )
    assert response.status_code == 200
    assert (await client.get("/api/notifications", headers=owner_headers)).json()["unread"] == 0


async def test_task_client_link_via_api(client, owner_headers, random_phone):
    # CRM: задача может быть привязана к клиенту — попадает в его ленту событий
    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Ахмед"}
    )
    client_id = response.json()["id"]

    response = await client.post(
        "/api/tasks",
        headers=owner_headers,
        json={"title": "Перезвонить по заказу", "client_id": client_id},
    )
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["client_id"] == client_id

    # несуществующий клиент — понятная ошибка, а не молчаливое сохранение
    response = await client.post(
        "/api/tasks", headers=owner_headers, json={"title": "Без клиента", "client_id": 999999},
    )
    assert response.status_code == 404, response.text

    # PATCH может как сменить привязку, так и явно снять её
    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Марьям"}
    )
    other_client_id = response.json()["id"]

    response = await client.patch(
        f"/api/tasks/{task['id']}", headers=owner_headers, json={"client_id": other_client_id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["client_id"] == other_client_id

    response = await client.patch(
        f"/api/tasks/{task['id']}", headers=owner_headers, json={"client_id": None},
    )
    assert response.status_code == 200
    assert response.json()["client_id"] is None


async def test_task_client_link_tenant_isolation_via_api(client, owner_headers, random_phone):
    # клиент другого магазина не должен быть доступен для привязки задачи
    other_owner_phone = random_phone()
    await client.post(
        "/api/auth/register",
        json={
            "shop_name": "Чужой магазин", "owner_name": "Другой", "phone": other_owner_phone,
            "password": "secret123",
        },
    )
    login = await client.post(
        "/api/auth/login", json={"phone": other_owner_phone, "password": "secret123"}
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = await client.post(
        "/api/counterparties/clients", headers=other_headers, json={"name": "Чужой клиент"}
    )
    foreign_client_id = response.json()["id"]

    response = await client.post(
        "/api/tasks",
        headers=owner_headers,
        json={"title": "Задача", "client_id": foreign_client_id},
    )
    assert response.status_code == 404, response.text


async def test_client_timeline_via_api(client, owner_headers):
    # CRM: единая лента событий клиента вместо поиска по Продажам/Заказам/Долгам/Задачам
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар для ленты", "purchase_price": "100", "retail_price": "200"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "10"}]},
    )

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Ахмед лента"}
    )
    client_id = response.json()["id"]

    # пустая лента для нового клиента — не ошибка
    response = await client.get(f"/api/counterparties/clients/{client_id}/timeline", headers=owner_headers)
    assert response.status_code == 200
    assert response.json() == []

    # обычная продажа
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1, "payment_method": "cash", "client_id": client_id,
            "items": [{"product_id": product_id, "quantity": "1", "price": "200"}],
        },
    )
    assert response.status_code == 201, response.text

    # продажа в долг + погашение
    response = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1, "payment_method": "credit", "client_id": client_id,
            "items": [{"product_id": product_id, "quantity": "1", "price": "200"}],
            "debt_due_date": str(date.today() + timedelta(days=7)),
        },
    )
    assert response.status_code == 201, response.text
    debts = (await client.get(f"/api/debts/client/{client_id}", headers=owner_headers)).json()["debts"]
    debt_id = debts[0]["id"]
    response = await client.post(
        f"/api/debts/{debt_id}/repayments", headers=owner_headers, json={"amount": "50"},
    )
    assert response.status_code == 200, response.text

    # заказ
    response = await client.post(
        "/api/orders",
        headers=owner_headers,
        json={
            "client_id": client_id, "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "1", "price": "200"}],
            "due_date": date.today().isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["id"]

    # задача, привязанная к клиенту
    response = await client.post(
        "/api/tasks", headers=owner_headers, json={"title": "Уточнить размер", "client_id": client_id},
    )
    assert response.status_code == 201, response.text
    task_id = response.json()["id"]

    response = await client.get(f"/api/counterparties/clients/{client_id}/timeline", headers=owner_headers)
    assert response.status_code == 200
    events = response.json()

    assert any(e["type"] == "sale" for e in events)
    assert sum(1 for e in events if e["type"] == "sale") == 2
    assert any(e["type"] == "debt_issued" and e["entity_id"] == debt_id for e in events)
    assert any(e["type"] == "debt_repaid" and e["entity_id"] == debt_id for e in events)
    assert any(e["type"] == "order_created" and e["entity_id"] == order_id for e in events)
    assert any(e["type"] == "task" and e["entity_id"] == task_id for e in events)

    # новые события сверху (по убыванию даты) — свежесозданная задача первая
    assert events[0]["type"] == "task"

    # несуществующий клиент — 404, не пустая лента (не спутать «нет событий» с «нет доступа»)
    response = await client.get("/api/counterparties/clients/999999/timeline", headers=owner_headers)
    assert response.status_code == 404


async def test_client_summary_via_api(client, owner_headers):
    # CRM: карточка клиента как хаб — баланс долга и счётчики активных заказов/задач
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар для сводки", "purchase_price": "100", "retail_price": "200"},
    )
    product_id = response.json()["id"]
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "10"}]},
    )

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Ахмед сводка"}
    )
    client_id = response.json()["id"]

    response = await client.get(f"/api/counterparties/clients/{client_id}", headers=owner_headers)
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["client"]["id"] == client_id
    assert summary["debt_balance"] == "0.00"
    assert summary["active_orders_count"] == 0
    assert summary["open_tasks_count"] == 0

    # продажа в долг — баланс растёт
    await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1, "payment_method": "credit", "client_id": client_id,
            "items": [{"product_id": product_id, "quantity": "1", "price": "200"}],
            "debt_due_date": str(date.today() + timedelta(days=7)),
        },
    )

    # активный заказ
    await client.post(
        "/api/orders",
        headers=owner_headers,
        json={
            "client_id": client_id, "warehouse_id": 1,
            "items": [{"product_id": product_id, "quantity": "1", "price": "200"}],
            "due_date": date.today().isoformat(),
        },
    )

    # одна задача останется открытой, вторую закроем — в счётчик попадает только открытая
    response = await client.post(
        "/api/tasks", headers=owner_headers, json={"title": "Закроем", "client_id": client_id},
    )
    task_to_close_id = response.json()["id"]
    await client.post(
        "/api/tasks", headers=owner_headers, json={"title": "Останется открытой", "client_id": client_id},
    )
    await client.patch(
        f"/api/tasks/{task_to_close_id}/status", headers=owner_headers, json={"new_status": "done"},
    )

    response = await client.get(f"/api/counterparties/clients/{client_id}", headers=owner_headers)
    summary = response.json()
    assert summary["debt_balance"] == "200.00"
    assert summary["active_orders_count"] == 1
    assert summary["open_tasks_count"] == 1

    response = await client.get("/api/counterparties/clients/999999", headers=owner_headers)
    assert response.status_code == 404


async def test_seller_sees_only_own_tasks_via_api(client, owner_headers, random_phone):
    phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={"name": "Заур", "phone": phone, "password": "secret123", "role": "seller"},
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "secret123"}
    )
    seller_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.post(
        "/api/tasks", headers=owner_headers, json={"title": "Задача владельца себе"}
    )
    assert response.status_code == 201, response.text
    owner_task_id = response.json()["id"]

    response = await client.get("/api/tasks", headers=seller_headers)
    assert response.json() == []

    response = await client.get(f"/api/tasks/{owner_task_id}", headers=seller_headers)
    assert response.status_code == 403

    # продавцу нельзя назначать задачи другим (нет USERS_MANAGE)
    response = await client.post(
        "/api/tasks",
        headers=seller_headers,
        json={"title": "Чужая задача", "assigned_user_id": 1},
    )
    assert response.status_code == 403


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


async def test_audit_log_records_actions_on_entity_history(client, owner_headers):
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
    sale = await client.post(
        "/api/sales",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "payment_method": "cash",
            "items": [{"product_id": product_id, "quantity": "1.5", "price": "700"}],
        },
    )
    sale_id = sale.json()["id"]

    # история продажи — записана через тот же журнал, но по конкретной сущности
    response = await client.get(f"/api/sales/{sale_id}/history", headers=owner_headers)
    assert response.status_code == 200
    actions = [entry["action"] for entry in response.json()]
    assert actions == ["sale.create"]
    assert response.json()[0]["details"]["total"] == "1050.00"

    # история товара — отдельный журнал по своей сущности
    response = await client.get(f"/api/products/{product_id}/history", headers=owner_headers)
    assert response.status_code == 200
    assert [entry["action"] for entry in response.json()] == ["product.create"]


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


def _test_photo_bytes(size: tuple[int, int] = (2000, 1500)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color=(90, 140, 200)).save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


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


async def test_connect_telegram_via_api(client, owner_headers, random_phone):
    response = await client.post(
        "/api/auth/telegram", headers=owner_headers, json={"chat_id": "555444333"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["owner_telegram_chat_id"] == "555444333"

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

    response = await client.post(
        "/api/auth/telegram", headers=seller_headers, json={"chat_id": "111"}
    )
    assert response.status_code == 403


async def test_update_shop_summary_schedule_via_api(client, owner_headers):
    response = await client.get("/api/auth/shop", headers=owner_headers)
    assert response.status_code == 200
    shop = response.json()
    # дефолты сразу после регистрации
    assert shop["summary_daily_enabled"] is True
    assert shop["summary_weekly_enabled"] is False
    assert shop["summary_monthly_enabled"] is False
    assert shop["summary_daily_hour_msk"] == 20

    response = await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={
            "name": shop["name"],
            "summary_weekly_enabled": True,
            "summary_monthly_enabled": True,
            "summary_daily_hour_msk": 9,
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["summary_daily_enabled"] is True  # не тронули — осталось прежним
    assert updated["summary_weekly_enabled"] is True
    assert updated["summary_monthly_enabled"] is True
    assert updated["summary_daily_hour_msk"] == 9

    response = await client.patch(
        "/api/auth/shop",
        headers=owner_headers,
        json={"name": shop["name"], "summary_daily_hour_msk": 24},
    )
    assert response.status_code == 422  # вне диапазона 0..23


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
        "min_order_qty", "order_step_qty",
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


async def test_storefront_request_full_flow_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Товар для заявки",
                "purchase_price": "50",
                "retail_price": "120",
                "show_on_storefront": True,
            },
        )
    ).json()
    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "10", "cost": "50"}]},
    )
    assert response.status_code == 201, response.text

    # публичная заявка — без авторизации
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Ахмед",
            "customer_phone": "+79280001122",
            "note": "Хочу два, если есть скидка — напишите",
            "items": [{"product_id": product["id"], "quantity": "2"}],
        },
    )
    assert response.status_code == 201, response.text
    request = response.json()
    assert request["status"] == "new"
    assert request["customer_name"] == "Ахмед"

    # владелец видит заявку в списке новых
    response = await client.get("/api/storefront/requests/new", headers=owner_headers)
    assert response.status_code == 200, response.text
    ids = [r["id"] for r in response.json()]
    assert request["id"] in ids

    # без авторизации список заявок недоступен
    response = await client.get("/api/storefront/requests/new")
    assert response.status_code in (401, 403), response.text

    due = (date.today() + timedelta(days=3)).isoformat()
    response = await client.post(
        f"/api/storefront/requests/{request['id']}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )
    assert response.status_code == 200, response.text
    order = response.json()
    assert order["source"] == "storefront"
    assert order["due_date"] == due
    assert order["lines"][0]["product_id"] == product["id"]
    assert order["lines"][0]["price"] == "120.00"  # цена взята из актуального retail_price

    # клиент создан по имени+телефону из заявки
    response = await client.get("/api/counterparties/clients", headers=owner_headers, params={"query": "Ахмед"})
    assert response.status_code == 200, response.text
    clients = response.json()
    assert any(c["phone"] == "+79280001122" for c in clients)

    # повторно принять ту же заявку нельзя
    response = await client.post(
        f"/api/storefront/requests/{request['id']}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )
    assert response.status_code == 400, response.text

    # повторная заявка с тем же телефоном не плодит второго клиента
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Ахмед",
            "customer_phone": "+79280001122",
            "items": [{"product_id": product["id"], "quantity": "1"}],
        },
    )
    assert response.status_code == 201, response.text
    second_request_id = response.json()["id"]
    response = await client.post(
        f"/api/storefront/requests/{second_request_id}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )
    assert response.status_code == 200, response.text
    second_order = response.json()
    assert second_order["client_id"] == order["client_id"]  # тот же клиент, не дубль

    response = await client.get("/api/counterparties/clients", headers=owner_headers, params={"query": "Ахмед"})
    assert sum(1 for c in response.json() if c["phone"] == "+79280001122") == 1


async def test_storefront_request_rejects_unknown_variant_via_api(client, owner_headers):
    """variant_id в заявке должен принадлежать указанному товару — иначе
    заявка тихо приняла бы ссылку на несуществующий/чужой вариант."""
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product_with_variant = (
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
    real_variant_id = product_with_variant["variants"][0]["id"]

    other_product = (
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
    other_variant_id = other_product["variants"][0]["id"]

    # вариант, принадлежащий ДРУГОМУ товару — отклонено
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Покупатель",
            "items": [
                {"product_id": product_with_variant["id"], "quantity": "1", "variant_id": other_variant_id}
            ],
        },
    )
    assert response.status_code == 400, response.text

    # несуществующий variant_id — отклонено
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Покупатель",
            "items": [{"product_id": product_with_variant["id"], "quantity": "1", "variant_id": 999999}],
        },
    )
    assert response.status_code == 400, response.text

    # правильный вариант этого же товара — принято
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Покупатель",
            "items": [
                {"product_id": product_with_variant["id"], "quantity": "1", "variant_id": real_variant_id}
            ],
        },
    )
    assert response.status_code == 201, response.text


async def test_storefront_request_reject_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()
    request = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            json={"customer_name": "Тест", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()

    response = await client.post(
        f"/api/storefront/requests/{request['id']}/reject", headers=owner_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"

    # повторно отклонить/принять нельзя
    response = await client.post(
        f"/api/storefront/requests/{request['id']}/reject", headers=owner_headers
    )
    assert response.status_code == 400, response.text

    # заявка на скрытый товар отклоняется на уровне создания
    hidden = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Скрытый", "purchase_price": "10", "retail_price": "20"},
        )
    ).json()
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={"customer_name": "Тест", "items": [{"product_id": hidden["id"], "quantity": "1"}]},
    )
    assert response.status_code == 400, response.text


async def test_storefront_chat_rest_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()
    created = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()
    assert "access_token" in created and created["access_token"]
    token = created["access_token"]

    # owner-side ответ (список заявок) не содержит токен
    response = await client.get("/api/storefront/requests/new", headers=owner_headers)
    assert "access_token" not in response.json()[0]

    # покупатель пишет по своему токену
    response = await client.post(
        "/api/storefront/requests/chat", params={"token": token}, json={"text": "Уточните размер, пожалуйста"}
    )
    assert response.status_code == 201, response.text
    assert response.json()["author"] == "customer"

    # неверный токен — заявка не найдена
    response = await client.post(
        "/api/storefront/requests/chat", params={"token": "garbage"}, json={"text": "тест"}
    )
    assert response.status_code == 404, response.text

    # сотрудник читает и отвечает
    response = await client.get(
        f"/api/storefront/requests/{created['id']}/chat", headers=owner_headers
    )
    assert response.status_code == 200, response.text
    assert len(response.json()) == 1
    assert response.json()[0]["text"] == "Уточните размер, пожалуйста"

    response = await client.post(
        f"/api/storefront/requests/{created['id']}/chat",
        headers=owner_headers,
        json={"text": "Размер M подойдёт?"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["author"] == "staff"

    # покупатель по токену видит оба сообщения
    response = await client.get("/api/storefront/requests/chat", params={"token": token})
    assert response.status_code == 200, response.text
    texts = [m["text"] for m in response.json()]
    assert texts == ["Уточните размер, пожалуйста", "Размер M подойдёт?"]

    # без авторизации staff-эндпоинт недоступен
    response = await client.get(f"/api/storefront/requests/{created['id']}/chat")
    assert response.status_code in (401, 403), response.text


async def test_storefront_chat_websocket_via_api(client, owner_headers):
    from starlette.testclient import TestClient

    from app.main import app as fastapi_app

    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()
    created = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()
    token = created["access_token"]

    sync_client = TestClient(fastapi_app)
    with sync_client.websocket_connect(f"/api/storefront/requests/chat/ws?token={token}") as ws:
        response = await client.post(
            f"/api/storefront/requests/{created['id']}/chat",
            headers=owner_headers,
            json={"text": "Ответ владельца через WS"},
        )
        assert response.status_code == 201, response.text

        event = ws.receive_json()
        assert event["author"] == "staff"
        assert event["text"] == "Ответ владельца через WS"


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


async def test_storefront_request_status_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "150", "show_on_storefront": True},
        )
    ).json()
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "5", "cost": "50"}]},
    )
    created = (
        await client.post(
            f"/api/storefront/{slug}/requests",
            json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
    ).json()
    token = created["access_token"]

    response = await client.get("/api/storefront/requests/status", params={"token": token})
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "new", "order": None}

    due = (date.today() + timedelta(days=2)).isoformat()
    await client.post(
        f"/api/storefront/requests/{created['id']}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )

    response = await client.get("/api/storefront/requests/status", params={"token": token})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"
    assert body["order"]["due_date"] == due
    assert body["order"]["total"] == "150.00"

    response = await client.get("/api/storefront/requests/status", params={"token": "garbage"})
    assert response.status_code == 404, response.text


async def test_storefront_request_spam_protection_via_api(client, owner_headers):
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={"name": "Товар", "purchase_price": "50", "retail_price": "100", "show_on_storefront": True},
        )
    ).json()

    phone = "+79281234567"
    for _ in range(5):
        response = await client.post(
            f"/api/storefront/{slug}/requests",
            json={
                "customer_name": "Спамер",
                "customer_phone": phone,
                "items": [{"product_id": product["id"], "quantity": "1"}],
            },
        )
        assert response.status_code == 201, response.text

    # шестая необработанная заявка с того же телефона — отклонена
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Спамер",
            "customer_phone": phone,
            "items": [{"product_id": product["id"], "quantity": "1"}],
        },
    )
    assert response.status_code == 400, response.text

    # другой телефон — не ограничен предыдущими заявками
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Другой человек",
            "customer_phone": "+79281234568",
            "items": [{"product_id": product["id"], "quantity": "1"}],
        },
    )
    assert response.status_code == 201, response.text

    # без телефона — лимит не применяется вообще (нечем идентифицировать)
    for _ in range(3):
        response = await client.post(
            f"/api/storefront/{slug}/requests",
            json={"customer_name": "Аноним", "items": [{"product_id": product["id"], "quantity": "1"}]},
        )
        assert response.status_code == 201, response.text


async def test_storefront_request_min_and_step_qty_via_api(client, owner_headers):
    """Мин. количество и шаг заказа — ограничение только для заявки с витрины,
    не для обычной продажи/заказа (тех тестов эта фича не касается)."""
    slug = "magazin-berkat"
    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Мука оптом",
                "purchase_price": "50",
                "retail_price": "100",
                "show_on_storefront": True,
                "storefront_min_qty": "10",
                "storefront_step_qty": "10",
            },
        )
    ).json()
    assert product["storefront_min_qty"] == "10"
    assert product["storefront_step_qty"] == "10"

    response = await client.get(f"/api/storefront/{slug}")
    assert response.status_code == 200, response.text
    listed = next(p for p in response.json()["products"] if p["id"] == product["id"])
    assert listed["min_order_qty"] == "10.000"
    assert listed["order_step_qty"] == "10.000"

    # меньше минимума — отклонено
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Покупатель",
            "items": [{"product_id": product["id"], "quantity": "5"}],
        },
    )
    assert response.status_code == 400, response.text

    # не кратно шагу от минимума — отклонено
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Покупатель",
            "items": [{"product_id": product["id"], "quantity": "15"}],
        },
    )
    assert response.status_code == 400, response.text

    # минимум плюс шаг — принято
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Покупатель",
            "items": [{"product_id": product["id"], "quantity": "20"}],
        },
    )
    assert response.status_code == 201, response.text

    # тот же товар двумя строками (например, два разных варианта) —
    # мин.кол-во и шаг проверяются суммарно по товару, не по каждой строке
    response = await client.post(
        f"/api/storefront/{slug}/requests",
        json={
            "customer_name": "Покупатель",
            "items": [
                {"product_id": product["id"], "quantity": "5"},
                {"product_id": product["id"], "quantity": "5"},
            ],
        },
    )
    assert response.status_code == 201, response.text  # 5+5=10 — валидно, хотя каждая строка меньше минимума


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


async def test_inventory_documents_history_via_api(client, owner_headers):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Гвозди 100мм", "unit_code": "pcs", "purchase_price": "5", "retail_price": "10"},
    )
    product_id = response.json()["id"]

    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={
            "warehouse_id": 1,
            "lines": [{"product_id": product_id, "quantity": "50", "cost": "5"}],
            "note": "Первая поставка",
        },
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        "/api/inventory/write-off",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "3"}]},
    )
    assert response.status_code == 201, response.text

    response = await client.get("/api/inventory/documents", headers=owner_headers)
    assert response.status_code == 200, response.text
    documents = response.json()
    assert len(documents) == 2
    # новые сначала
    assert documents[0]["type"] == "write_off"
    assert documents[1]["type"] == "receipt"
    assert documents[1]["note"] == "Первая поставка"
    assert documents[1]["lines"] == [
        {"product_id": product_id, "variant_id": None, "quantity": "50.000", "cost": "5.00"}
    ]
    assert documents[0]["lines"][0]["quantity"] == "3.000"
    assert all("number" in d and "created_at" in d and "author_id" in d for d in documents)

    response = await client.get("/api/inventory/documents/export.xlsx", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(response.content) > 0

    response = await client.get("/api/inventory/documents/export.csv", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    csv_text = response.content.decode("utf-8-sig")
    assert "Гвозди 100мм" in csv_text
    assert "Первая поставка" in csv_text

    response = await client.get("/api/inventory/documents/export.pdf", headers=owner_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")


async def test_seller_sees_only_own_warehouse_documents(client, owner_headers, random_phone):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар склад 2", "unit_code": "pcs", "purchase_price": "1", "retail_price": "2"},
    )
    product_id = response.json()["id"]

    response = await client.post(
        "/api/inventory/warehouses", headers=owner_headers, json={"name": "Второй склад"}
    )
    warehouse2_id = response.json()["id"]

    phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Продавец",
            "phone": phone,
            "password": "secret123",
            "role": "seller",
            "warehouse_ids": [warehouse2_id],
        },
    )
    assert response.status_code == 201, response.text

    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product_id, "quantity": "5"}]},
    )
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": warehouse2_id, "lines": [{"product_id": product_id, "quantity": "7"}]},
    )

    response = await client.post("/api/auth/login", json={"phone": phone, "password": "secret123"})
    seller_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.get("/api/inventory/documents", headers=seller_headers)
    assert response.status_code == 200, response.text
    documents = response.json()
    assert len(documents) == 1
    assert documents[0]["warehouse_id"] == warehouse2_id


async def test_get_inventory_document_via_api(client, owner_headers, random_phone):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар документа", "unit_code": "pcs", "purchase_price": "1", "retail_price": "2"},
    )
    product_id = response.json()["id"]

    response = await client.post(
        "/api/inventory/warehouses", headers=owner_headers, json={"name": "Второй склад"}
    )
    warehouse2_id = response.json()["id"]

    response = await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": warehouse2_id, "lines": [{"product_id": product_id, "quantity": "5"}]},
    )
    assert response.status_code == 201, response.text
    document_id = response.json()["id"]

    response = await client.get(f"/api/inventory/documents/{document_id}", headers=owner_headers)
    assert response.status_code == 200, response.text
    document = response.json()
    assert document["warehouse_id"] == warehouse2_id
    assert document["lines"][0]["product_id"] == product_id

    response = await client.get("/api/inventory/documents/999999", headers=owner_headers)
    assert response.status_code == 404

    phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Продавец",
            "phone": phone,
            "password": "secret123",
            "role": "seller",
            "warehouse_ids": [1],
        },
    )
    assert response.status_code == 201, response.text
    response = await client.post("/api/auth/login", json={"phone": phone, "password": "secret123"})
    seller_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.get(f"/api/inventory/documents/{document_id}", headers=seller_headers)
    assert response.status_code == 403


async def test_seller_sees_only_own_warehouse_orders(client, owner_headers, random_phone):
    response = await client.post(
        "/api/products",
        headers=owner_headers,
        json={"name": "Товар заказа", "unit_code": "pcs", "purchase_price": "1", "retail_price": "2"},
    )
    product_id = response.json()["id"]

    response = await client.post(
        "/api/inventory/warehouses", headers=owner_headers, json={"name": "Второй склад"}
    )
    warehouse2_id = response.json()["id"]

    for wh_id in (1, warehouse2_id):
        await client.post(
            "/api/inventory/receive",
            headers=owner_headers,
            json={"warehouse_id": wh_id, "lines": [{"product_id": product_id, "quantity": "5"}]},
        )

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Клиент"},
    )
    client_id = response.json()["id"]

    for wh_id in (1, warehouse2_id):
        response = await client.post(
            "/api/orders",
            headers=owner_headers,
            json={
                "client_id": client_id,
                "warehouse_id": wh_id,
                "items": [{"product_id": product_id, "quantity": "1", "price": "2"}],
                "due_date": date.today().isoformat(),
            },
        )
        assert response.status_code == 201, response.text

    phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Продавец",
            "phone": phone,
            "password": "secret123",
            "role": "seller",
            "warehouse_ids": [warehouse2_id],
        },
    )
    assert response.status_code == 201, response.text
    response = await client.post("/api/auth/login", json={"phone": phone, "password": "secret123"})
    seller_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.get("/api/orders", headers=seller_headers)
    assert response.status_code == 200, response.text
    orders = response.json()
    assert len(orders) == 1
    assert orders[0]["warehouse_id"] == warehouse2_id


async def test_seller_sees_only_own_warehouse_debts(client, owner_headers, random_phone):
    response = await client.post(
        "/api/inventory/warehouses", headers=owner_headers, json={"name": "Второй склад"}
    )
    warehouse2_id = response.json()["id"]

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Клиент долга"},
    )
    client_id = response.json()["id"]

    for wh_id in (1, warehouse2_id):
        response = await client.post(
            "/api/debts",
            headers=owner_headers,
            json={"client_id": client_id, "warehouse_id": wh_id, "amount": "500"},
        )
        assert response.status_code == 201, response.text

    phone = random_phone()
    response = await client.post(
        "/api/auth/employees",
        headers=owner_headers,
        json={
            "name": "Продавец",
            "phone": phone,
            "password": "secret123",
            "role": "seller",
            "warehouse_ids": [warehouse2_id],
        },
    )
    assert response.status_code == 201, response.text
    response = await client.post("/api/auth/login", json={"phone": phone, "password": "secret123"})
    seller_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    response = await client.get("/api/debts", headers=seller_headers)
    assert response.status_code == 200, response.text
    debts = response.json()
    assert len(debts) == 1
    assert debts[0]["warehouse_id"] == warehouse2_id
