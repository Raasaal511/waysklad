from datetime import date


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
