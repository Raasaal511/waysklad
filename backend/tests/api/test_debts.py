from datetime import date, timedelta


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


async def test_due_debt_whatsapp_reminder_link_via_api(client, owner_headers):
    today = date.today().isoformat()

    response = await client.post(
        "/api/counterparties/clients",
        headers=owner_headers,
        json={"name": "С телефоном", "phone": "+79281112233"},
    )
    with_phone_id = response.json()["id"]
    response = await client.post(
        "/api/debts",
        headers=owner_headers,
        json={"client_id": with_phone_id, "warehouse_id": 1, "amount": "1000", "due_date": today},
    )
    assert response.status_code == 201, response.text

    response = await client.post(
        "/api/counterparties/clients", headers=owner_headers, json={"name": "Без телефона"},
    )
    without_phone_id = response.json()["id"]
    response = await client.post(
        "/api/debts",
        headers=owner_headers,
        json={"client_id": without_phone_id, "warehouse_id": 1, "amount": "500", "due_date": today},
    )
    assert response.status_code == 201, response.text

    response = await client.get("/api/debts/due", headers=owner_headers)
    assert response.status_code == 200, response.text
    by_client = {d["client_id"]: d for d in response.json()}

    with_phone_link = by_client[with_phone_id]["whatsapp_reminder_link"]
    assert with_phone_link is not None
    assert with_phone_link.startswith("https://wa.me/79281112233?text=")
    assert "1000" in with_phone_link

    assert by_client[without_phone_id]["whatsapp_reminder_link"] is None
