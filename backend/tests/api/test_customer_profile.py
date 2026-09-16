from datetime import date, timedelta


async def test_customer_profile_requires_auth(client):
    response = await client.get("/api/auth/customer/me")
    assert response.status_code == 401, response.text

    response = await client.put("/api/auth/customer/me", json={"name": "Ахмед"})
    assert response.status_code == 401, response.text


async def test_customer_profile_default_empty_name(client, customer_headers):
    headers, phone = await customer_headers()

    response = await client.get("/api/auth/customer/me", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["phone"] == phone
    assert body["name"] == ""
    assert body["stats"] == {
        "requests_total": 0, "requests_accepted": 0, "requests_rejected": 0,
    }


async def test_customer_profile_update_name(client, customer_headers):
    headers, phone = await customer_headers()

    response = await client.put(
        "/api/auth/customer/me", headers=headers, json={"name": "Ахмед Юсупов"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Ахмед Юсупов"
    assert body["phone"] == phone

    # изменение сохранилось
    response = await client.get("/api/auth/customer/me", headers=headers)
    assert response.json()["name"] == "Ахмед Юсупов"


async def test_customer_profile_update_name_rejects_blank(client, customer_headers):
    headers, _ = await customer_headers()

    response = await client.put("/api/auth/customer/me", headers=headers, json={"name": "   "})
    assert response.status_code == 400, response.text

    response = await client.put("/api/auth/customer/me", headers=headers, json={"name": ""})
    assert response.status_code == 422, response.text  # min_length=1 на схеме


async def test_customer_profile_stats_across_shops(client, owner_headers, customer_headers):
    """Статистика в профиле считает заявки по ВСЕМ магазинам платформы, не
    одному — тот же смысл, что у GET /storefront/requests/my."""
    buyer_headers, _ = await customer_headers()

    await client.patch(
        "/api/auth/shop", headers=owner_headers, json={"name": "Магазин Беркат", "storefront_enabled": True}
    )
    product = (
        await client.post(
            "/api/products",
            headers=owner_headers,
            json={
                "name": "Товар",
                "purchase_price": "50",
                "retail_price": "120",
                "show_on_storefront": True,
            },
        )
    ).json()
    await client.post(
        "/api/inventory/receive",
        headers=owner_headers,
        json={"warehouse_id": 1, "lines": [{"product_id": product["id"], "quantity": "10", "cost": "50"}]},
    )

    # первая заявка — будет принята
    response = await client.post(
        "/api/storefront/magazin-berkat/requests",
        headers=buyer_headers,
        json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
    )
    request_id_1 = response.json()["id"]
    due = (date.today() + timedelta(days=3)).isoformat()
    await client.post(
        f"/api/storefront/requests/{request_id_1}/accept",
        headers=owner_headers,
        json={"warehouse_id": 1, "due_date": due},
    )

    # вторая заявка — будет отклонена
    response = await client.post(
        "/api/storefront/magazin-berkat/requests",
        headers=buyer_headers,
        json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
    )
    request_id_2 = response.json()["id"]
    await client.post(f"/api/storefront/requests/{request_id_2}/reject", headers=owner_headers)

    # третья заявка — остаётся новой
    await client.post(
        "/api/storefront/magazin-berkat/requests",
        headers=buyer_headers,
        json={"customer_name": "Ахмед", "items": [{"product_id": product["id"], "quantity": "1"}]},
    )

    response = await client.get("/api/auth/customer/me", headers=buyer_headers)
    assert response.status_code == 200, response.text
    assert response.json()["stats"] == {
        "requests_total": 3, "requests_accepted": 1, "requests_rejected": 1,
    }
